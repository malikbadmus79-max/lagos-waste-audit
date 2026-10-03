"""Repository paths, resolved from the package location."""

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
DATA_RAW: Path = ROOT / "data" / "raw"
DATA_INTERIM: Path = ROOT / "data" / "interim"
DATA_PROCESSED: Path = ROOT / "data" / "processed"
FIGURES: Path = ROOT / "reports" / "figures"
MAPS: Path = ROOT / "reports" / "maps"
