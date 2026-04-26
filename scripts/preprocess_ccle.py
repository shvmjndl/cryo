"""
Preprocess DepMap CCLE expression data into the parquet format used by ccle_loader.py.

Reads the DepMap expression file (OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv or
OmicsExpressionProteinCodingGenesTPMLogp1.csv) and creates:
    /cryo-data/ccle/ccle_expression_human1.parquet

The DepMap file uses ACH-XXXXXX model IDs. This script maps them to canonical cell line
names using either a companion Model.csv (if present) or a hardcoded known-good mapping.

Usage (from repo root):
    docker exec cryo-api-1 python /app/scripts/preprocess_ccle.py
"""
from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

CRYO_DATA = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data"))
CCLE_DIR = CRYO_DATA / "ccle"
OUT_PARQUET = CCLE_DIR / "ccle_expression_human1.parquet"

# Filenames to search for (in order of preference)
CANDIDATE_CSVS = [
    "OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv",
    "OmicsExpressionProteinCodingGenesTPMLogp1.csv",
    "ccle_expression_raw.csv",
]

# Model.csv companion file — if present, used for full ACH-ID → name mapping
MODEL_CSV = CCLE_DIR / "Model.csv"

# ─── Hardcoded ACH-ID → canonical cell line name ─────────────────────────────
# Stable across DepMap releases for established cell lines.
# From DepMap public portal (https://depmap.org/portal).
ACH_TO_NAME: dict[str, str] = {
    "ACH-000019": "MCF7",
    "ACH-000135": "HELA",
    "ACH-000681": "A549",
    "ACH-000971": "HCT116",
    "ACH-000015": "PC3",
    "ACH-000044": "LNCAP",
    "ACH-000787": "U87MG",
    "ACH-000180": "HEPG2",
    "ACH-000694": "K562",
    "ACH-000219": "JURKAT",
    "ACH-000521": "T98G",
    "ACH-000592": "MDAMB231",
    "ACH-000193": "MDAMB468",
    "ACH-000452": "SKBR3",
    "ACH-000714": "BT474",
    "ACH-000230": "ZR751",
    "ACH-000234": "NCIH1299",
    "ACH-000569": "NCIH460",
    "ACH-000559": "SW480",
    "ACH-000340": "HT29",
    "ACH-000552": "PANC1",
    "ACH-000113": "DU145",
    "ACH-000810": "22RV1",
    "ACH-000174": "VCAP",
    "ACH-000115": "SHSY5Y",
    "ACH-000086": "IMR90",
    "ACH-000130": "COLO205",
    "ACH-000370": "SW620",
    "ACH-000279": "NB4",
    "ACH-000495": "THP1",
    "ACH-000013": "U937",
    "ACH-000063": "RAJI",
    "ACH-000122": "DAUDI",
    "ACH-000118": "SKMEL28",
    "ACH-000143": "A375",
    "ACH-000138": "COLO829",
    "ACH-000100": "WM115",
    "ACH-000175": "CAL51",
    "ACH-000247": "BT549",
    "ACH-000224": "HS578T",
    "ACH-000218": "CAPAN1",
    "ACH-000191": "MIAPACA2",
    "ACH-000028": "HL60",
    "ACH-000056": "MOLT4",
    "ACH-000040": "CCRFCEM",
    "ACH-000588": "MM1S",
    "ACH-000208": "RPMI8226",
    "ACH-000158": "U266",
    "ACH-000001": "HEK293T",
}

# Also map common alias variants → canonical
NAME_ALIASES: dict[str, str] = {
    "MCF-7": "MCF7", "HeLa": "HELA", "HEK293": "HEK293T",
    "HepG2": "HEPG2", "PC-3": "PC3", "LNCaP": "LNCAP",
    "U87": "U87MG", "U87 MG": "U87MG",
    "MDA-MB-231": "MDAMB231", "MDA-MB-468": "MDAMB468",
    "SK-BR-3": "SKBR3", "ZR-75-1": "ZR751",
    "NCI-H1299": "NCIH1299", "NCI-H460": "NCIH460",
    "SH-SY5Y": "SHSY5Y", "SK-MEL-28": "SKMEL28",
    "COLO-205": "COLO205", "COLO-829": "COLO829",
    "HL-60": "HL60", "MOLT-4": "MOLT4",
    "CCRF-CEM": "CCRFCEM", "MM.1S": "MM1S",
    "RPMI-8226": "RPMI8226", "CAL-51": "CAL51",
    "BT-474": "BT474", "BT-549": "BT549",
    "HS-578T": "HS578T", "T-47D": "T47D",
    "MIA PaCa-2": "MIAPACA2",
}


def _normalize(name: str) -> str:
    return name.upper().replace("-", "").replace(" ", "").replace(".", "")


def _load_model_csv(path: Path) -> dict[str, str]:
    """Load Model.csv → {ach_id: normalized_cell_line_name}."""
    mapping: dict[str, str] = {}
    try:
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                ach = row.get("ModelID", "") or row.get("DepMap_ID", "")
                name = row.get("CellLineName", "") or row.get("CCLE_Name", "")
                if ach and name:
                    mapping[ach] = _normalize(name.split("_")[0])  # strip tissue suffix
        print(f"  Loaded {len(mapping)} entries from {path.name}")
    except Exception as e:
        print(f"  Warning: could not read Model.csv: {e}")
    return mapping


def _build_ach_map() -> dict[str, str]:
    """Build ACH-ID → normalized name mapping (Model.csv + hardcoded)."""
    mapping = {k: _normalize(v) for k, v in ACH_TO_NAME.items()}
    if MODEL_CSV.exists():
        mapping.update(_load_model_csv(MODEL_CSV))
    return mapping


