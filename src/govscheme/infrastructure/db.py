"""SQLite repository (swappable for PostgreSQL behind the same methods) and validated seed import."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, source_url TEXT, source_title TEXT, source_type TEXT,
  retrieved_at TEXT, last_verified_at TEXT, verification_status TEXT NOT NULL DEFAULT 'verification_required', source_page TEXT);
CREATE TABLE IF NOT EXISTS schemes(id TEXT PRIMARY KEY, name TEXT NOT NULL, level TEXT NOT NULL CHECK(level IN('Central','State')),
  state TEXT, category TEXT, benefit TEXT, description TEXT, source_id TEXT REFERENCES sources(id));
CREATE TABLE IF NOT EXISTS eligibility_rules(id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_id TEXT NOT NULL REFERENCES schemes(id),
  criterion TEXT NOT NULL, operator TEXT NOT NULL, expected_value TEXT NOT NULL, description TEXT, source_reference TEXT,
  verification_status TEXT NOT NULL DEFAULT 'verification_required', last_verified_at TEXT, effective_from TEXT, effective_to TEXT);
CREATE TABLE IF NOT EXISTS required_documents(id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_id TEXT NOT NULL REFERENCES schemes(id), name TEXT NOT NULL);
"""
OPERATORS = {"less_than_or_equal", "greater_than_or_equal", "equals", "in"}


class Repository:
    def __init__(self, path: Path | str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def counts(self) -> dict[str, int]:
        return {t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("schemes", "eligibility_rules", "required_documents", "sources")}

    def import_file(self, path: Path | str) -> dict[str, int]:
        """Validate and import a JSON seed file; deduplicates by scheme id and keeps provenance."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for s in data["schemes"]:
            for r in s.get("rules", []):
                if r["operator"] not in OPERATORS:
                    raise ValueError(f"{s['id']}: unknown operator {r['operator']}")
            src = s.get("source", {})
            sid = f"src-{s['id']}"
            self.conn.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?,?)", (sid, src.get("source_url"),
                src.get("source_title"), src.get("source_type", "manual entry"), src.get("retrieved_at"),
                src.get("last_verified_at"), src.get("verification_status", "verification_required"), src.get("source_page")))
            if self.conn.execute("SELECT 1 FROM schemes WHERE id=?", (s["id"],)).fetchone():
                continue  # dedupe
            self.conn.execute("INSERT INTO schemes VALUES(?,?,?,?,?,?,?,?)", (s["id"], s["name"], s["level"],
                s.get("state"), s.get("category"), s.get("benefit"), s.get("description"), sid))
            for r in s.get("rules", []):
                self.conn.execute("""INSERT INTO eligibility_rules(scheme_id,criterion,operator,expected_value,description,
                  source_reference,verification_status,last_verified_at,effective_from,effective_to) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (s["id"], r["criterion"], r["operator"], json.dumps(r["expected"]), r.get("description"),
                   r.get("source_reference", ""), r.get("verification_status", "verification_required"),
                   r.get("last_verified_at"), r.get("effective_from"), r.get("effective_to")))
            for d in s.get("documents", []):
                self.conn.execute("INSERT INTO required_documents(scheme_id,name) VALUES(?,?)", (s["id"], d))
        self.conn.commit()
        return self.counts()

    def schemes(self) -> list[dict[str, Any]]:
        out = []
        for row in self.conn.execute("SELECT s.*, src.source_url, src.verification_status AS source_status FROM schemes s LEFT JOIN sources src ON src.id=s.source_id"):
            d = dict(row)
            d["rules"] = [dict(r) | {"expected": json.loads(r["expected_value"])} for r in
                          self.conn.execute("SELECT * FROM eligibility_rules WHERE scheme_id=?", (d["id"],))]
            d["documents"] = [r["name"] for r in self.conn.execute("SELECT name FROM required_documents WHERE scheme_id=?", (d["id"],))]
            out.append(d)
        return out
