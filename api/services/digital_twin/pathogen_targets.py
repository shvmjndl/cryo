"""
Organism-specific drug → gene → reaction target mappings for pathogen and microbial models.

These supplement ChEMBL/DGIdb (which cover human drug targets well but are sparse for
microbial organisms) with curated, literature-validated antibiotic and antifungal targets.

Sources:
  E. coli targets: iJO1366 supplementary (Orth et al. 2011, Mol Syst Biol)
                   KEGG Pathway eco00790 (folate), eco00790 (cell wall)
                   Baba et al. 2006 (Keio collection essential genes)
  Yeast targets:   Saccharomyces Genome Database (SGD)
                   Parsons et al. 2004 (genome-wide chemical genomics)

Reaction IDs use BiGG namespace (iJO1366) and Yeast8 r_XXXX namespace.
"""
from __future__ import annotations


# ── E. coli (iJO1366) ──────────────────────────────────────────────────────────
# Key: lowercased drug name or common alias
# mechanism: human-readable mechanism of action
# gene: primary target gene (b-number or gene name)
# reactions: BiGG reaction IDs in iJO1366 that are directly inhibited
# note: scientific context / caveat

ECOLI_DRUG_TARGETS: dict[str, dict] = {
    # Folate pathway inhibitors
    "trimethoprim": {
        "gene": "folA",
        "gene_ids": ["b0048"],
        "reactions": ["DHFR"],  # iJO1366 has DHFR (not DHFR2); TMDS is downstream
        "mechanism": "Dihydrofolate reductase (DHFR) inhibitor — blocks tetrahydrofolate synthesis",
        "class": "antifolate",
        "note": "Highly selective for bacterial DHFR (10,000× lower Ki than mammalian).",
    },
    "methotrexate": {
        "gene": "folA",
        "gene_ids": ["b0048"],
        "reactions": ["DHFR"],
        "mechanism": "Dihydrofolate reductase inhibitor (folate analogue)",
        "class": "antifolate",
    },
    "sulfamethoxazole": {
        "gene": "folP",
        "gene_ids": ["b0290"],
        "reactions": ["DHPS2"],  # iJO1366 uses DHPS2 (not DHPS)
        "mechanism": "Dihydropteroate synthase (DHPS) inhibitor — blocks folate synthesis",
        "class": "sulfonamide",
    },
    "sulfanilamide": {
        "gene": "folP",
        "gene_ids": ["b0290"],
        "reactions": ["DHPS2"],
        "mechanism": "DHPS competitive inhibitor (PABA analogue)",
        "class": "sulfonamide",
    },
    # Cell wall synthesis
    "fosfomycin": {
        "gene": "murA",
        "gene_ids": ["b0091"],
        "reactions": ["UAGCVT"],  # iJO1366: UDP-N-acetylglucosamine 1-carboxyvinyltransferase
        "mechanism": "MurA (UDP-N-acetylglucosamine enolpyruvyl transferase) covalent inhibitor",
        "class": "cell wall inhibitor",
        "note": "Inhibits first committed step of peptidoglycan synthesis.",
    },
    "d-cycloserine": {
        "gene": "alr",
        "gene_ids": ["b4053"],
        "reactions": ["ALATA_D", "ALATA_L"],
        "mechanism": "D-Ala racemase and D-Ala-D-Ala ligase inhibitor",
        "class": "cell wall inhibitor",
    },
    # Metabolic inhibitors (present in metabolic model)
    "isoniazid": {
        "gene": "fabI",
        "gene_ids": ["b1288"],
        "reactions": ["ECOAH1", "ACCOAL"],
        "mechanism": "Enoyl-ACP reductase (FabI) inhibitor — blocks fatty acid elongation",
        "class": "FAS-II inhibitor",
        "note": "Primary target is InhA in Mycobacterium; E. coli FabI is the closest homologue.",
    },
    "triclosan": {
        "gene": "fabI",
        "gene_ids": ["b1288"],
        "reactions": ["ECOAH1"],
        "mechanism": "FabI enoyl-ACP reductase inhibitor",
        "class": "FAS-II inhibitor",
    },
    "cerulenin": {
        "gene": "fabB",
        "gene_ids": ["b2323"],
        "reactions": ["3OAR40", "3OAR60", "3OAR80"],
        "mechanism": "β-ketoacyl-ACP synthase I/II (FabB/FabF) inhibitor",
        "class": "FAS-II inhibitor",
    },
    # Purine/pyrimidine synthesis
    "5-fluorouracil": {
        "gene": "thyA",
        "gene_ids": ["b2827"],
        "reactions": ["TMDS", "DTMPK"],
        "mechanism": "Thymidylate synthase inhibitor — blocks dTMP synthesis",
        "class": "pyrimidine antimetabolite",
    },
    "metronidazole": {
        "gene": "pfo",
        "gene_ids": [],
        "reactions": ["PFL", "FRD2", "FRD3"],
        "mechanism": "Prodrug activated by nitroreductases under anaerobic conditions → DNA strand breaks",
        "class": "nitroimidazole",
        "note": "Active only under anaerobic conditions; iJO1366 anaerobic reactions are the relevant target.",
    },
    # Amino acid biosynthesis
    "glyphosate": {
        "gene": "aroA",
        "gene_ids": ["b0754"],
        "reactions": ["DDPA", "PSCVT"],
        "mechanism": "5-enolpyruvylshikimate-3-phosphate (EPSP) synthase inhibitor",
        "class": "shikimate pathway inhibitor",
    },
    "serine_hydroxamate": {
        "gene": "serS",
        "gene_ids": ["b2386"],
        "reactions": ["SERAT", "SERt2r"],
        "mechanism": "Seryl-tRNA synthetase competitive inhibitor → serine starvation",
        "class": "aminoacyl-tRNA synthetase inhibitor",
    },
    # Energy metabolism
    "arsenate": {
        "gene": "multiple",
        "gene_ids": [],
        "reactions": ["PGK", "GAPD"],
        "mechanism": "Arsenate uncouples oxidative phosphorylation by substituting for phosphate in glycolysis (arsenolysis)",
        "class": "metabolic poison",
    },
    "glucose_inhibitor": {
        "gene": "ptsG",
        "gene_ids": ["b1101"],
        "reactions": ["GLCptspp", "GLCt2pp", "EX_glc__D_e"],
        "mechanism": "Glucose transport (PTS system) inhibitor",
        "class": "carbon source inhibitor",
    },
}


