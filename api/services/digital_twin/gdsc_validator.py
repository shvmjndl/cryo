"""
GDSC (Genomics of Drug Sensitivity in Cancer) experimental validation lookup.

Compares CRYO's predicted growth inhibition against real experimental IC50 data.
Data source: GDSC2 from EMBL-EBI / Sanger Institute.
Reference: Yang W et al. (2013) Nucleic Acids Research. DOI: 10.1093/nar/gks1111
"""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("cryo.gdsc_validator")

_DATA_DIR = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data"))
_GDSC_CSV = _DATA_DIR / "gdsc" / "gdsc2_sensitivity.csv"

# Lazy-loaded: {(drug_lower, cell_line_lower): {"ic50_um": float, "auc": float}}
_GDSC_CACHE: dict[tuple[str, str], dict] | None = None


GDSC_CITATION = {
    "title": "Genomics of Drug Sensitivity in Cancer (GDSC): a resource for therapeutic biomarker discovery in cancer cells",
    "authors": "Yang W et al.",
    "year": 2013,
    "journal": "Nucleic Acids Research",
    "doi": "10.1093/nar/gks1111",
    "url": "https://doi.org/10.1093/nar/gks1111",
}


def _load_gdsc() -> dict[tuple[str, str], dict]:
    global _GDSC_CACHE
    if _GDSC_CACHE is not None:
        return _GDSC_CACHE

    _GDSC_CACHE = {}

    if not _GDSC_CSV.exists():
        logger.info("GDSC2 CSV not found at %s — validation unavailable", _GDSC_CSV)
        return _GDSC_CACHE

    try:
        import csv
        with open(_GDSC_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                drug = (row.get("DRUG_NAME") or row.get("drug_name") or "").strip().lower()
                cell = (row.get("CELL_LINE_NAME") or row.get("cell_line_name") or "").strip().lower()
                ln_ic50_str = row.get("LN_IC50") or row.get("ln_ic50") or ""
                auc_str = row.get("AUC") or row.get("auc") or ""

                if not drug or not cell or not ln_ic50_str:
                    continue
                try:
                    ln_ic50 = float(ln_ic50_str)
                    ic50_um = math.exp(ln_ic50)  # LN_IC50 is in ln(μM)
                    auc = float(auc_str) if auc_str else None
                    _GDSC_CACHE[(drug, cell)] = {"ic50_um": ic50_um, "auc": auc}
                except (ValueError, OverflowError):
                    continue

        logger.info("GDSC2 loaded: %d drug-cell pairs", len(_GDSC_CACHE))
    except Exception as e:
        logger.error("GDSC2 load failed: %s", e)
        _GDSC_CACHE = {}

    return _GDSC_CACHE


def _normalize(s: str) -> str:
    return s.lower().strip().replace("-", "").replace("_", "").replace(" ", "")


def lookup_gdsc(drug_name: str, cell_line: str) -> dict[str, Any]:
    """
    Look up GDSC2 experimental IC50 for a drug-cell line pair.

    Returns:
        {"found": bool, "drug_name": str, "cell_line": str,
         "ic50_um": float|None, "auc": float|None,
         "source": "GDSC2", "citation": dict}
    """
    if not drug_name or not cell_line:
        return {"found": False}

    cache = _load_gdsc()

    drug_lower = drug_name.lower().strip()
    cell_lower = cell_line.lower().strip()
    drug_norm = _normalize(drug_name)
    cell_norm = _normalize(cell_line)

    # Exact match first
    entry = cache.get((drug_lower, cell_lower))

    # Normalized fuzzy match
    if entry is None:
        for (d, c), v in cache.items():
            if _normalize(d) == drug_norm and _normalize(c) == cell_norm:
                entry = v
                break

    # Partial drug name match (e.g. "imatinib mesylate" vs "imatinib")
    if entry is None:
        for (d, c), v in cache.items():
            if drug_norm in _normalize(d) and _normalize(c) == cell_norm:
                entry = v
                break

    if entry is None:
        return {
            "found": False,
            "drug_name": drug_name,
            "cell_line": cell_line,
            "source": "GDSC2",
            "note": "No experimental data available for this drug-cell line pair in GDSC2.",
            "citation": GDSC_CITATION,
        }

    return {
        "found": True,
        "drug_name": drug_name,
        "cell_line": cell_line,
        "ic50_um": round(entry["ic50_um"], 4),
        "auc": entry["auc"],
        "source": "GDSC2",
        "citation": GDSC_CITATION,
    }
