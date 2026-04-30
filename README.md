# CRYO — Comprehensive Research Yielding Outcomes

AI-powered biology research platform with multi-canvas workspace. Mine literature, annotate proteins, repurpose drugs, interpret genomic variants, run omics pipelines, and generate interactive research reports — branch and explore like a research flowchart.

Built on [Hermes Agent](https://github.com/nousresearch/hermes-agent) with 28 custom biology tools + a genome-scale metabolic **Digital Twin** engine, powered by Gemini 3 Pro Preview.

## Quick Start

```bash
git clone <repo-url> cryo && cd cryo
cp .env.example .env       # Set GEMINI_API_KEY, JWT_SECRET
bash cryo.sh               # Builds image + starts all services + tails logs
open http://localhost:3000
```

Default superuser: `creator@cryo.in` / `creator@shivam0705`

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

## File Upload

Every chat (chat mode and workspace nodes) has a file upload button. Files are tracked in PostgreSQL and auto-classified.

**How to use:**
1. Click the paperclip icon or drag-and-drop a file onto the input area
2. File uploads with a real-time progress bar
3. On success, the suggested command + server path are auto-inserted into the input
4. Send to run the analysis

**Auto-classification:**
| File | Detected As | Suggested Command |
|------|-------------|-------------------|
| `*counts*.csv`, `*expression*.csv` | RNA-seq counts | `/deseq` |
| `*.h5ad` | scRNA-seq | `/scrna` |
| `*.bam` | BAM alignment | `/atac` |
| `*.fastq.gz`, `*.fq.gz` | FASTQ reads | `/meta` |
| `*proteingroups*.txt` | Proteomics | `/ms` |
| `*sec*.csv` | SEC chromatography | `/sec` |
| `*.xlsx` | Spreadsheet | `/export` |
| `*.fa`, `*.fasta` | FASTA sequence | `/protein` |

**Accepted formats:** `.csv`, `.tsv`, `.txt`, `.h5ad`, `.h5`, `.hdf5`, `.bam`, `.fastq`, `.fastq.gz`, `.fq`, `.fq.gz`, `.xlsx`, `.xls`, `.parquet`, `.json`, `.fa`, `.fasta`

**Max file size:** 2 GB

Files are stored in `/cryo-data/uploads/{user_id}/` and tracked in the `uploads` PostgreSQL table with filename, size, data_type, conversation link, and usage counter.

## Digital Twin

CRYO includes a genome-scale metabolic drug simulation engine built on [Human-GEM](https://github.com/SysBioChalmers/Human-GEM) (12,931 reactions, 2,848 genes) and COBRApy FBA.

```bash
/digital_twin glucose_inhibitor              # hardcoded — shows real biomass drop
/digital_twin metformin --cell_line HeLa     # Complex I → mitochondrial metabolism
/simulate 5-fluorouracil --cell_line HCT116  # TYMS target, GDSC IC50 = 15.0 μM
/digital_twin imatinib --cell_line MCF7      # ABL1/KIT/PDGFRB annotated; 0% Δbiomass (kinase, expected)
```

### What it does

1. **Drug target resolution** — ChEMBL REST → DGIdb GraphQL → SQLite cache (7-day TTL)
2. **Cell line personalization** — CCLE expression data (49 cell lines, 19,215 genes) → GPR scaling
3. **Media contextualization** — CCLE available → `human1_minimal` + GPR; no CCLE → `cancer_warburg`
4. **FBA simulation** — baseline and perturbed flux balance analysis; 90% inhibition on drug-targeted reactions
5. **GDSC2 validation** — experimental IC50 (μM) lookup from 235,748 drug-cell pairs
6. **Citations** — Human-GEM + COBRApy always; ChEMBL/DGIdb/CCLE/GDSC conditionally

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
│  │ Sidebar + ChatPage   │  │ React Flow canvas                  │ │
│  │ ChatInput + SlashMenu│  │ ChatNode (mini chat, per node)     │ │
│  │ FileUploadButton     │  │ FileUploadButton (compact)         │ │
│  │ ReportPanel (side)   │  │ Branching, resize, pan/zoom        │ │
│  │ MessageBubble (md)   │  │ Workspace persistence (PG)         │ │
│  └──────────────────────┘  └────────────────────────────────────┘ │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP + SSE
┌───────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (localhost:8000)                 │
│                                                                    │
│  /api/auth/*          JWT auth (signup, login, me)                 │
│  /api/chat/*          Conversations, SSE streaming, tools list     │
│  /api/workspace/*     List, create, get, save, rename, delete      │
│  /api/uploads         File upload, list, delete (2GB limit)        │
│  /api/reports/*       Serve generated HTML/Excel/PNG               │
│  /api/digital-twin/*  Metabolic simulation endpoints               │
│  /api/health          Health check                                 │
│                                                                    │
│  HermesBridge         Slash translation, conversation history,     │
│                       report format injection, per-request agent   │
│  Report Engine v4     Markdown → interactive HTML (Plotly, Mermaid,│
│                       callouts, timelines, progress bars, tables)  │
└──────────┬───────────────────────────┬───────────────────────────┘
           │                           │
┌──────────▼──────────┐  ┌────────────▼────────────────────────────┐
│   PostgreSQL 17     │  │   Hermes Agent (per-request)             │
│                     │  │   gemini-3-pro-preview · 32K tokens      │
│  users, api_keys    │  │                                          │
│  conversations      │  │  28 CRYO Tools:                          │
│  messages           │  │   pubmed_search · biorxiv_search         │
│  workspaces         │  │   fetch_citation · uniprot_lookup        │
│  workspace_nodes    │  │   pdb_search · chembl_search             │
│  workspace_edges    │  │   opentargets_search · vep               │
│  uploads            │  │   clinvar_lookup · ensembl_vep           │
│  papers, genes      │  │   stringdb_ppi · kegg_pathway            │
│  proteins, drugs    │  │   reactome_enrichment                    │
│  variants           │  │   differential_expression (PyDESeq2)     │
│  knowledge_edges    │  │   scrna_analysis (Scanpy)                │
│                     │  │   cell_annotation (CellTypist)           │
└─────────────────────┘  │   atac_seq · chip_seq (MACS3)           │
                          │   metagenomics (Kraken2+HUMAnN3)        │
┌─────────────────────┐  │   proteomics_ms · sec_report            │
│  cryo-data/         │  │   novelty_check · manuscript_pipeline    │
│  (bind-mounted)     │  │   compile_report · generate_excel        │
│  users/{uid}/       │  │   generate_chart · verify_claim          │
│   uploads/          │  │   analyze_image_vlm · deep_research      │
│   conversations/    │  │   digital_twin                           │
│    {cid}/           │  └──────────────────────────────────────────┘
│     reports/*.html  │
│  models/human1/     │  ┌──────────────────────────────────────────┐
│  ccle/*.parquet     │  │   Digital Twin Engine                     │
│  gdsc/*.csv         │  │   Human-GEM (12,931 rxns, 2,848 genes)   │
│  cache/             │  │   COBRApy FBA · CCLE GPR scaling         │
└─────────────────────┘  │   ChEMBL + DGIdb drug target lookup      │
                          │   GDSC2 IC50 validation                  │
                          │   SQLite drug cache (7-day TTL)          │
                          └──────────────────────────────────────────┘
```

## Tools Reference

### Core Biology (18 tools)

| Tool | Source | What It Does |
|------|--------|-------------|
| `pubmed_search` | NCBI E-utilities | Search papers, PMIDs, abstracts |
| `biorxiv_search` | bioRxiv API | Search preprints |
| `fetch_citation` | CrossRef + PubMed | APA/MLA/Chicago citations |
| `uniprot_lookup` | UniProt REST | Protein function, domains, GO terms |
| `pdb_search` | RCSB PDB | 3D structures |
| `chembl_search` | ChEMBL REST | Drug properties, SMILES, approval |
| `opentargets_search` | OpenTargets GraphQL | Disease-target associations |
| `clinvar_lookup` | ClinVar/NCBI | Variant pathogenicity |
| `ensembl_vep` | Ensembl REST | SIFT/PolyPhen variant effects |
| `compile_report` | Report Engine v4 | Markdown → interactive HTML report |
| `get_last_report` | Disk | Retrieve raw markdown for editing |
| `generate_excel` | openpyxl | Multi-sheet spreadsheets |
| `generate_chart` | matplotlib | Standalone chart PNGs |
| `verify_claim` | Multi-source | Cross-check claims (PubMed + OpenTargets + CrossRef) |
| `analyze_image_vlm` | Gemini Vision | Analyze microscopy, gels, structures |
| `deep_research` | gpt-researcher | Autonomous deep research |
| `multi_agent_research` | open_deep_research | Multi-agent research |
| `scientific_skill` | 133 skill packs | Biopython, DeepChem, ESM, MedChem |

### Omics Databases (3 tools)

| Tool | Source | What It Does |
|------|--------|-------------|
| `stringdb_ppi` | STRING v12 REST | PPI network + functional enrichment for gene list |
| `kegg_pathway` | KEGG REST API | Pathway search, details, gene members |
| `reactome_enrichment` | Reactome AnalysisService | Pathway enrichment for gene set, FDR-filtered |

### Analysis Skills (10 tools)

These tools return a code template + step-by-step instructions that the Hermes agent runs via `code_execution_tool`. They require uploaded data files.

| Tool | Stack | What It Does |
|------|-------|-------------|
| `differential_expression` | PyDESeq2 | DESeq2-equivalent DE analysis, volcano plot, DEG table |
| `scrna_analysis` | Scanpy | QC → normalization → UMAP → Leiden clustering → marker genes |
| `cell_annotation` | CellTypist | Automated cell type labeling with majority voting |
| `atac_seq` | MACS3 | Peak calling from BAM with `--shift -75 --extsize 150`, FRiP scoring |
| `chip_seq` | MACS3 | Peak calling with input control, narrow/broad peak mode |
| `metagenomics` | Kraken2 + HUMAnN3 | FastQC → Trimmomatic → Kraken2 → Bracken → HUMAnN3 functional profiling |
| `proteomics_ms` | MaxQuant output | Parse proteinGroups.txt, LFQ normalization, PCA, volcano |
| `sec_report` | scipy | Savitzky-Golay smoothing, peak detection, oligomeric state classification |
| `novelty_check` | PubMed API | Literature saturation score 1–10 based on recent publications |
| `manuscript_pipeline` | Structured workflow | 8-stage paper planning: intro → methods → figures → submission |

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
