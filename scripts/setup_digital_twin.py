"""
One-time setup for CRYO digital twin data dependencies.

Run from repo root:
    python scripts/setup_digital_twin.py

Steps:
  1. Verify Human1 model is accessible (required)
  2. Create SQLite drug target cache (required)
  3. Download CCLE expression data → parquet (optional, enables cell line personalization)
  4. Download GDSC2 sensitivity data → CSV (optional, enables IC50 validation)
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CRYO_DATA = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data"))
CACHE_DIR = CRYO_DATA / "cache"
CCLE_DIR = CRYO_DATA / "ccle"
GDSC_DIR = CRYO_DATA / "gdsc"
MODEL_PATH = CRYO_DATA / "models" / "human1" / "human1.xml"

DB_PATH = CACHE_DIR / "drug_targets.db"
CCLE_PARQUET = CCLE_DIR / "ccle_expression_human1.parquet"
GDSC_CSV = GDSC_DIR / "gdsc2_sensitivity.csv"

# GDSC2 public download (Sanger Institute / EMBL-EBI)
GDSC_URL = "https://cog.sanger.ac.uk/cancerrxgene/GDSC_release8.5/GDSC2_fitted_dose_response_27Oct23.csv"

# DepMap CCLE expression (public, protein-coding genes TPM log2+1)
CCLE_URL = "https://figshare.com/ndownloader/files/34008434"


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗  {msg}")


# ---------------------------------------------------------------------------
# Step 1 — Verify Human1
# ---------------------------------------------------------------------------
def verify_human1() -> bool:
    print("\n[1/4] Verifying Human1 model …")
    if MODEL_PATH.exists():
        _ok(f"Human1 found at {MODEL_PATH}")
        return True
    _fail(f"Human1 not found at {MODEL_PATH}")
    print("      Place human1.xml at that path and re-run.")
    return False


# ---------------------------------------------------------------------------
# Step 2 — SQLite cache
# ---------------------------------------------------------------------------
def setup_cache_db() -> bool:
    print("\n[2/4] Setting up SQLite drug target cache …")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS drug_targets (
                drug_name   TEXT NOT NULL,
                gene_symbol TEXT NOT NULL,
                source      TEXT NOT NULL,
                mechanism   TEXT,
                cached_at   INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                PRIMARY KEY (drug_name, gene_symbol, source)
            );
            CREATE TABLE IF NOT EXISTS drug_reactions (
                drug_name   TEXT NOT NULL,
                reaction_id TEXT NOT NULL,
                gene_symbol TEXT NOT NULL,
                PRIMARY KEY (drug_name, reaction_id)
            );
        """)
        con.commit()
        con.close()
        _ok(f"SQLite cache ready at {DB_PATH}")
        return True
    except Exception as exc:
        _fail(f"SQLite setup failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Step 3 — CCLE download + parquet
# ---------------------------------------------------------------------------
def download_ccle() -> bool:
    print("\n[3/4] Setting up CCLE expression data …")
    if CCLE_PARQUET.exists():
        _ok(f"CCLE parquet already present at {CCLE_PARQUET}")
        return True

    CCLE_DIR.mkdir(parents=True, exist_ok=True)
    raw_csv = CCLE_DIR / "ccle_expression_raw.csv"

    try:
        import urllib.request

        print(f"      Downloading CCLE CSV (~200 MB) from DepMap …")
        print(f"      URL: {CCLE_URL}")
        urllib.request.urlretrieve(CCLE_URL, raw_csv)
        _ok(f"Downloaded to {raw_csv}")
    except Exception as exc:
        _warn(f"CCLE download failed: {exc}")
        _warn("Cell line personalization will be disabled until CCLE data is available.")
        _warn("To add manually: place CCLE expression CSV at " + str(raw_csv))
        return False

    try:
        _preprocess_ccle(raw_csv)
        raw_csv.unlink(missing_ok=True)
        _ok(f"CCLE parquet written to {CCLE_PARQUET}")
        return True
    except Exception as exc:
        _warn(f"CCLE preprocessing failed: {exc}")
        return False


def _preprocess_ccle(raw_csv: Path) -> None:
    import math

    import pandas as pd

    SUPPORTED_CELL_LINES = {
        "HeLa", "MCF7", "A549", "HCT116", "PC-3", "LNCaP", "U87", "T98G",
        "HepG2", "K562", "Jurkat", "HL-60", "MOLT-4", "CCRF-CEM", "NCI-H460",
        "NCI-H1299", "CALU-1", "SW480", "HT-29", "COLO-205", "MDA-MB-231",
        "MDA-MB-468", "BT-474", "SK-BR-3", "T-47D", "ZR-75-1", "MDA-MB-453",
        "CAL-51", "BT-549", "HS-578T", "DU-145", "22RV1", "VCaP", "LAPC4",
        "MDA PCa 2b", "SH-SY5Y", "SK-N-SH", "IMR-32", "BE-2-C", "NB4",
        "KG-1", "THP-1", "U937", "RAJI", "DAUDI", "SK-MEL-28", "A-375",
        "G-361", "COLO-829", "WM-115",
    }

    print("      Loading raw CSV (this may take a minute) …")
    df = pd.read_csv(raw_csv, index_col=0)

    # Filter to supported cell lines (fuzzy: strip spaces/hyphens)
    def normalize(name: str) -> str:
        return name.replace("-", "").replace(" ", "").upper()

    norm_supported = {normalize(cl): cl for cl in SUPPORTED_CELL_LINES}
    keep_rows = {}
    for idx in df.index:
        cell = str(idx).split(" (")[0].strip()
        n = normalize(cell)
        if n in norm_supported:
            keep_rows[norm_supported[n]] = idx

    df = df.loc[list(keep_rows.values())]
    df.index = list(keep_rows.keys())

    # Strip Entrez IDs from column names: "GENE (1234)" → "GENE"
    df.columns = [c.split(" (")[0].strip() for c in df.columns]

    # Convert log2(TPM+1) → TPM
    df = df.apply(lambda col: col.apply(lambda v: max(0.0, math.pow(2, v) - 1)))

    df.to_parquet(CCLE_PARQUET)
    print(f"      Preprocessed {len(df)} cell lines × {len(df.columns)} genes.")


# ---------------------------------------------------------------------------
# Step 4 — GDSC download
# ---------------------------------------------------------------------------
def download_gdsc() -> bool:
    print("\n[4/4] Setting up GDSC2 sensitivity data …")
    if GDSC_CSV.exists():
        _ok(f"GDSC2 CSV already present at {GDSC_CSV}")
        return True

    GDSC_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import urllib.request

        print(f"      Downloading GDSC2 CSV (~10 MB) from Sanger/EMBL-EBI …")
        print(f"      URL: {GDSC_URL}")
        urllib.request.urlretrieve(GDSC_URL, GDSC_CSV)
        _ok(f"Downloaded to {GDSC_CSV}")
        return True
    except Exception as exc:
        _warn(f"GDSC download failed: {exc}")
        _warn("IC50 experimental validation will be disabled until GDSC2 data is available.")
        _warn("To add manually: place GDSC2 CSV at " + str(GDSC_CSV))
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("  CRYO Digital Twin — Data Setup")
    print("=" * 60)

    step1 = verify_human1()
    step2 = setup_cache_db()
    step3 = download_ccle()
    step4 = download_gdsc()

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  Human1 model:      {'✓ ready' if step1 else '✗ MISSING (required)'}")
    print(f"  SQLite drug cache: {'✓ ready' if step2 else '✗ FAILED (required)'}")
    print(f"  CCLE expression:   {'✓ ready' if step3 else '⚠ not available (optional)'}")
    print(f"  GDSC2 validation:  {'✓ ready' if step4 else '⚠ not available (optional)'}")
    print()

    if not step1 or not step2:
        print("  Required components missing. Fix errors above and re-run.")
        sys.exit(1)

    print("  Core setup complete. Run: /digital_twin imatinib --cell_line MCF7")
    if not step3:
        print("  Note: CCLE unavailable — GPR expression scaling disabled.")
    if not step4:
        print("  Note: GDSC2 unavailable — IC50 validation disabled.")


if __name__ == "__main__":
    main()
