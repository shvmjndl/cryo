"""
GEM-as-graph: extract, query, and traverse the metabolite–reaction–gene tripartite graph
from any COBRApy model.

The graph has three node types:
  M — metabolite  (id, name, formula, compartment)
  R — reaction    (id, name, subsystem, GPR, bounds)
  G — gene        (id, name)

And three edge types:
  M → R  (reactant, stoichiometry < 0)
  R → M  (product,  stoichiometry > 0)
  G → R  (catalyzes, from GPR)

All operations are read-only on the passed model.
"""
from __future__ import annotations

import re
from typing import Any

import cobra


# ── Node / edge builders ───────────────────────────────────────────────────────

def _met_node(met: cobra.Metabolite) -> dict:
    return {
        "id": met.id,
        "type": "metabolite",
        "name": met.name or met.id,
        "formula": met.formula or "",
        "charge": met.charge,
        "compartment": met.compartment or "",
    }


def _rxn_node(rxn: cobra.Reaction) -> dict:
    return {
        "id": rxn.id,
        "type": "reaction",
        "name": rxn.name or rxn.id,
        "subsystem": rxn.subsystem or "",
        "gpr": rxn.gene_reaction_rule or "",
        "lb": rxn.lower_bound,
        "ub": rxn.upper_bound,
        "reversible": rxn.reversibility,
        "gene_count": len(rxn.genes),
    }


def _gene_node(gene: cobra.Gene) -> dict:
    return {
        "id": gene.id,
        "type": "gene",
        "name": gene.name or gene.id,
        "reaction_count": len(gene.reactions),
    }


# ── Full graph export (for small models or API pagination) ─────────────────────

def build_gem_graph(model: cobra.Model, max_edges: int = 50_000) -> dict[str, Any]:
    """
    Extract the complete tripartite graph from a COBRApy model.

    Returns a dict suitable for JSON serialisation:
    {
        nodes: {metabolites: [...], reactions: [...], genes: [...]},
        edges: [{source, target, type, stoich?}, ...],
        stats: {metabolites, reactions, genes, edges}
    }

    max_edges limits payload size for large models (Human1 has ~150k edges).
    """
    met_nodes = [_met_node(m) for m in model.metabolites]
    rxn_nodes = [_rxn_node(r) for r in model.reactions]
    gene_nodes = [_gene_node(g) for g in model.genes]

    edges: list[dict] = []
    for rxn in model.reactions:
        for met, stoich in rxn.metabolites.items():
            if len(edges) >= max_edges:
                break
            if stoich < 0:
                edges.append({"source": met.id, "target": rxn.id, "type": "reactant", "stoich": round(stoich, 4)})
            else:
                edges.append({"source": rxn.id, "target": met.id, "type": "product", "stoich": round(stoich, 4)})
        for gene in rxn.genes:
            if len(edges) >= max_edges:
                break
            edges.append({"source": gene.id, "target": rxn.id, "type": "catalyzes"})

    return {
        "nodes": {
            "metabolites": met_nodes,
            "reactions": rxn_nodes,
            "genes": gene_nodes,
        },
        "edges": edges,
        "stats": {
            "metabolites": len(met_nodes),
            "reactions": len(rxn_nodes),
            "genes": len(gene_nodes),
            "edges": len(edges),
            "edges_truncated": len(edges) >= max_edges,
        },
    }


def get_model_stats(model: cobra.Model) -> dict[str, Any]:
    """Lightweight stats — no edge traversal."""
    subsystems: set[str] = set()
    compartments: set[str] = set()
    for rxn in model.reactions:
        if rxn.subsystem:
            subsystems.add(rxn.subsystem)
    for met in model.metabolites:
        if met.compartment:
            compartments.add(met.compartment)

    return {
        "model_id": model.id or "unknown",
        "reactions": len(model.reactions),
        "metabolites": len(model.metabolites),
        "genes": len(model.genes),
        "subsystems": len(subsystems),
        "compartments": sorted(compartments),
        "exchanges": len(model.exchanges),
        "objective": str(model.objective.expression)[:120],
    }


# ── Search / query ─────────────────────────────────────────────────────────────

def query_gem(model: cobra.Model, q: str, limit: int = 25) -> dict[str, Any]:
    """
    Full-text search across metabolites, reactions, and genes.
    Matches on id, name, formula (metabolites), subsystem (reactions).
    """
    ql = q.lower().strip()
    results: dict[str, list] = {"metabolites": [], "reactions": [], "genes": []}

    for met in model.metabolites:
        if ql in met.id.lower() or ql in (met.name or "").lower() or ql in (met.formula or "").lower():
            results["metabolites"].append(_met_node(met))
            if len(results["metabolites"]) >= limit:
                break

    for rxn in model.reactions:
        if (ql in rxn.id.lower() or ql in (rxn.name or "").lower()
                or ql in (rxn.subsystem or "").lower()
                or ql in (rxn.gene_reaction_rule or "").lower()):
            node = _rxn_node(rxn)
            # Add metabolite IDs for context
            node["metabolite_ids"] = [m.id for m in rxn.metabolites]
            results["reactions"].append(node)
            if len(results["reactions"]) >= limit:
                break

    for gene in model.genes:
        if ql in gene.id.lower() or ql in (gene.name or "").lower():
            node = _gene_node(gene)
            node["reaction_ids"] = [r.id for r in gene.reactions]
            results["genes"].append(node)
            if len(results["genes"]) >= limit:
                break

    results["total_hits"] = (
        len(results["metabolites"]) + len(results["reactions"]) + len(results["genes"])
    )
    return results


