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
- [ ] `/digital_twin glucose_inhibitor`
- [ ] `/digital_twin atp_synthase_inhibitor`
- [ ] `/digital_twin glucose_inhibitor_atp_synthase_inhibitor`
- [ ] `/digital_twin placebo`

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

- [ ] Slash menu shows `/digital_twin`
- [ ] `/digital_twin glucose_inhibitor` completes without backend error
- [ ] `/digital_twin atp_synthase_inhibitor` completes without backend error
- [ ] Combined inhibitor query returns a report and plot link
- [ ] Report link opens successfully
- [ ] Plot PNG link opens successfully
- [ ] Response includes initial biomass flux
- [ ] Response includes drug biomass flux
- [ ] Response lists applied reaction-level drug effects
- [ ] Response handles no-effect inputs like `placebo` cleanly
- [ ] No auth error or missing-tool error appears in the chat response

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
