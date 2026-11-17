"""Safely correct existing ChromaDB scheme IDs using PDF filename mapping."""

from pathlib import Path
import chromadb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "storage" / "chroma_db"

COLLECTION_NAME = "government_schemes"

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

    # Central Sector Scholarship
    "CSSS_GUIDLINES_06022024.pdf": "catalog-027",
    "SCHOLARSHIP PRADHAN MANTRI UCHCHATAR SHIKSHA PROTSAHAN (PMUSP) YOJANA.pdf": "catalog-027",

    # PMAY-G
    "PMAY G Advancing Housing for All in Rural India.pdf": "catalog-074",
}


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"ChromaDB not found: {DB_PATH}")

    client = chromadb.PersistentClient(path=str(DB_PATH))

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    total = collection.count()

    print("Existing ChromaDB chunks:", total)

    updated = 0
    unmapped_sources = set()

    batch_size = 200

    for offset in range(0, total, batch_size):

        records = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas"],
        )

        ids = records["ids"]
        metadatas = records["metadatas"]

        update_ids = []
        update_metadatas = []

        for chunk_id, metadata in zip(ids, metadatas):

            source = metadata.get("source", "")
            target_scheme_id = SCHEME_DOCUMENT_MAP.get(source)

            if target_scheme_id is None:
                unmapped_sources.add(source)
                continue

            if metadata.get("scheme_id") == target_scheme_id:
                continue

            corrected_metadata = dict(metadata)
            corrected_metadata["scheme_id"] = target_scheme_id

            update_ids.append(chunk_id)
            update_metadatas.append(corrected_metadata)

        if update_ids:
            collection.update(
                ids=update_ids,
                metadatas=update_metadatas,
            )

            updated += len(update_ids)

        print(f"Checked {min(offset + batch_size, total)}/{total}")

    print("\nMetadata correction completed.")
    print("Updated chunks:", updated)
    print("Total chunks now:", collection.count())

    print("\nUnmapped PDF sources:")
    for source in sorted(unmapped_sources):
        print("-", source)

    print("\nVerified scheme ID counts:")

    for scheme_id in sorted(set(SCHEME_DOCUMENT_MAP.values())):
        result = collection.get(
            where={"scheme_id": scheme_id},
            include=["metadatas"],
        )

        print(f"{scheme_id}: {len(result['ids'])} chunks")


if __name__ == "__main__":
    main()