# ── Saccharomyces cerevisiae (Yeast8) ──────────────────────────────────────────
# Reaction IDs use Yeast8 r_XXXX namespace where known, else gene-only.

YEAST_DRUG_TARGETS: dict[str, dict] = {
    "fluconazole": {
        "gene": "ERG11",
        "gene_ids": ["YHR007C"],
        "reactions": ["r_0317"],  # cytochrome P450 lanosterol 14α-demethylase in Yeast8
        "mechanism": "Lanosterol 14α-demethylase (Erg11/CYP51) inhibitor — blocks ergosterol synthesis",
        "class": "azole antifungal",
        "note": "Ergosterol is the primary fungal membrane sterol (analogous to cholesterol in mammals).",
    },
    "itraconazole": {
        "gene": "ERG11",
        "gene_ids": ["YHR007C"],
        "reactions": ["r_0317"],
        "mechanism": "CYP51 (Erg11) inhibitor",
        "class": "azole antifungal",
    },
    "voriconazole": {
        "gene": "ERG11",
        "gene_ids": ["YHR007C"],
        "reactions": ["r_0317"],
        "mechanism": "CYP51 (Erg11) inhibitor — second-generation triazole",
        "class": "azole antifungal",
    },
    "amphotericin_b": {
        "gene": "ERG6",
        "gene_ids": ["YML008C"],
        "reactions": ["r_0555", "r_0562"],
        "mechanism": "Binds ergosterol → membrane pores → cell death",
        "class": "polyene antifungal",
    },
    "terbinafine": {
        "gene": "ERG1",
        "gene_ids": ["YGR175C"],
        "reactions": ["r_1011"],  # squalene epoxidase (NADP) in Yeast8
        "mechanism": "Squalene epoxidase (Erg1) inhibitor — squalene accumulates, ergosterol depleted",
        "class": "allylamine antifungal",
    },
    "cycloheximide": {
        "gene": "RPL28",
        "gene_ids": ["YGL103W"],
        "reactions": [],
        "mechanism": "Ribosomal protein L28 inhibitor → translational elongation block",
        "class": "protein synthesis inhibitor",
        "note": "RPL28 not encoded in metabolic model — biomass change expected to be 0%.",
    },
    "rapamycin": {
        "gene": "TOR1",
        "gene_ids": ["YJR066W"],
        "reactions": ["r_2111", "r_0466"],
        "mechanism": "FKBP12-rapamycin complex inhibits TOR kinase → autophagy, reduced ribosome biogenesis",
        "class": "mTOR inhibitor",
        "note": "TOR signaling connects to amino acid and nitrogen metabolism — indirect metabolic effects.",
    },
    "lovastatin": {
        "gene": "HMG1",
        "gene_ids": ["YML075C"],
        "reactions": ["r_0691"],
        "mechanism": "HMG-CoA reductase inhibitor — sterol synthesis",
        "class": "statin",
    },
    "5-fluorouracil": {
        "gene": "CDC21",
        "gene_ids": ["YOR074C"],
        "reactions": ["r_0539", "r_1912"],
        "mechanism": "Thymidylate synthase (Cdc21) inhibitor — dTMP synthesis block",
        "class": "pyrimidine antimetabolite",
    },
    "hydroxyurea": {
        "gene": "RNR1",
        "gene_ids": ["YER070W"],
        "reactions": ["r_0549"],
        "mechanism": "Ribonucleotide reductase inhibitor → dNTP depletion → replication stress",
        "class": "DNA synthesis inhibitor",
    },
    "glucose_inhibitor": {
        "gene": "HXT1",
        "gene_ids": ["YHR094C"],
        "reactions": ["r_1714", "r_2058"],
        "mechanism": "Glucose transporter inhibition — carbon source limitation",
        "class": "carbon source inhibitor",
    },
}


