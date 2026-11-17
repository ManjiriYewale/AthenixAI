"""
Import the 84 Central and Maharashtra government schemes
into the AthenixAI SQLite database.

Existing PDF indexing is preserved.
Synthetic DEMO records are removed.
"""

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

JSON_PATH = ROOT / "data" / "samples" / "india-central-maharashtra-schemes.json"
DB_PATH = ROOT / "storage" / "athenix.db"


def import_schemes():

    print("\n========== ATHENIXAI IMPORT ==========\n")

    # Load JSON
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        schemes = json.load(f)

    print("JSON schemes found:", len(schemes))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        # Remove only synthetic demo records
        demo_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM schemes WHERE id LIKE 'DEMO-%'"
            )
        ]

        for scheme_id in demo_ids:
            conn.execute(
                "DELETE FROM eligibility_rules WHERE scheme_id=?",
                (scheme_id,)
            )
            conn.execute(
                "DELETE FROM required_documents WHERE scheme_id=?",
                (scheme_id,)
            )
            conn.execute(
                "DELETE FROM schemes WHERE id=?",
                (scheme_id,)
            )
            conn.execute(
                "DELETE FROM sources WHERE id=?",
                (f"src-{scheme_id}",)
            )

        imported = 0

        for item in schemes:

            scheme_id = item["id"]

            jurisdiction = item.get("jurisdiction", "").strip()

            if jurisdiction == "Central":
                level = "Central"
                state = None

            elif jurisdiction == "Maharashtra":
                level = "State"
                state = "Maharashtra"

            else:
                raise ValueError(
                    f"Unknown jurisdiction: {jurisdiction}"
                )

            # Preserve eligibility information without
            # converting unverified descriptions into rules.
            eligibility = item.get("eligibility", [])

            if isinstance(eligibility, str):
                eligibility = [eligibility]

            eligibility_text = "\n".join(eligibility)

            description = (
                f"{item.get('summary', '')}\n\n"
                f"Eligibility information:\n{eligibility_text}\n\n"
                f"Application guidance:\n"
                f"{item.get('how_to_apply', '')}\n\n"
                f"Last catalogue review: {item.get('reviewed', 'Unknown')}"
            )

            source_id = f"src-{scheme_id}"

            source_url = (
                item.get("source_url")
                or item.get("official_url")
            )

            # Update source provenance
            conn.execute(
                """
                INSERT INTO sources (
                    id, source_url, source_title, source_type,
                    verification_status
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_url=excluded.source_url,
                    source_title=excluded.source_title,
                    source_type=excluded.source_type,
                    verification_status=excluded.verification_status
                """,
                (
                    source_id,
                    source_url,
                    item.get("source_label"),
                    "government_scheme_catalogue",
                    "verification_required"
                )
            )

            # Update existing catalogue record if re-imported
            conn.execute(
                """
                DELETE FROM eligibility_rules WHERE scheme_id=?
                """,
                (scheme_id,)
            )

            conn.execute(
                """
                DELETE FROM required_documents WHERE scheme_id=?
                """,
                (scheme_id,)
            )

            conn.execute(
                """
                INSERT INTO schemes (
                    id, name, level, state, category,
                    benefit, description, source_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    level=excluded.level,
                    state=excluded.state,
                    category=excluded.category,
                    benefit=excluded.benefit,
                    description=excluded.description,
                    source_id=excluded.source_id
                """,
                (
                    scheme_id,
                    item["name"],
                    level,
                    state,
                    item.get("category"),
                    item.get("summary"),
                    description,
                    source_id
                )
            )

            # Import documents
            documents = item.get("documents", [])

            if isinstance(documents, str):
                documents = [documents]

            for document in documents:
                conn.execute(
                    """
                    INSERT INTO required_documents(scheme_id, name)
                    VALUES (?, ?)
                    """,
                    (scheme_id, document)
                )

            imported += 1

        conn.commit()

        print("\n========== IMPORT SUCCESS ==========\n")

        print("Imported schemes:", imported)

        print(
            "Central schemes:",
            conn.execute(
                "SELECT COUNT(*) FROM schemes WHERE level='Central'"
            ).fetchone()[0]
        )

        print(
            "Maharashtra schemes:",
            conn.execute(
                "SELECT COUNT(*) FROM schemes WHERE level='State'"
            ).fetchone()[0]
        )

        print(
            "Total schemes:",
            conn.execute(
                "SELECT COUNT(*) FROM schemes"
            ).fetchone()[0]
        )

        print(
            "Eligibility rules:",
            conn.execute(
                "SELECT COUNT(*) FROM eligibility_rules"
            ).fetchone()[0]
        )

        print(
            "Required documents:",
            conn.execute(
                "SELECT COUNT(*) FROM required_documents"
            ).fetchone()[0]
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    import_schemes()