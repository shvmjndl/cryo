# CRYO — Comprehensive Research Yielding Outcomes
(whoever stumbles on this repo, pls note im still working on it as a single person team, if some features donot work pls raise an issue or PR :))

**AI-powered biology research platform** designed for autonomous scientific discovery. Synthesize literature, analyze proteins, repurpose drugs, interpret genomic variants, run omics pipelines, simulate metabolic drug responses, and generate publication-ready interactive reports — branch and explore research hypotheses like a visual flowchart.

**Built on:** [Hermes Agent](https://github.com/nousresearch/hermes-agent) with **28+ biology tools** | **Genome-scale metabolic digital twin engine** (Human-GEM, iJO1366, Yeast8, etc.) | **Interactive report engine v4** with charts, diagrams, callouts, timelines | **Google Gemini 3 Pro Preview** | **React Flow workspace** | **PostgreSQL persistence**

## Quick Start

```bash
git clone <repo-url> cryo && cd cryo
cp .env.example .env           # Set GEMINI_API_KEY, JWT_SECRET (required)
bash cryo.sh                   # Builds Docker image + starts all services (db, api, frontend)
open http://localhost:3000     # Access CRYO in browser
```

**Default superuser:** `creator@cryo.in` / `creator@shivam0705`

**Services:**
- 🖥️ **Frontend** (React 19 + TypeScript): http://localhost:3000
- 🔌 **API** (FastAPI + SSE): http://localhost:8000
- 🗄️ **PostgreSQL 17**: localhost:5432
- 📊 **Reports serve** from `/cryo-data/users/{uid}/conversations/{cid}/reports/`

## Two Interfaces

### Chat View (`/`)
Traditional single-thread chat with sidebar conversation history, slash commands, streaming responses, file upload, and report viewer panel.

### Workspace View (`/workspace`)
Multi-canvas research workspace built on React Flow:

```
┌─────────────────────────────────────────────────────────────────┐
│ CRYO Workspace                                    [+ New Node]  │
│                                                                  │
│ ┌──────────────┐         ┌──────────────┐                       │
│ │ 🧬 EGFR       │────────▶│ 🔬 Osimertinib│                      │
│ │ protein info  │         │ drug info     │                      │
│ │              │         │               │   ┌──────────────┐   │
│ │ [messages]   │         │ [messages]    │──▶│ 📋 Report:    │   │
│ │ [/commands]  │         │ [Branch btn]  │   │ EGFR in NSCLC │   │
│ └──────────────┘         └──────────────┘   └──────────────┘   │
│                                                                  │
│ Pan: drag background · Zoom: scroll · Resize: drag node corner  │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- **Multiple research nodes** — each is an independent chat with its own conversation
- **Branching** — hover any assistant response → click Branch → spawns connected child node with context
- **Resizable nodes** — drag bottom-right corner
- **Slash commands** in every node (all 30 commands available)
- **File upload** — drag-drop or click to attach data files in every node
- **Collapsible panels** — left (workspace list) and right (node list), draggable width
- **Multiple workspaces** — create, switch, rename, delete (max 10 per user, max 50 nodes per workspace)
- **Persistent** — nodes, positions, edges, conversations all saved to PostgreSQL
- **Messages reload** — refresh page → messages load from conversation history
- **Visual connections** — animated cyan arrows between branched nodes
- **Minimap** — overview of all nodes in corner

## Slash Commands

Type `/` in any chat or workspace node. Commands are grouped by category:

### Literature
| Command | Example | What It Does |
|---------|---------|-------------|
| `/pubmed <query>` | `/pubmed CRISPR glioblastoma` | Search PubMed literature |
| `/biorxiv <query>` | `/biorxiv single-cell RNA-seq` | Search bioRxiv preprints |

### Protein & Structure
| Command | Example | What It Does |
|---------|---------|-------------|
| `/protein <gene>` | `/protein TP53` | Protein/gene lookup (UniProt) |
| `/structure <id>` | `/structure EGFR` | Protein 3D structures (PDB) |

### Drug & Variant
| Command | Example | What It Does |
|---------|---------|-------------|
| `/drug <name>` | `/drug temozolomide` | Drug/compound info (ChEMBL) |
| `/targets <disease>` | `/targets glioblastoma` | Disease-target associations |
| `/variant <rsid>` | `/variant rs28934578` | Variant clinical significance |
| `/vep <pos>` | `/vep 17:7675088:C:T` | Variant effect prediction |
| `/repurpose <disease>` | `/repurpose Huntington disease` | Drug repurposing candidates |

### Simulation
| Command | Example | What It Does |
|---------|---------|-------------|
| `/digital_twin <drug> [--cell_line <line>]` | `/digital_twin imatinib --cell_line MCF7` | Metabolic drug response simulation |
| `/simulate <drug> [--cell_line <line>]` | `/simulate metformin --cell_line HeLa` | Alias for `/digital_twin` |

### Omics Databases
| Command | Example | What It Does |
|---------|---------|-------------|
| `/ppi <gene>` | `/ppi TP53` | Protein-protein interactions (StringDB) |
| `/kegg <query>` | `/kegg cell cycle` | KEGG pathway search |
| `/reactome <genes>` | `/reactome BRCA1,BRCA2,ATM` | Reactome pathway enrichment |

### Analysis Pipelines (requires file upload)
| Command | Example | What It Does |
|---------|---------|-------------|
| `/deseq <file> vs <control>` | `/deseq counts.csv vs control` | Differential expression (PyDESeq2) |
| `/scrna <file>` | `/scrna data.h5ad` | scRNA-seq clustering (Scanpy) |
| `/annotate <file>` | `/annotate scrna_processed.h5ad` | Cell type annotation (CellTypist) |
| `/atac <file>` | `/atac sample.bam` | ATAC-seq peak calling (MACS3) |
| `/chip <file> vs <input>` | `/chip chip.bam vs input.bam` | ChIP-seq peak calling (MACS3) |
| `/meta <fastq>` | `/meta sample_R1.fastq.gz` | Metagenomics (Kraken2 + HUMAnN3) |
| `/ms <file>` | `/ms proteinGroups.txt` | Mass spectrometry proteomics |
| `/sec <file>` | `/sec sec_data.csv` | SEC chromatography analysis |

### Research Workflow
| Command | Example | What It Does |
|---------|---------|-------------|
| `/novelty <topic>` | `/novelty CRISPR base editing sickle cell` | Research novelty/saturation check |
| `/paper <topic>` | `/paper spatial transcriptomics TNBC` | Full manuscript planning pipeline |

### Output
| Command | Example | What It Does |
|---------|---------|-------------|
| `/compare <A> <B>` | `/compare BRCA1 BRCA2` | Compare genes/proteins/drugs |
| `/export <topic>` | `/export TP53 variants` | Export to Excel |
| `/report <topic>` | `/report glioblastoma drug targets` | Generate interactive HTML report |
| `/chart <topic>` | `/chart cancer mutation frequency` | Generate visualization |

## File Upload & Collections

### Upload Feature (v2 — 2026-05-15)

Every chat (chat mode and workspace nodes) has a **drag-drop file upload** button with real-time progress tracking.

**Workflow:**
1. Click the 📎 icon or drag-and-drop a file onto the input area
2. Real-time progress bar shows upload status
3. **Auto-classified:** suggested command + server path inserted into input
4. Send to run the analysis or share with agent

**Auto-classification Engine:**
| File Pattern | Detected As | Suggested Command |
|------|-------------|-------------------|
| `*counts*.csv`, `*expression*.csv` | RNA-seq counts | `/deseq` |
| `*.h5ad`, `*.h5`, `*.hdf5` | scRNA-seq | `/scrna` |
| `*.bam` | BAM alignment | `/atac` or `/chip` |
| `*.fastq.gz`, `*.fq.gz`, `*.fastq` | FASTQ reads | `/meta` |
| `*proteingroups*.txt` | MS proteomics | `/ms` |
| `*sec*.csv` | SEC chromatography | `/sec` |
| `*.xlsx`, `*.xls` | Spreadsheet | `/export` |
| `*.fa`, `*.fasta` | FASTA sequence | `/protein` |
| `*.pdf`, `*.png`, `*.jpg` | Images/documents | `/analyze_image_vlm` |

**Specs:**
- **Accepted formats:** `.csv`, `.tsv`, `.txt`, `.h5ad`, `.h5`, `.hdf5`, `.bam`, `.fastq`, `.fastq.gz`, `.fq`, `.fq.gz`, `.xlsx`, `.xls`, `.parquet`, `.json`, `.fa`, `.fasta`, `.pdf`, `.png`, `.jpg`, `.jpeg`
- **Max file size:** 2 GB
- **Storage:** `/cryo-data/uploads/{user_id}/`
- **Metadata:** PostgreSQL `uploads` table tracks filename, size, data_type, conversation_id, usage_count

### Collections (v1 — 2026-05-15)

**Organize research artifacts** into topic collections. Reference collections in chat to automatically inject context.

**Usage:**
```bash
/collection create Alzheimer_drug_targets
/collection add <topic> → adds to active collection
/collection list → shows all collections + item counts
/collection show <name> → displays collection contents
@collection:Alzheimer_drug_targets → mentions collection in chat (injects metadata)
```

**Schema:**
- Collections: user_id, name, created_at, description, metadata
- Items: collection_id, content_type (paper, gene, drug, pathway), identifier, extracted_data
- Auto-populated from: reports, literature searches, drug lookups, gene annotations

## Digital Twin v3 (Multi-Backbone Simulation Engine)

CRYO includes a **genome-scale metabolic drug simulation engine** supporting **multiple organism models** with real drug target lookup and cell-line personalization.

### Supported Models (Backbones)

| Backbone | Organism | Reactions | Genes | Cell Line Support |
|----------|----------|-----------|-------|------------------|
| **Human-GEM** | *Homo sapiens* | 12,931 | 2,848 | ✅ 49 CCLE lines |
| **iJO1366** | *E. coli* K-12 | 1,366 | 1,337 | ❌ Generic only |
| **Yeast8** | *S. cerevisiae* | 3,953 | 1,045 | ❌ Generic only |
| **Plasmodium** | *P. falciparum* | 1,267 | 705 | ❌ Generic only |

### Usage Examples

```bash
/digital_twin glucose_inhibitor              # Human-GEM: hardcoded target on MAR09034
/digital_twin metformin --cell_line HeLa     # Human-GEM + CCLE GPR scaling (MCF7, HeLa, etc.)
/simulate 5-fluorouracil --cell_line HCT116  # TYMS target lookup, GDSC IC50 validation
/digital_twin imatinib --cell_line MCF7      # ABL1/KIT/PDGFRB from ChEMBL; ~8 biomass (MCF7-specific)
/digital_twin trimethoprim --model ijo1366   # Pathogen: folA gene mapping, iJO1366 backbone
/digital_twin fluconazole --model yeast8     # Yeast: ERG11 target, S. cerevisiae model
/gem stats --model ijo1366                   # Query genome stats: 1,366 reactions, 1,337 genes
```

### Recent Validations (2026-04-30)

| Drug | Backbone | Target | Cell Line | Biomass Change | Notes |
|------|----------|--------|-----------|----------------|-------|
| `trimethoprim` | iJO1366 | folA → DHFR | — | **-90%** ✓ | Pathogen digital twin |
| `sulfamethoxazole` | iJO1366 | folP → DHPS2 | — | **-90%** ✓ | Antibacterial |
| `fluconazole` | yeast8 | ERG11 → r_0317 | — | **-90%** ✓ | Antifungal |
| `metformin` | Human-GEM | MT-ND1 (Complex I) | MCF7 | **-18%** ✓ | Cell-line specific |
| `imatinib` | Human-GEM | ABL1/KIT/PDGFRA | MCF7 | **0%** (kinase) | Expected (signaling) |

### Pipeline: Drug → FBA → Report

1. **Drug target resolution**
   - Human drugs: ChEMBL REST + DGIdb GraphQL with SQLite cache (7-day TTL)
   - Pathogen drugs: Custom pathogen_targets_db for *E. coli*, *S. cerevisiae*, *P. falciparum*
   - Fallback: Query as reaction ID directly (e.g., `MAR09034` for glucose exchange)

2. **Model selection**
   - `--model ijo1366`: *E. coli* iJO1366 (antibacterial context)
   - `--model yeast8`: *S. cerevisiae* (antifungal context)
   - Default (Human-GEM): Cancer drug response, metabolic disease

3. **Cell line personalization** (Human-GEM only)
   - CCLE expression data (49 cell lines × 19,215 genes)
   - Gene expression → reaction GPR constraints (TPM < 1.0 → upper_bound = 0.001)
   - Media adaptation: `cancer_warburg` (generic) or `human1_minimal` (CCLE-constrained)

4. **FBA simulation**
   - Baseline flux balance (growth rate as biomass production)
   - Perturbed: 90% inhibition on drug-targeted reactions
   - Delta computation: `(perturbed_biomass - baseline) / baseline × 100%`

5. **GDSC2 validation** (Human drugs + cell lines)
   - Lookup experimental IC50 (μM) from 235,748 drug-cell pairs
   - Display in report with trial phase data

6. **HTML report + PNG plot**
   - Markdown with :::diagram (pathway), :::callout (findings), tables
   - Flux bar chart (top 10 reactions, delta values)

### `--cell_line` flag

**Without `--cell_line`** — uses generic cancer Warburg model (glucose-limited):
```
/digital_twin metformin
→ cancer_warburg media (glucose-limited)
→ biomass baseline: 62.43  (generic Human1)
```

**With `--cell_line`** — constrains the model to cell line's actual RNA expression:
```
/digital_twin metformin --cell_line MCF7
→ loads MCF7 RNA-seq from CCLE (19,215 genes, TPM values)
→ reactions where ALL driving genes have TPM < 1.0 → upper_bound = 0.001
→ 1,212 reactions constrained for MCF7
→ biomass baseline: 8.06  (MCF7-specific)
```

**Supported cell lines (49):**
MCF7, HeLa, A549, HCT116, PC3, LNCaP, U87MG, HepG2, K562, Jurkat, T98G, MDA-MB-231, SK-BR-3, BT474, ZR75-1, PANC1, and 33 more.

### Known scientific limitations

| Limitation | Root Cause | Impact |
|-----------|-----------|--------|
| TKIs always show 0% biomass change | ABL1/EGFR/PDGFRA are signaling kinases not in Human1 | Drug annotation + GPR still work; no direct flux inhibition |
| Most drugs show 0% biomass change | FBA degrees of freedom — solver routes around single blocks | Hardcoded targets and Complex I drugs show real effects |

### Best drugs to test

| Drug | Target | Effect |
|------|--------|--------|
| `glucose_inhibitor` | MAR09034 (glucose exchange) | Hardcoded — biomass drops >10% |
| `atp_synthase_inhibitor` | MAR04137 (ATP synthase) | ATP production blocked |
| `metformin` | MT-ND1 (Complex I) | Mitochondrial ETC target |
| `5-fluorouracil` | TYMS (thymidylate synthase) | Nucleotide synthesis |
| `methotrexate` | DHFR (dihydrofolate reductase) | Folate metabolism |

### Setup (one-time)

```bash
# Downloads GDSC2 (~10MB), creates SQLite drug cache
docker exec cryo-api-1 python /app/scripts/setup_digital_twin.py

# Preprocess CCLE data (download OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv
# from depmap.org/portal/download/ → place in /cryo-data/ccle/)
docker exec cryo-api-1 python /app/scripts/preprocess_ccle.py
```

## Report Engine v4

Reports are interactive HTML pages with:
- **Plotly.js charts** (bar, pie, line, scatter) — via `:::chart` blocks
- **Mermaid.js diagrams** (pathway flowcharts) — via `:::diagram` blocks
- **Callout boxes** (info/warning/success/danger) — via `:::callout` blocks
- **Progress bars** (mutation frequencies, trial enrollment) — via `:::progress` blocks
- **Timelines** (drug approval history) — via `:::timeline` blocks
- **Sortable tables** — auto-parsed from markdown pipe tables
- **Sidebar TOC** with scroll-spy
- **Search bar** for in-report text search
- **Dark/light mode** toggle
- **Print button** (clean print layout)
- **Cover page** with CRYO branding and report ID

Reports open in a slide-in side panel within CRYO — no new browser tab.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    BROWSER (localhost:3000)                        │
│  React 19 · TypeScript · Tailwind 4 · Vite 6 · React Flow 12    │
│                                                                    │
│  ┌─ Chat View ──────────┐  ┌─ Workspace View ──────────────────┐ │
│  │ Sidebar + ChatPage   │  │ React Flow canvas (pan/zoom)       │ │
│  │ ChatInput + SlashMenu│  │ Resizable ChatNodes (mini chat)    │ │
│  │ FileUploadButton     │  │ Branching (context inheritance)    │ │
│  │ ReportPanel (slide)  │  │ File upload per node               │ │
│  │ MessageBubble (md)   │  │ Workspace persistence (PG)         │ │
│  └──────────────────────┘  └────────────────────────────────────┘ │
│                                                                    │
│  Collections: Topic-based metadata org (papers, genes, drugs)    │
│  File Mentions: @file:name syntax in chat                        │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP + SSE
┌───────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (localhost:8000)                 │
│                                                                    │
│  /api/auth/*              JWT auth (signup, login, me)             │
│  /api/chat/*              Conversations, SSE streaming             │
│  /api/workspace/*         CRUD + node positions/edges save         │
│  /api/collections/*       Topic org (create, add, show)            │
│  /api/uploads             File upload, list, delete (2GB)          │
│  /api/reports/*           Serve HTML/Excel/PNG reports             │
│  /api/digital-twin/*      Metabolic simulation REST endpoints      │
│  /api/gem/*               Genome-scale model queries               │
│  /api/health              Health + dependency check                │
│                                                                    │
│  HermesBridge             Slash command dispatch, agent wrapper     │
│  Report Engine v4         Markdown + :::blocks → interactive HTML   │
│  Digital Twin Service v3  Multi-backbone FBA + GPR scaling         │
│  VLM Client               Gemini Vision 2 integration (images)     │
└──────────┬───────────────────────────┬───────────────────────────┘
           │                           │
┌──────────▼──────────┐  ┌────────────▼────────────────────────────┐
│   PostgreSQL 17     │  │   Hermes Agent (per-request)             │
│                     │  │   google-gemini-3-pro-preview · 32K       │
│  users, api_keys    │  │                                          │
│  conversations      │  │  28+ CRYO Tools:                         │
│  messages           │  │   pubmed_search · biorxiv_search         │
│  workspaces         │  │   fetch_citation · uniprot_lookup        │
│  workspace_nodes    │  │   pdb_search · chembl_search · targets   │
│  workspace_edges    │  │   opentargets_search · clinvar_lookup    │
│  uploads            │  │   ensembl_vep · stringdb_ppi             │
│  collections        │  │   kegg_pathway · reactome_enrichment     │
│  papers, genes      │  │   differential_expression (PyDESeq2)     │
│  proteins, drugs    │  │   scrna_analysis · cell_annotation       │
│  variants           │  │   atac_seq · chip_seq (MACS3)            │
│  knowledge_edges    │  │   metagenomics · proteomics_ms · sec_*   │
│                     │  │   novelty_check · manuscript_pipeline    │
│                     │  │   compile_report · generate_excel/chart  │
│                     │  │   verify_claim · analyze_image_vlm        │
│                     │  │   deep_research · digital_twin · /gem     │
└─────────────────────┘  └──────────────────────────────────────────┘
                          
┌─────────────────────────────────────────────────────────────────┐
│  Data & Services (bind-mounted /cryo-data/)                      │
├─────────────────────────────────────────────────────────────────┤
│  users/{uid}/                                                   │
│    uploads/                      ← Uploaded files (2GB max)     │
│    conversations/{cid}/          ← Per-conversation artifacts   │
│      reports/*.html              ← Interactive reports (v4)     │
│      sources/*.json              ← Markdown (editable)          │
│  models/                                                        │
│    human1/human1.xml             ← Human-GEM (12.9k reactions) │
│    ijo1366/ijo1366.json          ← E. coli (1.3k reactions)    │
│    yeast8/yeast8.json            ← S. cerevisiae (3.9k reactions) │
│  ccle/                                                          │
│    ccle_expression_human1.parquet ← 49 cell lines × 19,215 genes │
│  gdsc/                                                          │
│    gdsc2_sensitivity.csv         ← 235,748 drug-cell IC50s     │
│  cache/                                                         │
│    drug_targets.db               ← SQLite (ChEMBL/DGIdb, 7d TTL) │
└─────────────────────────────────────────────────────────────────┘

Optional Services:
┌─────────────────────────────────────────────────────────────────┐
│  VLM OCR Server (localhost:8001) — Image analysis microservice   │
│  Gemini Vision 2 · Tesseract OCR · JSON output                  │
└─────────────────────────────────────────────────────────────────┘
```

## Tools Reference

### Core Biology (18 tools)

| Tool | Source | Input | Output |
|------|--------|-------|--------|
| `pubmed_search` | NCBI E-utilities | Query string | PMIDs, titles, abstracts, citation count |
| `biorxiv_search` | bioRxiv API | Query string | Preprints, authors, dates |
| `fetch_citation` | CrossRef + PubMed | PMID or DOI | APA/MLA/Chicago formatted |
| `uniprot_lookup` | UniProt REST | Gene name (e.g., TP53) | Protein info: domains, GO, orthologs |
| `pdb_search` | RCSB PDB | Protein name or ID | 3D structures, resolution, ligands |
| `chembl_search` | ChEMBL REST | Drug/compound name | SMILES, properties, targets, IC50 |
| `opentargets_search` | OpenTargets GraphQL | Disease or gene | Disease-target association scores |
| `clinvar_lookup` | ClinVar/NCBI | Variant (rsid or HGVS) | Clinical significance, pathogenicity |
| `ensembl_vep` | Ensembl REST | Genomic position | SIFT/PolyPhen predictions, impact |
| `compile_report` | Report Engine v4 | Markdown content | Interactive HTML with charts/diagrams |
| `get_last_report` | Disk/DB | Conversation ID | Raw markdown for editing |
| `generate_excel` | openpyxl | Data + sheet names | Multi-sheet `.xlsx` spreadsheet |
| `generate_chart` | matplotlib/Plotly | Data + chart type | Standalone PNG or interactive HTML |
| `verify_claim` | Multi-source | Claim text | Verification status + sources |
| `analyze_image_vlm` | Gemini Vision | Image file | Image analysis (gels, microscopy, etc.) |
| `deep_research` | gpt-researcher | Topic | Deep multi-source research report |
| `multi_agent_research` | open_deep_research | Topic | Multi-perspective research synthesis |
| `scientific_skill` | 133 skill packs | Biopython, DeepChem, ESM, MedChem | Code templates + step-by-step execution |

### Omics Databases (3 tools)

| Tool | Source | What It Does |
|------|--------|-------------|
| `stringdb_ppi` | STRING v12 REST | PPI network + functional enrichment for gene list |
| `kegg_pathway` | KEGG REST API | Pathway search, details, gene members |
| `reactome_enrichment` | Reactome AnalysisService | Pathway enrichment for gene set, FDR-filtered |

### Analysis Skills (10 tools)

These tools return a code template + step-by-step instructions executed by Hermes agent. They require uploaded data files.

| Tool | Stack | Input | Pipeline |
|------|-------|-------|----------|
| `differential_expression` | PyDESeq2 | Count matrix CSV | DESeq2 → volcano plot → DEG table |
| `scrna_analysis` | Scanpy | H5AD file | QC → norm → UMAP → Leiden → markers |
| `cell_annotation` | CellTypist | H5AD (normalized) | Cell type labeling + confidence scores |
| `atac_seq` | MACS3 | BAM + metadata | Peak calling (--shift -75) → BED + FRiP |
| `chip_seq` | MACS3 | IP + input BAM | Narrow/broad peaks, summit annotation |
| `metagenomics` | Kraken2 + HUMAnN3 | FASTQ reads | FastQC → Kraken2 → Bracken → profiling |
| `proteomics_ms` | MaxQuant output | proteinGroups.txt | LFQ norm → PCA → volcano → pathways |
| `sec_report` | scipy | SEC trace CSV | Savitzky-Golay → peaks → oligomeric state |
| `novelty_check` | PubMed API | Research topic | Saturation score (1–10) + recent papers |
| `manuscript_pipeline` | Structured workflow | Topic + context | 8-stage planning: abstract → figs → submission |

### VLM & Image Analysis (New — 2026-05)

| Service | Model | What It Does |
|---------|-------|-------------|
| `analyze_image_vlm` | Gemini Vision 2 | Upload gel photos, microscopy images → extract data |
| `ocr_pipeline` | Gemini Vision 2 + Tesseract | Standalone VLM + OCR microservice (`:8001`) |

**VLM OCR Server** (optional container):
```bash
docker run -p 8001:8001 cryo-vlm:latest
# POST /process_image + image file → structured JSON
```

### Genome-Scale Model API (GEM Graph — v1, 2026-04)

Query any supported backbone (Human-GEM, iJO1366, Yeast8, Plasmodium).

| Endpoint | What It Returns |
|----------|----------------|
| `GET /api/gem/backbones` | List all 4 models + load status |
| `GET /api/gem/stats?backbone=ijo1366` | Reaction/gene/metabolite counts |
| `GET /api/gem/gene/{gene_id}?backbone=ijo1366` | Gene info + associated reactions |
| `GET /api/gem/reaction/{rxn_id}?backbone=ijo1366` | Reaction details (substrate, product, GPR) |

**Slash command:**
```bash
/gem stats --model ijo1366    # CLI query of above endpoints
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google AI Studio API key | **required** |
| `JWT_SECRET` | JWT signing secret | **required** |
| `HERMES_MODEL` | LLM model | `gemini-3-pro-preview` |
| `HERMES_MAX_ITERATIONS` | Max tool loops | `15` |
| `NCBI_API_KEY` | NCBI E-utilities key (free, 10 req/s) | optional |
| `NCBI_EMAIL` | Required when using NCBI key | optional |
| `CRYO_DATA_DIR` | Persistent data dir | `/cryo-data` |
| `CRYO_UPLOAD_DIR` | File upload directory | `{CRYO_DATA_DIR}/uploads` |
| `CRYO_REPORTS_DIR` | Reports directory | `{CRYO_DATA_DIR}/users` |
| `CRYO_CACHE_DIR` | SQLite cache directory | `{CRYO_DATA_DIR}/cache` |
| `CRYO_MAX_WORKSPACES_PER_USER` | Max workspaces | `10` |
| `CRYO_MAX_NODES_PER_WORKSPACE` | Max nodes | `50` |
| `POSTGRES_*` | Database config | `cryo:5432/cryo` |
| `MACS3_PATH` | MACS3 binary | `macs3` |
| `KRAKEN2_PATH` | Kraken2 binary | `kraken2` |
| `KRAKEN2_DB` | Kraken2 database path | `/cryo-data/kraken2_db` |
| `HUMANN3_PATH` | HUMAnN3 binary | `humann` |
| `FASTQC_PATH` | FastQC binary | `fastqc` |
| `DRUG_LOOKUP_CACHE_TTL_DAYS` | Drug target cache TTL | `7` |
| `PUBMED_MAX_RESULTS` | Max PubMed results | `20` |
| `STRINGDB_DEFAULT_CONFIDENCE` | StringDB confidence threshold | `0.4` |
| `REACTOME_FDR_THRESHOLD` | Reactome enrichment FDR | `0.05` |

## Data

```
cryo-data/                              ← bind-mounted from host
  ├── uploads/{user_id}/                ← uploaded data files (all types)
  ├── users/{user_id}/
  │   └── conversations/{conv_id}/
  │       ├── reports/*.html            ← generated interactive reports
  │       └── sources/*.json            ← raw markdown for editing
  ├── models/human1/human1.xml          ← Human-GEM (cached singleton)
  ├── ccle/
  │   └── ccle_expression_human1.parquet  ← 49 cell lines × 19,215 genes (17MB)
  ├── gdsc/
  │   └── gdsc2_sensitivity.csv         ← 235,748 drug-cell IC50 pairs
  └── cache/
      └── drug_targets.db              ← SQLite ChEMBL/DGIdb cache (7-day TTL)
```

## Project Structure

```
cryo/
├── api/                             # FastAPI backend
│   ├── routers/
│   │   ├── auth.py                  # JWT auth
│   │   ├── chat.py                  # SSE chat + conversations
│   │   ├── workspace.py             # Workspace CRUD + save
│   │   ├── uploads.py               # File upload, list, delete
│   │   └── digital_twin.py          # Simulation REST endpoints
│   ├── models/
│   │   ├── user.py                  # User model
│   │   ├── conversation.py          # Conversation + Message models
│   │   ├── workspace.py             # Workspace + Node + Edge models
│   │   └── upload.py                # Upload tracking model
│   └── services/
│       ├── hermes_bridge.py         # Agent wrapper + slash dispatch (30 commands)
│       ├── report_engine.py         # v4 HTML report engine
│       └── digital_twin/
│           ├── drug_lookup.py       # ChEMBL + DGIdb + SQLite cache
│           ├── ccle_loader.py       # CCLE parquet + GPR scaling
│           ├── gdsc_validator.py    # GDSC2 IC50 lookup
│           ├── personalizer.py      # Media + GPR pipeline
│           ├── media_registry.py    # Cancer Warburg / minimal media
│           ├── perturbation.py      # Drug inhibition logic
│           ├── simulator.py         # FBA baseline + perturbed
│           ├── reporting.py         # Digital twin HTML report + citations
│           ├── service.py           # Orchestration entry point
│           └── data/
│               └── media_registry.json
├── frontend/src/
│   ├── components/
│   │   ├── ChatInput.tsx            # Slash command input + file upload
│   │   ├── ChatNode.tsx             # Workspace node (mini chat + file upload)
│   │   ├── ChatMessage.tsx          # Markdown + bionic reading
│   │   ├── SlashMenu.tsx            # Command dropdown (30 commands, grouped)
│   │   ├── FileUploadButton.tsx     # Shared upload (chat + workspace)
│   │   ├── ReportPanel.tsx          # Slide-in report viewer
│   │   └── Sidebar.tsx              # Chat view sidebar
│   └── pages/
│       ├── ChatPage.tsx             # Traditional chat
│       └── WorkspacePage.tsx        # Multi-canvas workspace
├── hermes-agent/tools/
│   ├── cryo_digital_twin.py         # Digital twin tool schema
│   ├── cryo_literature.py           # PubMed/bioRxiv tools
│   ├── cryo_protein.py              # UniProt/PDB tools
│   ├── cryo_drug.py                 # ChEMBL/OpenTargets tools
│   ├── cryo_variant.py              # ClinVar/VEP tools
│   ├── cryo_reports.py              # Report/chart/export tools
│   ├── cryo_omics_databases.py      # StringDB/KEGG/Reactome tools
│   └── cryo_analysis_skills.py      # DESeq2/Scanpy/MACS3/etc skill tools
├── scripts/
│   ├── setup_digital_twin.py        # One-time data setup (GDSC + cache)
│   ├── preprocess_ccle.py           # CCLE CSV → parquet (49 cell lines)
│   └── verify_human1_exchanges.py   # Inspect Human1 reaction IDs
├── tests/
│   ├── test_digital_twin.py         # 8 integration tests
│   └── test_api.py                  # API endpoint tests
├── cryo-data/                       # Persistent data (bind-mounted)
├── db/schema.sql                    # PostgreSQL schema
├── SOUL.md                          # Agent persona + :::block examples
├── cryo.sh                          # One-command start script
└── docker-compose.yml               # 3 services: db, api, frontend
```

## Docker

```bash
bash cryo.sh                      # Rebuild image + start all + tail logs
docker compose up -d              # Start without rebuild
docker compose logs api -f        # Watch tool calls
docker compose restart api        # Reload after .env changes
```

## Tests

```bash
docker exec cryo-api-1 python -m pytest tests/test_digital_twin.py -v
# 8/8 passing (~60s)

docker exec cryo-api-1 python -m pytest tests/ -v
```

## License

MIT
