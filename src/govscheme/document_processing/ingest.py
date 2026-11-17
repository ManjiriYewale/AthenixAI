"""Extract text with page metadata, clean conservatively, and chunk with provenance."""
from __future__ import annotations
import hashlib
import re
from collections import Counter
from pathlib import Path

# Verified document-to-catalogue mappings.
# Unmapped PDFs retain their filename as their scheme_id.
SCHEME_DOCUMENT_MAP = {
    # PM-KISAN
    "FAQPMKISAN.pdf": "catalog-001",
    "RevisedPM-KISANOperationalGuidelines(English).pdf": "catalog-001",
    "Note-on-Modes-and-processes-of-ekyc-13th-Nov-English.pdf": "catalog-001",

    # PMFBY
    "operational_guidelines_pmfby.pdf": "catalog-003",
    "THE OPERATIONAL GUIDELINES OF PMFBY.pdf": "catalog-003",
    "Final_Presentation_CEO Sir_5 Years of PMFBY_13.01.2021.pdf": "catalog-003",

    # AB PM-JAY
    "BeneficiaryIdentificationGuidelines ABPNJAY.pdf": "catalog-049",
    "Capacity Building Guidelines AB PMJAY.pdf": "catalog-049",

    # Central Sector Scholarship Scheme
    "CSSS_GUIDLINES_06022024.pdf": "catalog-027",
    "SCHOLARSHIP PRADHAN MANTRI UCHCHATAR SHIKSHA PROTSAHAN (PMUSP) YOJANA.pdf": "catalog-027",

    # PMAY-G
    "PMAY G Advancing Housing for All in Rural India.pdf": "catalog-074",
}

INJECTION = re.compile(r"ignore (all )?(previous|prior|above) instructions|system prompt|you are now|disregard .{0,30}(rules|instructions)", re.I)


def extract_pages(path: Path) -> list[str]:
    """Return one string per page (txt uses form-feed breaks; docx has a single 'page')."""
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace").split("\f")
    if ext == ".pdf":
        from pypdf import PdfReader
        return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    if ext == ".docx":
        from docx import Document
        return ["\n".join(p.text for p in Document(str(path)).paragraphs)]
    raise ValueError(f"Unsupported document type: {ext}")


def clean_pages(pages: list[str]) -> list[str]:
    """Drop lines repeated on most pages (headers/footers); keep amounts, dates and wording intact."""
    if len(pages) >= 3:
        seen = Counter(l.strip() for p in pages for l in set(p.splitlines()) if l.strip())
        pages = ["\n".join(l for l in p.splitlines() if seen[l.strip()] <= len(pages) // 2) for p in pages]
    return [re.sub(r"[ \t]+", " ", p).strip() for p in pages]


def chunk_page(text: str, max_chars: int = 900) -> list[str]:
    """Group paragraphs up to max_chars with a one-paragraph overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=Step \d)", text) if p.strip()]
    chunks, cur = [], []
    for p in paras:
        if cur and sum(map(len, cur)) + len(p) > max_chars:
            chunks.append("\n".join(cur)); cur = cur[-1:]
        cur.append(p)
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def ingest_file(path: Path, scheme_id: str | None = None) -> list[dict]:
    """Chunks carry scheme_id, source, page and a deterministic id so re-ingestion updates, not duplicates."""
    scheme_id = scheme_id or SCHEME_DOCUMENT_MAP.get(path.name, path.stem)
    out = []
    for page_no, page in enumerate(clean_pages(extract_pages(path)), 1):
        for i, text in enumerate(chunk_page(page)):
            cid = hashlib.sha1(f"{scheme_id}|{path.name}|{page_no}|{i}".encode()).hexdigest()[:16]
            out.append({"chunk_id": cid, "scheme_id": scheme_id, "source": path.name, "page": page_no,
                        "text": text, "suspicious": bool(INJECTION.search(text))})
    return out


def load_documents(dirs: list[Path]) -> list[dict]:
    chunks: dict[str, dict] = {}
    for d in dirs:
        for f in sorted(Path(d).glob("*")) if Path(d).exists() else []:
            if f.suffix.lower() in (".txt", ".md", ".pdf", ".docx"):
                for c in ingest_file(f):
                    chunks[c["chunk_id"]] = c
    return list(chunks.values())
