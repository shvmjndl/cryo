"""
Drug-target resolution via ChEMBL REST API, DGIdb REST API, and local SQLite cache.
Resolves drug name → gene targets → Human1 reaction IDs (read-only model query).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cobra
import httpx

logger = logging.getLogger("cryo.drug_lookup")

_CACHE_DIR = Path(os.getenv("CRYO_DATA_DIR", "/cryo-data")) / "cache"
_DB_PATH = _CACHE_DIR / "drug_targets.db"
_CACHE_TTL_DAYS = 7

_CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_DGIDB_GQL = "https://dgidb.org/api/graphql"


# ─── Schema ───────────────────────────────────────────────────────────────────

def _init_db() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drug_targets (
            drug_name   TEXT NOT NULL,
            gene_symbol TEXT NOT NULL,
            source      TEXT NOT NULL,
            mechanism   TEXT,
            chembl_id   TEXT,
            fetched_at  TEXT NOT NULL,
            PRIMARY KEY (drug_name, gene_symbol, source)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drug_reactions (
            drug_name   TEXT NOT NULL,
            reaction_id TEXT NOT NULL,
            gene_symbol TEXT NOT NULL,
            backbone    TEXT NOT NULL DEFAULT 'human1',
            fetched_at  TEXT NOT NULL,
            PRIMARY KEY (drug_name, reaction_id, backbone)
        )
    """)
    conn.commit()
    return conn


# ─── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_is_fresh(fetched_at: str) -> bool:
    try:
        ts = datetime.fromisoformat(fetched_at)
        return datetime.utcnow() - ts < timedelta(days=_CACHE_TTL_DAYS)
    except Exception:
        return False


def _load_cached_targets(drug_name: str) -> list[dict] | None:
    try:
        conn = _init_db()
        rows = conn.execute(
            "SELECT gene_symbol, source, mechanism, chembl_id, fetched_at FROM drug_targets WHERE drug_name=?",
            (drug_name.lower(),)
        ).fetchall()
        conn.close()
        if not rows:
            return None
        if not _cache_is_fresh(rows[0][4]):
            return None
        return [{"gene_symbol": r[0], "source": r[1], "mechanism": r[2], "chembl_id": r[3]} for r in rows]
    except Exception as e:
        logger.debug("Cache read failed: %s", e)
        return None


