"""
Essential gene analysis via single-gene knockout FBA.

An essential gene is one whose deletion reduces the growth rate (biomass objective)
below a threshold fraction of wild-type growth. These are candidate antibiotic/antifungal
targets because inhibiting them would selectively kill the pathogen.

Results are cached in SQLite (alongside drug targets) with a 30-day TTL, since
computing ~1,300 knockouts takes ~2–5 minutes on Human1 and ~30s on iJO1366.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
from typing import Any

import cobra
from cobra.flux_analysis import single_gene_deletion

logger = logging.getLogger("cryo.essential_genes")

_DB_PATH = Path(os.getenv("DRUG_TARGETS_DB_PATH",
                           os.path.join(os.getenv("CRYO_DATA_DIR", "/cryo-data"),
                                        "cache", "drug_targets.db")))
_TTL_DAYS = 30


def _init_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS essential_genes (
            backbone        TEXT NOT NULL,
            computed_at     TEXT NOT NULL,
            threshold       REAL NOT NULL,
            gene_ids_json   TEXT NOT NULL,
            stats_json      TEXT NOT NULL,
            PRIMARY KEY (backbone, threshold)
        )
    """)
    conn.commit()
    return conn


def _cache_fresh(computed_at: str) -> bool:
    try:
        ts = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - ts < timedelta(days=_TTL_DAYS)
    except Exception:
        return False


def get_cached_essential_genes(backbone: str, threshold: float = 0.01) -> list[str] | None:
    try:
        conn = _init_db()
        row = conn.execute(
            "SELECT computed_at, gene_ids_json FROM essential_genes WHERE backbone=? AND threshold=?",
            (backbone, threshold),
        ).fetchone()
        conn.close()
        if row and _cache_fresh(row[0]):
            return json.loads(row[1])
    except Exception as exc:
        logger.warning("Cache read failed: %s", exc)
    return None


def _save_essential_genes(backbone: str, gene_ids: list[str], stats: dict, threshold: float) -> None:
    try:
        conn = _init_db()
        conn.execute(
            """INSERT OR REPLACE INTO essential_genes
               (backbone, computed_at, threshold, gene_ids_json, stats_json)
               VALUES (?,?,?,?,?)""",
            (
                backbone,
                datetime.now(timezone.utc).isoformat(),
                threshold,
                json.dumps(gene_ids),
                json.dumps(stats),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)


def compute_essential_genes(
    model: cobra.Model,
    backbone: str,
    threshold: float = 0.01,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Identify essential genes via single-gene deletion FBA.

    Args:
        model:     COBRApy model (read — will be copied internally by cobra).
        backbone:  Model key for caching (e.g. "ijo1366", "human1").
        threshold: Growth fraction below which a gene is considered essential (default 1% of WT).
        use_cache: Return cached result if available.

    Returns:
        {
            essential_genes: [gene_id, ...],
            total_genes: int,
            essential_count: int,
            wt_growth: float,
            threshold_used: float,
            backbone: str,
            cached: bool,
            computed_at: str,
        }
    """
    if use_cache:
        cached = get_cached_essential_genes(backbone, threshold)
        if cached is not None:
            return {
                "essential_genes": cached,
                "essential_count": len(cached),
                "total_genes": len(model.genes),
                "cached": True,
                "backbone": backbone,
                "threshold_used": threshold,
            }

    logger.info("Computing essential genes for %s (%d genes) — this may take minutes",
                backbone, len(model.genes))

    wt_solution = model.optimize()
    wt_growth = float(wt_solution.objective_value or 0.0)
    if wt_growth < 1e-6:
        return {
            "error": "Wild-type growth is infeasible or near-zero — cannot compute essentiality.",
            "wt_growth": wt_growth,
            "backbone": backbone,
        }

    growth_cutoff = wt_growth * threshold

    # single_gene_deletion returns a DataFrame indexed by frozenset({gene_id})
    deletion_results = single_gene_deletion(model)

    essential_ids: list[str] = []
    for idx, row in deletion_results.iterrows():
        growth = row.get("growth", row.get("objective_value", 0.0))
        if growth is None or growth < growth_cutoff:
            gene_id = next(iter(idx))  # frozenset → single element
            essential_ids.append(str(gene_id))

    essential_ids.sort()
    stats = {
        "wt_growth": wt_growth,
        "total_genes": len(model.genes),
        "essential_count": len(essential_ids),
        "threshold_fraction": threshold,
        "growth_cutoff": growth_cutoff,
    }
    _save_essential_genes(backbone, essential_ids, stats, threshold)

    logger.info("Essential genes computed: %d / %d", len(essential_ids), len(model.genes))
    return {
        "essential_genes": essential_ids,
        "essential_count": len(essential_ids),
        "total_genes": len(model.genes),
        "wt_growth": wt_growth,
        "threshold_used": threshold,
        "backbone": backbone,
        "cached": False,
    }


def annotate_targets_with_essentiality(
    drug_target_info: dict[str, Any],
    essential_gene_ids: list[str],
) -> dict[str, Any]:
    """Tag each drug target gene with whether it is essential in the model."""
    essential_set = set(essential_gene_ids)
    annotated_targets = []
    for t in drug_target_info.get("targets", []):
        t_copy = dict(t)
        gene_ids = t.get("gene_ids", [])
        t_copy["is_essential"] = any(g in essential_set for g in gene_ids) if gene_ids else None
        annotated_targets.append(t_copy)
    return {**drug_target_info, "targets": annotated_targets}
