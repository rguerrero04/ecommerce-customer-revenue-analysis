"""Remove reproducible local data and analysis outputs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "data" / "raw" / "online_retail.zip",
    ROOT / "data" / "raw" / "Online Retail.xlsx",
    ROOT / "data" / "processed" / "ecommerce.db",
    ROOT / "data" / "processed" / "ecommerce.db-journal",
]

for target in TARGETS:
    if target.exists():
        target.unlink()
        print(f"Removed {target.relative_to(ROOT)}")