def _save_targets(drug_name: str, targets: list[dict]) -> None:
    try:
        conn = _init_db()
        now = datetime.utcnow().isoformat()
        for t in targets:
            conn.execute(
                "INSERT OR REPLACE INTO drug_targets VALUES (?,?,?,?,?,?)",
                (drug_name.lower(), t["gene_symbol"], t["source"],
                 t.get("mechanism"), t.get("chembl_id"), now)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Cache write failed: %s", e)


def _load_cached_reactions(drug_name: str, backbone: str = "human1") -> list[str] | None:
    try:
        conn = _init_db()
        rows = conn.execute(
            "SELECT reaction_id, fetched_at FROM drug_reactions WHERE drug_name=? AND backbone=?",
            (drug_name.lower(), backbone)
        ).fetchall()
        conn.close()
        if not rows:
            return None
        if not _cache_is_fresh(rows[0][1]):
            return None
        return [r[0] for r in rows]
    except Exception as e:
        logger.debug("Reaction cache read failed: %s", e)
        return None


def _save_reactions(drug_name: str, reaction_ids: list[str], gene_symbol: str, backbone: str = "human1") -> None:
    try:
        conn = _init_db()
        now = datetime.utcnow().isoformat()
        for rxn_id in reaction_ids:
            conn.execute(
                "INSERT OR REPLACE INTO drug_reactions VALUES (?,?,?,?,?)",
                (drug_name.lower(), rxn_id, gene_symbol, backbone, now)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Reaction cache write failed: %s", e)


# ─── ChEMBL lookup ────────────────────────────────────────────────────────────

def _chembl_lookup(drug_name: str) -> list[dict]:
    """Query ChEMBL: drug_name → gene targets with mechanism of action.

    ChEMBL stores mechanism data on the approved salt form, not always the base
    molecule. So we search all returned molecules and pick the first that has
    mechanism entries (usually the approved drug salt, e.g. imatinib mesylate).
    """
    results = []
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            # Step 1: search by drug name — get all variants
            r = client.get(f"{_CHEMBL_BASE}/molecule/search",
                           params={"q": drug_name, "format": "json", "limit": 10})
            if not r.is_success:
                return results
            molecules = r.json().get("molecules", [])
            if not molecules:
                return results

            # Step 2: find first molecule that has mechanism data
            # (mechanism is often on the approved salt, not the parent free base)
            mechanisms: list[dict] = []
            chembl_id = ""
            for mol in molecules:
                cid = mol.get("molecule_chembl_id", "")
                if not cid:
                    continue
                r2 = client.get(f"{_CHEMBL_BASE}/mechanism",
                                params={"molecule_chembl_id": cid, "format": "json", "limit": 50})
                if not r2.is_success:
                    continue
                mechs = r2.json().get("mechanisms", [])
                if mechs:
                    mechanisms = mechs
                    chembl_id = cid
                    logger.info("ChEMBL mechanisms found on %s (%s): %d entries",
                                mol.get("pref_name"), cid, len(mechs))
                    break

            if not mechanisms:
                logger.info("ChEMBL: no mechanism data found for %r", drug_name)
                return results

            # Step 3: resolve each target → gene symbol
            seen_genes: set[str] = set()
            for mech in mechanisms:
                target_id = mech.get("target_chembl_id", "")
                mechanism_text = mech.get("mechanism_of_action", "")
                if not target_id:
                    continue
                r3 = client.get(f"{_CHEMBL_BASE}/target/{target_id}",
                                params={"format": "json"})
                if not r3.is_success:
                    continue
                components = r3.json().get("target_components", [])
                for comp in components:
                    for syn in comp.get("target_component_synonyms", []):
                        if syn.get("syn_type") == "GENE_SYMBOL":
                            gene = syn["component_synonym"]
                            if gene and gene not in seen_genes:
                                seen_genes.add(gene)
                                results.append({
                                    "gene_symbol": gene,
                                    "source": "chembl",
                                    "mechanism": mechanism_text,
                                    "chembl_id": chembl_id,
                                })

    except Exception as e:
        logger.warning("ChEMBL lookup failed for %r: %s", drug_name, e)

    return results


# ─── DGIdb lookup ─────────────────────────────────────────────────────────────

def _dgidb_lookup(drug_name: str) -> list[dict]:
    """Query DGIdb GraphQL API for drug-gene interactions.

    DGIdb v2 REST is deprecated (now returns HTML). Using GraphQL endpoint.
    """
    results = []
    query = """
    query DrugInteractions($name: String!) {
      drugs(names: [$name]) {
        nodes {
          name
          interactions {
            gene { name }
            interactionAttributes { name value }
          }
        }
      }
    }
    """
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            r = client.post(
                _DGIDB_GQL,
                json={"query": query, "variables": {"name": drug_name}},
                headers={"Content-Type": "application/json"},
            )
            if not r.is_success:
                logger.warning("DGIdb GraphQL returned %s for %r", r.status_code, drug_name)
                return results
            data = r.json()
            nodes = data.get("data", {}).get("drugs", {}).get("nodes", [])
            seen_genes: set[str] = set()
            for node in nodes:
                for interaction in node.get("interactions", []):
                    gene = (interaction.get("gene") or {}).get("name", "")
                    if not gene or gene in seen_genes:
                        continue
                    seen_genes.add(gene)
                    attrs = interaction.get("interactionAttributes", []) or []
                    mechanism = next(
                        (a["value"] for a in attrs if a.get("name") == "interaction_type"),
                        ""
                    )
                    results.append({
                        "gene_symbol": gene,
                        "source": "dgidb",
                        "mechanism": mechanism,
                        "chembl_id": None,
                    })
    except Exception as e:
        logger.warning("DGIdb lookup failed for %r: %s", drug_name, e)

    return results


# ─── Gene → Reaction mapping ───────────────────────────────────────────────────

def _gene_to_reactions(model: cobra.Model, gene_symbol: str) -> list[str]:
    """Map HGNC gene symbol to Human1 reaction IDs (read-only).

    Human1 stores gene IDs as Ensembl IDs (ENSG...) with empty gene.name.
    The HGNC symbol is in g.annotation['hgnc.symbol']. We search that first.
    """
    normalized = gene_symbol.upper().strip()

    # 1. HGNC symbol via annotation (Human1's primary lookup path)
    for g in model.genes:
        hgnc = (g.annotation or {}).get("hgnc.symbol", "")
        if hgnc and hgnc.upper() == normalized:
            return [rxn.id for rxn in g.reactions]

    # 2. Exact gene.id match (Ensembl or other direct ID)
    try:
        gene = model.genes.get_by_id(gene_symbol)
        return [rxn.id for rxn in gene.reactions]
    except KeyError:
        pass

    # 3. gene.name match (some models store HGNC name here)
    matches = [g for g in model.genes if (g.name or "").upper() == normalized]
    if matches:
        return [rxn.id for rxn in matches[0].reactions]

    # 4. Partial HGNC symbol match (e.g. "ABL" matches "ABL1")
    matches = [
        g for g in model.genes
        if normalized in (g.annotation or {}).get("hgnc.symbol", "").upper()
    ]
    if matches:
        return [rxn.id for rxn in matches[0].reactions]

    return []


# ─── Public API ───────────────────────────────────────────────────────────────

STANDARD_DRUG_CITATIONS = [
    {
        "title": "ChEMBL: a large-scale bioactivity database for drug discovery",
        "authors": "Gaulton A et al.",
        "year": 2012,
        "journal": "Nucleic Acids Research",
        "doi": "10.1093/nar/gkr777",
        "url": "https://doi.org/10.1093/nar/gkr777",
    },
    {
        "title": "DGIdb: mining the druggable genome",
        "authors": "Griffith M et al.",
        "year": 2013,
        "journal": "Nature Methods",
        "doi": "10.1038/nmeth.2689",
        "url": "https://doi.org/10.1038/nmeth.2689",
    },
]


def resolve_drug_targets(
    model: cobra.Model,
    drug_name: str,
    backbone: str = "human1",
) -> dict[str, Any]:
    """
    Resolve drug_name → gene targets → model reaction IDs.
    Uses SQLite cache (7-day TTL), then ChEMBL, then DGIdb.
    Model is used READ-ONLY (gene/reaction queries only).

    Returns:
        {
            "drug_name": str,
            "targets": [{"gene_symbol", "source", "mechanism", "chembl_id"}, ...],
            "reaction_ids": [str, ...],
            "citations": [...],
            "error": str | None,
        }
    """
    normalized = drug_name.lower().strip()
    result: dict[str, Any] = {
        "drug_name": drug_name,
        "targets": [],
        "reaction_ids": [],
        "citations": [],
        "error": None,
    }

    # 1. Try reaction cache
    cached_rxns = _load_cached_reactions(normalized, backbone)
    cached_targets = _load_cached_targets(normalized)
    if cached_rxns is not None and cached_targets is not None:
        result["targets"] = cached_targets
        result["reaction_ids"] = cached_rxns
        result["citations"] = STANDARD_DRUG_CITATIONS
        logger.info("Drug lookup cache hit: %s → %d reactions", drug_name, len(cached_rxns))
        return result

    # 2. ChEMBL lookup
    targets = _chembl_lookup(normalized)
    if not targets:
        # 3. DGIdb fallback
        targets = _dgidb_lookup(normalized)

    if not targets:
        result["error"] = f"No drug-target mapping found for {drug_name!r} in ChEMBL or DGIdb."
        logger.info("No targets found for drug: %s", drug_name)
        return result

    # 4. Map genes → reaction IDs
    all_reaction_ids: list[str] = []
    for target in targets:
        gene = target["gene_symbol"]
        rxn_ids = _gene_to_reactions(model, gene)
        all_reaction_ids.extend(rxn_ids)
        if rxn_ids:
            logger.info("Gene %s → %d Human1 reactions", gene, len(rxn_ids))
        _save_reactions(normalized, rxn_ids, gene, backbone)

    all_reaction_ids = list(dict.fromkeys(all_reaction_ids))  # deduplicate, preserve order

    # 5. Cache
    _save_targets(normalized, targets)

    result["targets"] = targets
    result["reaction_ids"] = all_reaction_ids
    result["citations"] = STANDARD_DRUG_CITATIONS
    logger.info("Drug lookup: %s → %d targets, %d reactions", drug_name, len(targets), len(all_reaction_ids))
    return result