# ── Neighbourhood subgraphs ────────────────────────────────────────────────────

def get_gene_neighborhood(model: cobra.Model, gene_id: str, depth: int = 1) -> dict[str, Any]:
    """
    Return all reactions catalysed by a gene and their metabolites.

    depth=1 → direct reactions + their metabolites
    depth=2 → also add reactions that consume/produce those metabolites (expensive)
    """
    try:
        gene = model.genes.get_by_id(gene_id)
    except KeyError:
        return {"error": f"Gene '{gene_id}' not found in model"}

    reactions = []
    metabolite_ids: set[str] = set()
    for rxn in gene.reactions:
        node = _rxn_node(rxn)
        met_list = []
        for met, stoich in rxn.metabolites.items():
            met_list.append({"id": met.id, "name": met.name, "stoich": round(stoich, 4),
                             "compartment": met.compartment})
            metabolite_ids.add(met.id)
        node["metabolites"] = met_list
        reactions.append(node)

    result: dict[str, Any] = {
        "gene": _gene_node(gene),
        "reactions": reactions,
        "metabolite_count": len(metabolite_ids),
    }

    if depth >= 2:
        # Find reactions that share metabolites with this gene's reactions
        connected_reactions = []
        seen_rxn_ids = {r["id"] for r in reactions}
        for met in model.metabolites:
            if met.id not in metabolite_ids:
                continue
            for rxn in met.reactions:
                if rxn.id not in seen_rxn_ids:
                    connected_reactions.append(_rxn_node(rxn))
                    seen_rxn_ids.add(rxn.id)
        result["connected_reactions"] = connected_reactions[:50]

    return result


def get_reaction_detail(model: cobra.Model, reaction_id: str) -> dict[str, Any]:
    """Full detail for one reaction: metabolites, genes, flux bounds."""
    try:
        rxn = model.reactions.get_by_id(reaction_id)
    except KeyError:
        return {"error": f"Reaction '{reaction_id}' not found in model"}

    met_list = []
    for met, stoich in rxn.metabolites.items():
        met_list.append({
            "id": met.id,
            "name": met.name or met.id,
            "formula": met.formula or "",
            "stoich": round(stoich, 4),
            "compartment": met.compartment or "",
            "role": "reactant" if stoich < 0 else "product",
        })

    gene_list = [{"id": g.id, "name": g.name or g.id} for g in rxn.genes]

    return {
        "reaction": _rxn_node(rxn),
        "equation": rxn.reaction,
        "metabolites": met_list,
        "genes": gene_list,
    }


def get_metabolite_detail(model: cobra.Model, metabolite_id: str) -> dict[str, Any]:
    """Full detail for one metabolite: producing and consuming reactions."""
    try:
        met = model.metabolites.get_by_id(metabolite_id)
    except KeyError:
        return {"error": f"Metabolite '{metabolite_id}' not found in model"}

    producing = []
    consuming = []
    for rxn in met.reactions:
        stoich = rxn.metabolites[met]
        entry = {**_rxn_node(rxn), "stoich": round(stoich, 4)}
        if stoich > 0:
            producing.append(entry)
        else:
            consuming.append(entry)

    return {
        "metabolite": _met_node(met),
        "producing_reactions": producing[:20],
        "consuming_reactions": consuming[:20],
        "reaction_count": len(met.reactions),
    }


def get_subsystem_reactions(model: cobra.Model, subsystem: str, limit: int = 50) -> dict[str, Any]:
    """Return reactions belonging to a metabolic subsystem/pathway."""
    sl = subsystem.lower()
    matching = []
    for rxn in model.reactions:
        if sl in (rxn.subsystem or "").lower():
            node = _rxn_node(rxn)
            node["gene_ids"] = [g.id for g in rxn.genes]
            matching.append(node)
            if len(matching) >= limit:
                break

    # List unique subsystems for autocomplete
    all_subsystems = sorted({rxn.subsystem for rxn in model.reactions if rxn.subsystem})

    return {
        "subsystem_query": subsystem,
        "reactions": matching,
        "total_found": len(matching),
        "truncated": len(matching) >= limit,
        "all_subsystems_count": len(all_subsystems),
    }


def compare_gene_sets(
    model: cobra.Model,
    gene_ids_a: list[str],
    gene_ids_b: list[str],
) -> dict[str, Any]:
    """
    Compare two gene sets (e.g. drug A targets vs drug B targets) at the reaction level.
    Returns shared reactions, reactions unique to A, reactions unique to B.
    """
    def reactions_for_genes(ids: list[str]) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for gid in ids:
            try:
                gene = model.genes.get_by_id(gid)
                result[gid] = {r.id for r in gene.reactions}
            except KeyError:
                result[gid] = set()
        return result

    rxns_a = reactions_for_genes(gene_ids_a)
    rxns_b = reactions_for_genes(gene_ids_b)
    all_a: set[str] = set().union(*rxns_a.values()) if rxns_a else set()
    all_b: set[str] = set().union(*rxns_b.values()) if rxns_b else set()

    return {
        "shared_reactions": sorted(all_a & all_b),
        "unique_to_a": sorted(all_a - all_b),
        "unique_to_b": sorted(all_b - all_a),
        "total_a_reactions": len(all_a),
        "total_b_reactions": len(all_b),
    }
