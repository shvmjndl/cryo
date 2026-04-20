"""CRYO Genomic Variant Tools — ClinVar and Ensembl VEP via free public APIs."""

import json
import logging
import re

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.variant")

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ENSEMBL_BASE = "https://rest.ensembl.org"
TIMEOUT = 25


def _safe_get(url: str, params: dict | None = None, headers: dict | None = None) -> dict | str | None:
    try:
        h = {"Accept": "application/json", **(headers or {})}
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(url, params=params, headers=h)
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            return r.json() if "json" in ct else r.text
    except Exception as e:
        logger.error("HTTP GET failed: %s — %s", url, e)
        return {"error": str(e)}


# ─── ClinVar Lookup ──────────────────────────────────────────

def _clinvar_lookup(args: dict, **kw) -> str:
    query = args.get("query", "").strip()
    max_results = min(int(args.get("max_results", 10)), 20)

    if not query:
        return json.dumps({"error": "query is required"})

    logger.info("ClinVar lookup: query=%r", query)

    # Search ClinVar via NCBI E-utilities
    search_params = {
        "db": "clinvar",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }
    search_result = _safe_get(f"{NCBI_BASE}/esearch.fcgi", params=search_params)

    if isinstance(search_result, str):
        try:
            search_result = json.loads(search_result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse ClinVar search"})

    if "error" in (search_result if isinstance(search_result, dict) else {}):
        return json.dumps(search_result)

    id_list = search_result.get("esearchresult", {}).get("idlist", [])
    total = search_result.get("esearchresult", {}).get("count", "0")

    if not id_list:
        return json.dumps({"query": query, "total": 0, "variants": [], "message": f"No ClinVar results for '{query}'"})

    # Fetch summaries
    summary_params = {
        "db": "clinvar",
        "id": ",".join(id_list),
        "retmode": "json",
    }
    summary = _safe_get(f"{NCBI_BASE}/esummary.fcgi", params=summary_params)

    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse ClinVar summary"})

    variants = []
    result_data = summary.get("result", {})
    for vid in id_list:
        info = result_data.get(vid, {})
        if not isinstance(info, dict):
            continue

        # Extract clinical significance
        clin_sig_list = info.get("clinical_significance", {})
        if isinstance(clin_sig_list, dict):
            significance = clin_sig_list.get("description", "")
        else:
            significance = str(clin_sig_list)

        # Extract genes
        genes = info.get("genes", [])
        gene_names = [g.get("symbol", "") for g in genes] if isinstance(genes, list) else []

        # Extract conditions
        trait_set = info.get("trait_set", [])
        conditions = []
        if isinstance(trait_set, list):
            for ts in trait_set:
                traits = ts.get("trait_name", "") if isinstance(ts, dict) else str(ts)
                if traits:
                    conditions.append(traits)

        variants.append({
            "clinvar_id": vid,
            "title": info.get("title", ""),
            "gene_symbols": gene_names,
            "clinical_significance": significance,
            "review_status": info.get("clinical_significance", {}).get("review_status", "") if isinstance(info.get("clinical_significance"), dict) else "",
            "conditions": conditions[:5],
            "variation_type": info.get("variation_set", [{}])[0].get("variation_type", "") if info.get("variation_set") else "",
            "url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{vid}/",
        })

    return json.dumps({
        "query": query,
        "total": int(total),
        "returned": len(variants),
        "variants": variants,
    })


CLINVAR_SCHEMA = {
    "name": "clinvar_lookup",
    "description": "Search ClinVar for clinical significance of genetic variants. Returns pathogenicity classifications, associated conditions, and review status. Use for any variant interpretation query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Variant identifier (rsID like rs28934578, gene name like BRCA1, or HGVS notation like NM_000546.6:c.215C>G)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results (1-20, default 10)"
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="clinvar_lookup",
    toolset="cryo_variant",
    schema=CLINVAR_SCHEMA,
    handler=_clinvar_lookup,
    check_fn=lambda: True,
    emoji="🧪",
)


# ─── Ensembl VEP (Variant Effect Predictor) ──────────────────

def _ensembl_vep(args: dict, **kw) -> str:
    variant = args.get("variant", "").strip()

    if not variant:
        return json.dumps({"error": "variant is required"})

    logger.info("Ensembl VEP: variant=%r", variant)

    # Determine input format
    # rsID: rs28934578
    # HGVS: ENST00000269305.9:c.215C>G
    # Region: 17:7675088:7675088:C/T or 17:7675088:C:T

    if variant.startswith("rs"):
        url = f"{ENSEMBL_BASE}/vep/human/id/{variant}"
    elif ":" in variant and "/" not in variant:
        # Try to parse as chr:pos:ref:alt
        parts = variant.replace("-", ":").split(":")
        if len(parts) >= 4:
            chrom, pos, ref, alt = parts[0], parts[1], parts[2], parts[3]
            region = f"{chrom}:{pos}:{pos}"
            allele = f"{ref}/{alt}" if len(ref) == 1 and len(alt) == 1 else alt
            url = f"{ENSEMBL_BASE}/vep/human/region/{region}/{allele}"
        elif len(parts) == 3:
            # chr:pos:allele
            url = f"{ENSEMBL_BASE}/vep/human/region/{parts[0]}:{parts[1]}:{parts[1]}/{parts[2]}"
        else:
            return json.dumps({"error": f"Cannot parse variant format: {variant}. Use rsID, chr:pos:ref:alt, or HGVS."})
    else:
        # Try HGVS
        url = f"{ENSEMBL_BASE}/vep/human/hgvs/{variant}"

    headers = {"Content-Type": "application/json"}
    data = _safe_get(url, headers=headers)

    if not data:
        return json.dumps({"error": f"No VEP results for '{variant}'"})

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse VEP response"})

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    # Parse VEP results
    results = data if isinstance(data, list) else [data]
    predictions = []

    for result in results:
        for tc in result.get("transcript_consequences", [])[:10]:
            pred = {
                "gene_symbol": tc.get("gene_symbol", ""),
                "gene_id": tc.get("gene_id", ""),
                "transcript_id": tc.get("transcript_id", ""),
                "consequence": ", ".join(tc.get("consequence_terms", [])),
                "impact": tc.get("impact", ""),
                "biotype": tc.get("biotype", ""),
                "amino_acids": tc.get("amino_acids", ""),
                "codons": tc.get("codons", ""),
                "protein_position": tc.get("protein_start", ""),
                "sift": f"{tc.get('sift_prediction', '')} ({tc.get('sift_score', '')})" if tc.get("sift_prediction") else "",
                "polyphen": f"{tc.get('polyphen_prediction', '')} ({tc.get('polyphen_score', '')})" if tc.get("polyphen_prediction") else "",
            }
            predictions.append(pred)

        # Regulatory consequences
        for rc in result.get("regulatory_feature_consequences", [])[:3]:
            predictions.append({
                "type": "regulatory",
                "consequence": ", ".join(rc.get("consequence_terms", [])),
                "impact": rc.get("impact", ""),
                "biotype": rc.get("biotype", ""),
                "regulatory_feature_id": rc.get("regulatory_feature_id", ""),
            })

    return json.dumps({
        "variant": variant,
        "most_severe": results[0].get("most_severe_consequence", "") if results else "",
        "allele": results[0].get("allele_string", "") if results else "",
        "location": f"{results[0].get('seq_region_name', '')}:{results[0].get('start', '')}" if results else "",
        "predictions": predictions,
    })


VEP_SCHEMA = {
    "name": "ensembl_vep",
    "description": "Predict functional effects of a genetic variant using Ensembl Variant Effect Predictor (VEP). Returns consequence types, impact severity, SIFT/PolyPhen scores, and affected transcripts.",
    "parameters": {
        "type": "object",
        "properties": {
            "variant": {
                "type": "string",
                "description": "Variant in any format: rsID (rs28934578), chr:pos:ref:alt (17:7675088:C:T), or HGVS notation"
            },
        },
        "required": ["variant"],
    },
}

registry.register(
    name="ensembl_vep",
    toolset="cryo_variant",
    schema=VEP_SCHEMA,
    handler=_ensembl_vep,
    check_fn=lambda: True,
    emoji="🔎",
)
