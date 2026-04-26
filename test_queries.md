# CRYO Test Queries

Difficulty-graded test queries. Run each and check: tool chain, content quality, charts/diagrams/tables rendered.

## Status: [ ] untested [~] partial [x] working

---

## Tier 1: Single Tool Queries

- [ ] `/protein TP53`
- [ ] `/drug temozolomide`
- [ ] `/variant rs28934578`
- [ ] `/vep 17:7675088:C:T`
- [ ] `/targets Alzheimer's disease`
- [ ] `/structure 1TUP`
- [ ] `/pubmed CRISPR base editing 2025`

## Tier 2: Multi-Tool Chain

- [ ] `What is the clinical significance of BRCA1 c.5266dupC and what protein domain does it affect?`
- [ ] `Find recent papers on CAR-T therapy for solid tumors and cite them in APA`
- [ ] `Compare osimertinib and erlotinib for EGFR-mutant NSCLC`
- [ ] `Look up KRAS G12C, find approved drugs targeting it, and check clinical trial outcomes`

## Tier 3: Reports (check for :::chart, :::diagram, :::callout, tables)

- [ ] `/report EGFR mutations in lung cancer: TKI generations, resistance mechanisms, and clinical outcomes`
- [ ] `/report TP53 mutations across cancer types: frequency, prognostic impact, and emerging therapies`
- [ ] `/report CRISPR-Cas9 gene therapy: clinical trials, base editing breakthroughs, and safety data from 2024-2026`
- [ ] `/report Drug repurposing for Alzheimer disease: GLP-1 agonists, metformin, and clinical evidence`
- [ ] `/report HER2-positive breast cancer: trastuzumab to antibody-drug conjugates, T-DXd revolution`
- [ ] `/report Immunotherapy biomarkers TMB and MSI: tissue-agnostic approvals, clinical utility, and limitations`
- [ ] `/report CAR-T cell therapy: from hematological malignancies to solid tumors, challenges and 2025-2026 breakthroughs`

## Tier 4: Hot Topics 2025-2026 (complex, multi-source)

- [ ] `/report Personalized neoantigen cancer vaccines: clinical trial results, mRNA platforms, and combination with checkpoint inhibitors`
- [ ] `/report CRISPR base editing and prime editing: first-in-human trials, glycogen storage disease, sickle cell disease cure data`
- [ ] `/report GLP-1 receptor agonists beyond diabetes: Alzheimer neuroprotection, cancer risk reduction, cardiovascular outcomes`
- [ ] `/report Liquid biopsy in oncology: ctDNA for minimal residual disease detection, treatment monitoring, and early cancer screening`
- [ ] `/report KRAS G12C inhibitors: sotorasib vs adagrasib, resistance mechanisms, combination strategies in NSCLC and CRC`
- [ ] `/report Antibody-drug conjugates (ADCs) revolution: trastuzumab deruxtecan, sacituzumab govitecan, payload-linker innovations`
- [ ] `/report Tumor microenvironment reprogramming: turning cold tumors hot, myeloid cell targeting, and next-gen immunotherapy`
- [ ] `/report AI and machine learning in drug discovery: AlphaFold impact, de novo drug design, virtual screening at scale`
- [ ] `/report Epigenetic therapies in cancer: DNMT inhibitors, EZH2 inhibitors, BET bromodomain inhibitors, and clinical trials`
- [ ] `/report Single-cell multi-omics in cancer research: scRNA-seq, spatial transcriptomics, and tumor heterogeneity insights`

## Tier 5: Edge Cases

- [ ] `/report` (empty — should ask for topic)
- [ ] `/protein NOTAREALGENE` (graceful error)
- [ ] `What is quantum computing?` (off-topic — should answer without bio tools)
- [ ] `/variant rs9999999999999` (non-existent — should report no data)
- [ ] `/digital_twin` (empty — should ask for or fail clearly on missing drug input)
- [ ] `/digital_twin unknown_compound_xyz` (should run and report no meaningful effect rather than crash)

