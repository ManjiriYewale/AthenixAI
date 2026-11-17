"""Usage: python scripts/import_seed.py path/to/reviewed_schemes.json  (validates, dedupes, keeps provenance)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from govscheme.config import settings
from govscheme.infrastructure.db import Repository

print(Repository(settings.DB_PATH).import_file(sys.argv[1] if len(sys.argv) > 1 else settings.SEED_PATH))
