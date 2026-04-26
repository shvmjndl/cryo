"""
CCLE (Cancer Cell Line Encyclopedia) expression data loader and GPR-based reaction scaling.

Downloads from DepMap public portal. Preprocesses to parquet for fast per-cell-line lookup.
Implements a simplified GIMME-like algorithm: reactions whose ALL associated genes have
TPM < threshold are constrained to near-zero, reflecting tissue-specific inactivity.

Source: Barretina J et al. (2012) Nature. DOI: 10.1038/nature11003
Data:   DepMap public portal — https://depmap.org/portal/
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import cobra

logger = logging.getLogger("cryo.ccle_loader")

_DATA_DIR = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data"))
_CCLE_PARQUET = _DATA_DIR / "ccle" / "ccle_expression_human1.parquet"
_CCLE_CSV_RAW = _DATA_DIR / "ccle" / "OmicsExpressionProteinCodingGenesTPMLogp1.csv"

TPM_THRESHOLD = 1.0  # genes below this → constrain their reactions
CONSTRAINED_UB = 0.001  # near-zero flux limit for constrained reactions

# Canonical cell line names → DepMap cell line name variants
SUPPORTED_CELL_LINES = {
    "HeLa", "MCF7", "A549", "HCT116", "PC3", "PC-3", "LNCaP",
    "U87", "U87MG", "T98G", "HepG2", "K562", "Jurkat", "HL60",
    "MOLT4", "DAUDI", "RAMOS", "SHSY5Y", "SH-SY5Y", "SKNBE2",
    "SK-N-BE(2)", "IMR90", "BJ", "HEK293T", "293T", "HEK293",
    "MDAMB231", "MDA-MB-231", "MDAMB468", "MDA-MB-468",
    "SKBR3", "SK-BR-3", "BT474", "ZR751", "ZR-75-1",
    "COLO205", "SW480", "SW620", "HT29", "LS174T",
    "PANC1", "MIAPACA2", "CAPAN1",
    "U266", "RPMI8226", "MM1S",
    "NCI-H1299", "H1299", "NCI-H1650", "H1650",
}

# Normalize cell line name to lowercase key
def _normalize_cell_line(name: str) -> str:
    return name.upper().replace("-", "").replace("_", "").replace(" ", "").replace(".", "")


_expression_cache: dict[str, dict[str, float]] = {}


def _load_parquet() -> dict[str, dict[str, float]]:
    """Load CCLE parquet → {cell_line_key: {gene_symbol: tpm}}."""
    global _expression_cache
    if _expression_cache:
        return _expression_cache

    if not _CCLE_PARQUET.exists():
        logger.info("CCLE parquet not found at %s — GPR scaling unavailable", _CCLE_PARQUET)
        return {}

    try:
        try:
            import polars as pl
            df_pl = pl.read_parquet(str(_CCLE_PARQUET))
            for row in df_pl.iter_rows(named=True):
                cell_line_raw = row.get("cell_line", "")
                if not cell_line_raw:
                    continue
                key = _normalize_cell_line(str(cell_line_raw))
                gene_data = {k: float(v) for k, v in row.items() if k != "cell_line" and v is not None}
                _expression_cache[key] = gene_data
        except ImportError:
            import pandas as pd
            df_pd = pd.read_parquet(str(_CCLE_PARQUET))
            for cell_line_raw, row in df_pd.iterrows():
                key = _normalize_cell_line(str(cell_line_raw))
                _expression_cache[key] = {g: float(v) for g, v in row.items() if v is not None}
        logger.info("CCLE loaded: %d cell lines", len(_expression_cache))
    except Exception as e:
        logger.error("CCLE load failed: %s", e)

    return _expression_cache


def load_ccle_expression(cell_line: str) -> dict[str, float] | None:
    """
    Return {gene_symbol: tpm_value} for the given cell line.
    Returns None if CCLE data is not available or cell line not found.
    """
    cache = _load_parquet()
    if not cache:
        return None

    key = _normalize_cell_line(cell_line)

    # Exact match
    if key in cache:
        return cache[key]

    # Fuzzy: find any key that contains the query
    for k in cache:
        if key in k or k in key:
            return cache[k]

    logger.info("CCLE: cell line %r not found (available: %d lines)", cell_line, len(cache))
    return None


def apply_gpr_expression_scaling(
    model: cobra.Model,
    cell_line: str,
) -> tuple[cobra.Model, dict[str, Any]]:
    """
    Apply GPR-based expression scaling to a model copy.

    Algorithm (simplified GIMME):
    1. Load CCLE expression for cell_line → {gene: TPM}
    2. For each reaction in model:
       a. Get associated genes (COBRApy reaction.genes)
       b. If ALL genes with known expression have TPM < threshold:
          → constrain upper_bound to near-zero (reaction is inactive in this cell)
    3. Return (modified_model_copy, notes)

    This is conservative (AND logic) — only constrains reactions where ALL
    measured genes are below threshold, preventing false positives.

    IMPORTANT: Always operates on a copy — singleton model is never mutated.
    """
    notes: dict[str, Any] = {
        "cell_line": cell_line,
        "applied": False,
        "reactions_constrained": 0,
        "tpm_threshold": TPM_THRESHOLD,
        "reason": "",
        "citation": {
            "title": "The Cancer Cell Line Encyclopedia enables predictive modelling of anticancer drug sensitivity",
            "authors": "Barretina J et al.",
            "year": 2012,
            "journal": "Nature",
            "doi": "10.1038/nature11003",
            "url": "https://doi.org/10.1038/nature11003",
        },
    }

    expression = load_ccle_expression(cell_line)
    if expression is None:
        notes["reason"] = (
            f"CCLE expression data not available for '{cell_line}'. "
            "Run scripts/setup_digital_twin.py to download CCLE data. "
            "Simulation will proceed without GPR scaling."
        )
        logger.info("GPR scaling skipped: no CCLE data for %s", cell_line)
        return model, notes

    scaled_model = model.copy()
    constrained_ids: list[str] = []

    for reaction in scaled_model.reactions:
        genes = reaction.genes
        if not genes:
            continue  # exchange/transport reactions without gene associations untouched

        # Collect TPM values for all genes in this reaction.
        # Human1 stores HGNC symbols in g.annotation['hgnc.symbol'] (g.name is empty).
        gene_tpms: list[float] = []
        for g in genes:
            hgnc = (g.annotation or {}).get("hgnc.symbol", "") or g.name or ""
            tpm = expression.get(hgnc) or expression.get(g.id or "")
            if tpm is not None:
                gene_tpms.append(float(tpm))

        if not gene_tpms:
            continue  # no expression data for any gene in this reaction

        # AND logic: constrain only if ALL measured genes are below threshold
        if all(tpm < TPM_THRESHOLD for tpm in gene_tpms):
            if reaction.upper_bound > CONSTRAINED_UB:
                reaction.upper_bound = CONSTRAINED_UB
                constrained_ids.append(reaction.id)

    notes["applied"] = True
    notes["reactions_constrained"] = len(constrained_ids)
    notes["genes_with_data"] = len(expression)
    logger.info(
        "GPR scaling applied for %s: %d reactions constrained (threshold=%.1f TPM)",
        cell_line, len(constrained_ids), TPM_THRESHOLD
    )
    return scaled_model, notes


CCLE_CITATION = {
    "title": "The Cancer Cell Line Encyclopedia enables predictive modelling of anticancer drug sensitivity",
    "authors": "Barretina J et al.",
    "year": 2012,
    "journal": "Nature",
    "doi": "10.1038/nature11003",
    "url": "https://doi.org/10.1038/nature11003",
}
