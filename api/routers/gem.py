"""
GEM graph API — expose the metabolite–reaction–gene tripartite graph for any loaded model.

All endpoints are read-only. The model is fetched from the DigitalTwinService pool
(no re-loading if already cached). Backbone selection defaults to human1.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from api.services.digital_twin_service import digital_twin_service
from api.services.digital_twin.gem_graph import (
    build_gem_graph,
    get_model_stats,
    query_gem,
    get_gene_neighborhood,
    get_reaction_detail,
    get_metabolite_detail,
    get_subsystem_reactions,
    compare_gene_sets,
)
from api.services.digital_twin.essential_genes import compute_essential_genes
from api.services.digital_twin.organism import detect_organism, organism_display

router = APIRouter(prefix="/gem", tags=["gem"])


def _get_model(backbone: str):
    """Resolve model from pool or load on demand."""
    try:
        return digital_twin_service.get_model_for_backbone(backbone)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load backbone '{backbone}': {exc}")


# ── /gem/backbones — list available models ─────────────────────────────────────

@router.get("/backbones")
async def list_backbones():
    """List all supported backbone models with loaded status."""
    return {
        "backbones": digital_twin_service.available_backbones(),
    }


# ── /gem/stats — model statistics ─────────────────────────────────────────────

@router.get("/stats")
async def gem_stats(backbone: str = Query(default="human1", description="Model backbone key")):
    """Return statistics for the requested GEM (reactions, metabolites, genes, subsystems)."""
    model, meta = _get_model(backbone)
    organism = detect_organism(model)
    stats = get_model_stats(model)
    return {
        **stats,
        "backbone": backbone,
        "organism": organism,
        "organism_display": organism_display(organism),
        "model_metadata": {
            "source": meta.get("source", ""),
            "display_name": meta.get("display_name", backbone),
        },
    }


# ── /gem/query — full-text search across metabolites, reactions, genes ──────────

@router.get("/query")
async def gem_query(
    q: str = Query(..., description="Search term"),
    backbone: str = Query(default="human1"),
    limit: int = Query(default=25, ge=1, le=100),
):
    """Search metabolites, reactions, and genes by name or ID."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' must not be empty")
    model, _ = _get_model(backbone)
    return query_gem(model, q.strip(), limit=limit)


# ── /gem/gene/{gene_id} — gene neighbourhood ──────────────────────────────────

@router.get("/gene/{gene_id}")
async def gene_neighborhood(
    gene_id: str,
    backbone: str = Query(default="human1"),
    depth: int = Query(default=1, ge=1, le=2),
):
    """Return reactions catalysed by a gene and their metabolites."""
    model, _ = _get_model(backbone)
    result = get_gene_neighborhood(model, gene_id, depth=depth)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── /gem/reaction/{reaction_id} ────────────────────────────────────────────────

@router.get("/reaction/{reaction_id}")
async def reaction_detail(
    reaction_id: str,
    backbone: str = Query(default="human1"),
):
    """Return full details of a single reaction."""
    model, _ = _get_model(backbone)
    result = get_reaction_detail(model, reaction_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── /gem/metabolite/{metabolite_id} ───────────────────────────────────────────

@router.get("/metabolite/{metabolite_id}")
async def metabolite_detail(
    metabolite_id: str,
    backbone: str = Query(default="human1"),
):
    """Return producing and consuming reactions for a metabolite."""
    model, _ = _get_model(backbone)
    result = get_metabolite_detail(model, metabolite_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── /gem/subsystem — pathway reactions ────────────────────────────────────────

@router.get("/subsystem")
async def subsystem_reactions(
    name: str = Query(..., description="Subsystem / pathway name"),
    backbone: str = Query(default="human1"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Return reactions in a metabolic subsystem/pathway."""
    model, _ = _get_model(backbone)
    return get_subsystem_reactions(model, name, limit=limit)


# ── /gem/essential_genes — computationally expensive, cached ──────────────────

@router.get("/essential_genes")
async def essential_genes(
    backbone: str = Query(default="ijo1366", description="Backbone to analyse (best for iJO1366 / Yeast8 — fast)"),
    threshold: float = Query(default=0.01, ge=0.0, le=0.1, description="Growth fraction below which gene is essential"),
    compute: bool = Query(default=False, description="Set to true to compute (slow — minutes for Human1). Returns cached if available."),
):
    """
    Return essential genes for the model.

    Essential = single gene knockout drops biomass below threshold × wildtype.
    Results are cached for 30 days.

    ⚠️  Human1 has ~2,800 genes — computation takes 5–10 minutes.
        iJO1366 has ~1,366 genes — computation takes ~1 minute.
        Pass compute=false (default) to return cached results only.
    """
    model, _ = _get_model(backbone)

    if not compute:
        from api.services.digital_twin.essential_genes import get_cached_essential_genes
        cached = get_cached_essential_genes(backbone, threshold)
        if cached is None:
            return {
                "cached": False,
                "message": "No cached results. Pass compute=true to run the analysis (may take minutes).",
                "backbone": backbone,
                "threshold": threshold,
            }
        return {
            "essential_genes": cached,
            "essential_count": len(cached),
            "total_genes": len(model.genes),
            "cached": True,
            "backbone": backbone,
            "threshold_used": threshold,
        }

    return compute_essential_genes(model, backbone, threshold=threshold, use_cache=True)


# ── /gem/compare_genes — compare two gene sets at reaction level ───────────────

class CompareGenesRequest(BaseModel):
    genes_a: list[str]
    genes_b: list[str]
    backbone: Optional[str] = "human1"


@router.post("/compare_genes")
async def compare_genes(request: CompareGenesRequest):
    """Compare two gene sets by their shared and unique metabolic reactions."""
    model, _ = _get_model(request.backbone or "human1")
    return compare_gene_sets(model, request.genes_a, request.genes_b)


# ── /gem/graph — full graph export (use sparingly on large models) ─────────────

@router.get("/graph")
async def gem_graph(
    backbone: str = Query(default="ijo1366", description="Recommended: ijo1366 or yeast8 (Human1 is very large)"),
    max_edges: int = Query(default=10_000, ge=100, le=100_000),
):
    """
    Export the full metabolite–reaction–gene graph.

    Human1 has ~150k edges — use max_edges to limit response size.
    For large models, prefer /gem/query + /gem/gene/{id} instead.
    """
    model, _ = _get_model(backbone)
    return build_gem_graph(model, max_edges=max_edges)
