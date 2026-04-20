# CRYO Test Queries

Difficulty-graded test queries to validate agent tool chaining, accuracy, and output quality.

## Status Legend
- [ ] Not tested
- [~] Partial (tools fired but output incomplete)
- [x] Working

---

## Tier 1: Single Tool (should always work)

- [~] `/pubmed CRISPR-Cas9 gene therapy 2024`
  - Expected: pubmed_search → list of papers with titles, authors, PMIDs
  - Known issue: gemini-2.5-flash sometimes returns empty after tool call

- [ ] `/protein TP53`
  - Expected: uniprot_lookup → function, domains, GO terms, PDB structures

- [ ] `/drug temozolomide`
  - Expected: chembl_search → ChEMBL ID, phase, molecular weight, SMILES

- [ ] `/variant rs28934578`
  - Expected: clinvar_lookup → clinical significance, conditions, review status

- [ ] `/vep 17:7675088:C:T`
  - Expected: ensembl_vep → consequence, impact, SIFT/PolyPhen scores

- [ ] `/targets Alzheimer's disease`
  - Expected: opentargets_search → disease info, associated targets

- [ ] `/structure 1TUP`
  - Expected: pdb_search → PDB entry details for p53 DNA-binding domain

## Tier 2: Multi-Tool Chain (2-3 tools)

- [ ] `What is the clinical significance of the BRCA1 c.5266dupC variant and what protein domain does it affect?`
  - Expected: clinvar_lookup → uniprot_lookup → synthesized answer

- [ ] `Find recent papers on CAR-T therapy for multiple myeloma and provide citations in APA format`
  - Expected: pubmed_search → fetch_citation → formatted references

- [ ] `Compare the drug targets of imatinib and nilotinib`
  - Expected: chembl_search (imatinib) → chembl_search (nilotinib) → comparison

- [ ] `What are the known pathogenic variants in the CFTR gene?`
  - Expected: clinvar_lookup (CFTR) → uniprot_lookup (CFTR) → summary

- [ ] `Look up the protein EGFR, find its 3D structure, and list approved drugs targeting it`
  - Expected: uniprot_lookup → pdb_search → chembl_search → synthesis

## Tier 3: Report Generation (tools + generate_pdf)

- [~] `/report Top drug targets for glioblastoma multiforme with approved therapies and clinical pipeline`
  - Expected: opentargets_search → pubmed_search → generate_pdf
  - Status: PDF generates but content thin (2-3KB). Agent doesn't enrich with knowledge.
  - Times tested: 4. Success rate: 3/4.

- [ ] `/report Comprehensive analysis of TP53 mutations in breast cancer`
  - Expected: uniprot_lookup → clinvar_lookup → pubmed_search → generate_pdf

- [ ] `/report Drug repurposing opportunities for Huntington disease`
  - Expected: opentargets_search → chembl_search → pubmed_search → generate_pdf

- [ ] `/report BRCA1 and BRCA2 clinical variant landscape with pathogenicity distribution`
  - Expected: clinvar_lookup (BRCA1) → clinvar_lookup (BRCA2) → generate_chart → generate_pdf

## Tier 4: Data Export (tools + generate_excel)

- [ ] `/export All pathogenic BRCA1 variants from ClinVar`
  - Expected: clinvar_lookup → generate_excel with variant table

- [ ] `/export Comparison of approved kinase inhibitors for cancer`
  - Expected: chembl_search → generate_excel with drug properties table

- [ ] `/export Top 20 PubMed papers on immunotherapy in melanoma`
  - Expected: pubmed_search → generate_excel with paper details

## Tier 5: Visualization (tools + generate_chart)

- [ ] `/chart Distribution of TP53 variant types in cancer`
  - Expected: clinvar_lookup → generate_chart (pie or bar)

- [ ] `/chart Top 10 drug targets for glioblastoma by association score`
  - Expected: opentargets_search → generate_chart (horizontal bar)

- [ ] `/chart Comparison of molecular weights of FDA-approved kinase inhibitors`
  - Expected: chembl_search → generate_chart (bar chart)

## Tier 6: Complex Multi-Step Research

- [ ] `A patient has a VUS in EGFR at position c.2573T>G. What is the predicted functional impact, are there similar pathogenic variants nearby, and what targeted therapies exist for EGFR-mutant cancers?`
  - Expected: ensembl_vep → clinvar_lookup → chembl_search → uniprot_lookup → clinical interpretation

- [ ] `I found a novel variant in the RB1 gene at chr13:48367512 G>A. Interpret this variant, check population frequency, identify the affected protein domain, and generate a clinical interpretation report as PDF.`
  - Expected: ensembl_vep → clinvar_lookup → uniprot_lookup → generate_pdf

- [ ] `Compare the efficacy landscape of PD-1 inhibitors (pembrolizumab, nivolumab, cemiplimab) — search literature, find target info, and create an Excel comparison sheet.`
  - Expected: chembl_search x3 → pubmed_search → generate_excel

- [ ] `Search for the latest research on PCSK9 inhibitors, find structural data for PCSK9, identify all approved drugs, create a bar chart of their molecular weights, and compile everything into a PDF report.`
  - Expected: pubmed_search → uniprot_lookup → pdb_search → chembl_search → generate_chart → generate_pdf

- [ ] `What genes are most commonly mutated in triple-negative breast cancer? For the top 3, look up their protein function, check ClinVar for pathogenic variants, and generate an Excel sheet summarizing everything.`
  - Expected: pubmed_search → uniprot_lookup x3 → clinvar_lookup x3 → generate_excel

## Tier 7: VLM (Vision)

- [ ] `Analyze this protein structure image and identify key binding sites` (requires image upload feature)
  - Expected: analyze_image_vlm → structural interpretation

- [ ] `Here is a gel electrophoresis image. Identify the bands and estimate molecular weights.` (requires image)
  - Expected: analyze_image_vlm → band analysis

## Tier 8: Edge Cases & Stress Tests

- [ ] `What is rs9999999999?` (non-existent variant)
  - Expected: clinvar_lookup returns no results → agent says "no data found"

- [ ] `/protein NOTAREALGENE`
  - Expected: uniprot_lookup returns no results → graceful error message

- [ ] `/drug ` (empty query)
  - Expected: Agent asks for clarification, doesn't crash

- [ ] `Generate a PDF report about quantum computing` (off-topic)
  - Expected: Agent responds but doesn't use biology tools

- [ ] Same query 3x rapidly (rate limiting test)
  - Expected: All 3 should complete without server errors

---

## Known Issues (from production logs)

1. **Empty model responses (~20%)**: gemini-2.5-flash returns empty after processing tool results. Hermes retries 3x then fails silently.
2. **Redundant tool calls**: Agent calls same tool with same/similar query multiple times before synthesizing. Mitigated by max_iterations=6 cap.
3. **PubMed disconnects**: NCBI occasionally returns `Server disconnected without sending a response`. Agent retries with rephrased query.
4. **PDF content quality**: Reports are thin — agent dumps tool data without enriching with training knowledge. Needs better SOUL.md synthesis instructions.
5. **No .env warning**: `No .env file found. Using system environment variables.` — harmless, Docker injects env vars.
6. **Model naming**: `gemini-3-flash` doesn't exist on API. Must use `gemini-2.5-flash` or `gemini-3-flash-preview`.
7. **JWT key warning**: `HMAC key is 29 bytes` — need 32+ byte secret for production.
8. **Context overflow**: 10+ tool calls fills Gemini context → empty responses. Fixed by capping iterations and trimming result sizes.