## Digital Twin Checks

### Slash commands (all work in chat AND workspace nodes)
- [ ] Slash menu shows `/digital_twin` and `/simulate`
- [ ] `/digital_twin glucose_inhibitor` completes — shows effects on MAR09034
- [ ] `/digital_twin atp_synthase_inhibitor` completes — shows ATP synthase effects
- [ ] `/digital_twin imatinib --cell_line MCF7` — ChEMBL finds ABL1/KIT/PDGFRA, GPR scaling applied (1200+ reactions constrained), biomass ~8 not 62
- [ ] `/simulate metformin --cell_line HeLa` — DGIdb lookup, GPR scaling for HeLa
- [ ] `/digital_twin 5-fluorouracil --cell_line HCT116` — metabolic drug (TYMS), should show real flux changes
- [ ] `/digital_twin methotrexate --cell_line A549` — metabolic drug (DHFR), should show flux changes
- [ ] `/digital_twin unknown_compound_xyz` — no crash, honest "no target mapping" note
- [ ] `/digital_twin` (empty) — fails gracefully
- [ ] `/digital_twin placebo` — runs, reports no effects

### What to check in each digital twin response
- [ ] Drug target section (gene names, source: chembl/dgidb)
- [ ] Cell line context (media preset used, GPR scaling status)
- [ ] Biomass flux values (personalized model baseline ≠ 62.43 when GPR applied)
- [ ] Top 10 flux shifts table (reaction IDs + delta values)
- [ ] GDSC validation section (IC50 if data available, or "no data" statement)
- [ ] Report link (HTML) + Plot link (PNG)
- [ ] ### References section with DOI links (always present)
- [ ] Disclaimer "please cross-check" appears when citations empty

### Data-dependent features (require setup)
- [ ] CCLE GPR scaling: requires `/cryo-data/ccle/ccle_expression_human1.parquet` — run `scripts/preprocess_ccle.py`
- [ ] GDSC IC50 validation: requires `/cryo-data/gdsc/gdsc2_sensitivity.csv` — run `scripts/setup_digital_twin.py`

### Best drugs to test (metabolic enzyme targets — show real effects)
| Drug | Target gene | Why it works |
|------|------------|--------------|
| `metformin` | MT-ND1 (Complex I) | Targets mitochondrial metabolism |
| `5-fluorouracil` | TYMS | Thymidylate synthase — in metabolic model |
| `methotrexate` | DHFR | Dihydrofolate reductase — in metabolic model |
| `2-deoxyglucose` | HK1/HK2 | Hexokinase — glycolysis |
| `glucose_inhibitor` | MAR09034 | Hardcoded: glucose exchange |
| `atp_synthase_inhibitor` | MAR04137 | Hardcoded: ATP synthase |

### Why TKIs (imatinib, erlotinib, etc.) show 0% biomass change
Kinase inhibitors target **signaling proteins** (ABL1, EGFR, PDGFRA) that are NOT encoded in genome-scale metabolic models. Human1 only models metabolic enzymes (transferases, oxidoreductases, transporters). TKIs still get ChEMBL target annotation and GPR scaling is still applied, but no direct reaction inhibition is possible.

## What to Check in Each Report

- [ ] Cover page renders with title, date, report ID
- [ ] Sidebar TOC with clickable links
- [ ] Search bar works
- [ ] Dark/light toggle works
- [ ] :::chart blocks render as interactive Plotly charts
- [ ] :::diagram blocks render as Mermaid flowcharts
- [ ] :::callout blocks render as colored info/warning/success boxes
- [ ] :::progress blocks render as comparison bars
- [ ] :::timeline blocks render as chronological timelines
- [ ] Markdown tables render with sortable headers
- [ ] **Bold** text renders properly (not as asterisks or garbled)
- [ ] Citations section with numbered references and DOI links
- [ ] Data sources badges at bottom
- [ ] Print button works (Cmd+P produces clean output)