def lookup_pathogen_targets(organism: str, drug_name: str) -> dict | None:
    """
    Return target info dict for a known pathogen drug, or None if not found.

    Returns same structure as drug_lookup.resolve_drug_targets() for compatibility:
    {targets: [{gene_symbol, mechanism, source}], reaction_ids, citations}
    """
    drug_lower = drug_name.lower().replace("-", "_").replace(" ", "_")

    table: dict[str, dict] | None = None
    if organism == "ecoli":
        table = ECOLI_DRUG_TARGETS
    elif organism == "yeast":
        table = YEAST_DRUG_TARGETS

    if table is None:
        return None

    entry = table.get(drug_lower)
    if not entry:
        # Fuzzy match: check if any key is a substring
        for key, val in table.items():
            if key in drug_lower or drug_lower in key:
                entry = val
                break

    if not entry:
        return None

    return {
        "targets": [
            {
                "gene_symbol": entry["gene"],
                "mechanism": entry.get("mechanism", ""),
                "source": "pathogen_targets_db",
                "gene_ids": entry.get("gene_ids", []),
                "class": entry.get("class", ""),
            }
        ],
        "reaction_ids": entry.get("reactions", []),
        "source": "pathogen_targets_db",
        "organism": organism,
        "note": entry.get("note", ""),
        "citations": [
            {
                "authors": "Orth JD et al.",
                "year": "2011",
                "title": "A comprehensive genome-scale reconstruction of Escherichia coli metabolism — 2011",
                "journal": "Molecular Systems Biology",
                "doi": "10.1038/msb.2011.65",
                "url": "https://doi.org/10.1038/msb.2011.65",
                "note": "iJO1366 E. coli metabolic model",
            },
        ] if organism == "ecoli" else [
            {
                "authors": "Lu H et al.",
                "year": "2019",
                "title": "A consensus S. cerevisiae metabolic model Yeast8 and its ecosystem for comprehensively probing cellular metabolism",
                "journal": "Nature Communications",
                "doi": "10.1038/s41467-019-11581-3",
                "url": "https://doi.org/10.1038/s41467-019-11581-3",
                "note": "Yeast8 S. cerevisiae metabolic model",
            },
        ],
    }