def _find_csv() -> Path | None:
    for name in CANDIDATE_CSVS:
        p = CCLE_DIR / name
        if p.exists():
            return p
    return None


def _logp1_to_tpm(v: float) -> float:
    """Convert log2(TPM+1) or log(TPM+1) to TPM."""
    return max(0.0, math.pow(2, v) - 1)


def preprocess(csv_path: Path) -> None:
    print(f"\n  Reading {csv_path.name} ({csv_path.stat().st_size // 1_000_000} MB) …")
    print("  This takes 1-2 minutes …")

    ach_map = _build_ach_map()
    print(f"  ACH-ID mapping: {len(ach_map)} known cell lines")

    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)

    # Detect format
    has_model_id = "ModelID" in header
    has_is_default = "IsDefaultEntryForModel" in header
    old_format = header[0] in ("", "Unnamed: 0") and not has_model_id

    if old_format:
        # Old DepMap format: index is cell line name directly
        print("  Detected old format (cell line names as index)")
        _preprocess_old_format(csv_path, header)
    else:
        print("  Detected new format (ACH model IDs)")
        _preprocess_new_format(csv_path, header, ach_map, has_model_id, has_is_default)


def _preprocess_new_format(
    csv_path: Path, header: list[str],
    ach_map: dict[str, str],
    has_model_id: bool, has_is_default: bool,
) -> None:
    import pandas as pd

    model_id_col = header.index("ModelID") if has_model_id else 3
    default_col = header.index("IsDefaultEntryForModel") if has_is_default else None

    # Gene columns start after metadata columns
    meta_cols = {"", "SequencingID", "ModelConditionID", "ModelID",
                 "IsDefaultEntryForMC", "IsDefaultEntryForModel"}
    gene_cols = [i for i, c in enumerate(header) if c not in meta_cols and " (" in c]
    if not gene_cols:
        # Old-style without Entrez IDs in column names
        gene_cols = [i for i, c in enumerate(header) if c not in meta_cols and c]

    gene_names = [header[i].split(" (")[0].strip() for i in gene_cols]
    print(f"  {len(gene_names)} genes in expression matrix")

    rows_by_cell_line: dict[str, list[float]] = {}

    with open(csv_path) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        skipped = 0
        for row in reader:
            if not row:
                continue
            if default_col is not None and row[default_col].strip() not in ("Yes", "TRUE", "1", "true"):
                skipped += 1
                continue

            ach = row[model_id_col].strip()
            cell_name = ach_map.get(ach)
            if not cell_name:
                skipped += 1
                continue

            values = [_logp1_to_tpm(float(row[i]) if row[i] else 0.0) for i in gene_cols]
            rows_by_cell_line[cell_name] = values

    print(f"  Kept {len(rows_by_cell_line)} cell lines (skipped {skipped} unmapped/non-default rows)")

    if not rows_by_cell_line:
        print("  ERROR: no cell lines matched. Check your Model.csv or hardcoded ACH-ID mapping.")
        sys.exit(1)

    df = pd.DataFrame(rows_by_cell_line, index=gene_names).T
    df.index.name = "cell_line"
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET)
    print(f"  Written: {OUT_PARQUET} ({OUT_PARQUET.stat().st_size // 1024}KB)")
    print(f"  Cell lines: {sorted(df.index.tolist())[:10]} … ({len(df)} total)")
    print(f"  Genes: {len(df.columns)}")


def _preprocess_old_format(csv_path: Path, header: list[str]) -> None:
    """Handle old DepMap format where index is cell line name."""
    import pandas as pd

    df = pd.read_csv(csv_path, index_col=0)
    # Strip gene Entrez IDs from column names
    df.columns = [c.split(" (")[0].strip() for c in df.columns]
    # Strip tissue suffix from row index: "MCF7_BREAST" → "MCF7"
    df.index = [r.split("_")[0].upper().replace("-", "") for r in df.index]
    # Convert log2(TPM+1) → TPM
    df = df.apply(lambda col: col.apply(_logp1_to_tpm))
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET)
    print(f"  Written: {OUT_PARQUET} ({OUT_PARQUET.stat().st_size // 1024}KB)")


def main() -> None:
    print("=" * 60)
    print("  CRYO CCLE Preprocessing")
    print("=" * 60)

    csv_path = _find_csv()
    if not csv_path:
        print(f"\n  ERROR: No CCLE expression CSV found in {CCLE_DIR}")
        print("  Expected one of:")
        for name in CANDIDATE_CSVS:
            print(f"    {CCLE_DIR / name}")
        print("\n  Download from: https://depmap.org/portal/download/")
        print("  File: OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv")
        sys.exit(1)

    if OUT_PARQUET.exists():
        print(f"\n  Parquet already exists at {OUT_PARQUET}")
        print("  Delete it and re-run to regenerate.")
        sys.exit(0)

    if MODEL_CSV.exists():
        print(f"\n  Found companion Model.csv — will use for full ACH-ID mapping")
    else:
        print(f"\n  No Model.csv found — using hardcoded ACH-ID mapping ({len(ACH_TO_NAME)} cell lines)")
        print("  Tip: place Model.csv from DepMap in /cryo-data/ccle/ for broader coverage")

    preprocess(csv_path)
    print("\n  Done. GPR scaling is now enabled.")
    print("  Run: /digital_twin imatinib --cell_line MCF7")


if __name__ == "__main__":
    main()
