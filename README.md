# CRYO — Comprehensive Research Yielding Outcomes

AI-powered biology research platform with multi-canvas workspace. Mine literature, annotate proteins, repurpose drugs, interpret genomic variants, generate interactive research reports — branch and explore like a research flowchart.

Built on [Hermes Agent](https://github.com/nousresearch/hermes-agent) with 18 custom biology tools + a genome-scale metabolic **Digital Twin** engine, powered by Gemini 3 Pro Preview.

## Quick Start

```bash
git clone <repo-url> cryo && cd cryo
cp .env.example .env       # Set GEMINI_API_KEY
bash cryo.sh               # Builds image + starts all services + tails logs
open http://localhost:3000
```

Default superuser: `creator@cryo.in` / `creator@shivam0705`

## Two Interfaces

### Chat View (`/`)
Traditional single-thread chat with sidebar conversation history, slash commands, streaming responses, and file download cards.

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
- **Slash commands** in every node (`/pubmed`, `/protein`, `/drug`, `/report`, etc.)
- **Collapsible panels** — left (workspace list) and right (node list), draggable width
- **Multiple workspaces** — create, switch, rename, delete (max 10 per user, max 50 nodes per workspace)
- **Persistent** — nodes, positions, edges, conversations all saved to PostgreSQL
- **Messages reload** — refresh page → messages load from conversation history
- **Visual connections** — animated cyan arrows between branched nodes
- **Minimap** — overview of all nodes in corner
- **Pan/zoom** — infinite canvas with dot grid background

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    BROWSER (localhost:3000)                        │
│  React 19 · TypeScript · Tailwind 4 · Vite 6 · React Flow 12    │
│                                                                    │
│  ┌─ Chat View ──────────┐  ┌─ Workspace View ──────────────────┐ │
│  │ Sidebar + ChatPage   │  │ React Flow canvas                  │ │
│  │ Single conversation  │  │ ChatNode components (mini chats)   │ │
│  │ SlashMenu component  │  │ Branching, resize, pan/zoom        │ │
│  │ MessageBubble (md)   │  │ Workspace persistence (PG)         │ │
│  │ Bionic reading toggle│  │ Left panel: workspace list          │ │
│  └──────────────────────┘  │ Right panel: node list              │ │
│                             └────────────────────────────────────┘ │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP + SSE
┌───────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (localhost:8000)                 │
│                                                                    │
│  /api/auth/*          JWT auth (signup, login, me)                 │
│  /api/chat/*          Conversations, SSE streaming, tools list     │
│  /api/workspace/*     List, create, get, save, rename, delete      │
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
│  conversations      │  │  18 CRYO Tools:                          │
│  messages           │  │   pubmed_search · biorxiv_search         │
│  workspaces         │  │   fetch_citation · uniprot_lookup        │
│  workspace_nodes    │  │   pdb_search · chembl_search             │
│  workspace_edges    │  │   opentargets_search                     │
│  papers, genes      │  │   clinvar_lookup · ensembl_vep           │
│  proteins, drugs    │  │   compile_report · get_last_report       │
│  variants           │  │   generate_excel · generate_chart        │
│  knowledge_edges    │  │   verify_claim · analyze_image_vlm       │
│                     │  │   deep_research                          │
└─────────────────────┘  │   multi_agent_research                   │
                          │   scientific_skill                       │
┌─────────────────────┐  └──────────────────────────────────────────┘
│  cryo-data/         │
│  (bind-mounted)     │  ┌──────────────────────────────────────────┐
│  users/{uid}/       │  │   Digital Twin Engine                     │
│   conversations/    │  │   Human-GEM (12,931 rxns, 2,848 genes)   │
│    {cid}/           │  │   COBRApy FBA · CCLE GPR scaling         │
│     reports/*.html  │  │   ChEMBL + DGIdb drug target lookup      │
│     sources/*.json  │  │   GDSC2 IC50 validation                  │
│  ccle/*.parquet     │  │   SQLite drug cache (7-day TTL)          │
│  gdsc/*.csv         │  └──────────────────────────────────────────┘
│  models/human1/     │
└─────────────────────┘
```

## 18 Tools

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

## Report Engine v4

Reports are interactive HTML pages with:
- **Plotly.js charts** (bar, pie, line, scatter) — embedded via `:::chart` blocks
- **Mermaid.js diagrams** (pathway flowcharts) — via `:::diagram` blocks
- **Callout boxes** (info/warning/success/danger) — via `:::callout` blocks
- **Progress bars** (mutation frequencies, trial enrollment) — via `:::progress` blocks
- **Timelines** (drug approval history) — via `:::timeline` blocks
- **Sortable tables** — auto-parsed from markdown pipe tables
- **Sidebar TOC** with scroll-spy
- **Search bar** for in-report text search
- **Dark/light mode** toggle
- **Print button** (clean print layout via `@media print`)
- **Cover page** with CRYO branding and report ID

### Sample report output (EGFR in lung cancer)
```
34KB HTML · 2 Plotly charts · 4 Mermaid diagrams · 15 callouts
31 timeline items · 1 sortable table · 14 citation links
Cover page + TOC sidebar + search + dark/light toggle + print
```

## Slash Commands

Type `/` in any chat or workspace node:

| Command | What It Does |
|---------|-------------|
| `/pubmed <query>` | Search PubMed |
| `/protein <gene>` | Protein/gene lookup |
| `/drug <name>` | Drug/compound info |
| `/variant <rsid>` | Variant significance |
| `/vep <pos>` | Variant effect prediction |
| `/targets <disease>` | Disease-target associations |
| `/structure <id>` | 3D protein structures |
| `/report <topic>` | Generate interactive HTML report |
| `/chart <topic>` | Generate visualization |
| `/export <topic>` | Export to Excel |
| `/repurpose <disease>` | Drug repurposing |
| `/compare <A> <B>` | Compare genes/proteins/drugs |
| `/digital_twin <drug> [--cell_line <line>]` | Metabolic drug response simulation |
| `/simulate <drug> [--cell_line <line>]` | Alias for `/digital_twin` |

## Digital Twin

CRYO includes a genome-scale metabolic drug simulation engine built on [Human-GEM](https://github.com/SysBioChalmers/Human-GEM) (12,931 reactions, 2,848 genes) and COBRApy FBA.

```bash
/digital_twin glucose_inhibitor              # hardcoded — shows real biomass drop
/digital_twin metformin --cell_line HeLa     # Complex I → mitochondrial metabolism
/simulate 5-fluorouracil --cell_line HCT116  # TYMS target, GDSC IC50 = 15.0 μM
/digital_twin imatinib --cell_line MCF7      # ABL1/KIT/PDGFRB annotated; 0% Δbiomass (kinase, expected)
```

### What it does

1. **Drug target resolution** — ChEMBL REST (iterates all molecule variants for mechanism data) → DGIdb GraphQL → SQLite cache (7-day TTL)
2. **Cell line personalization** — CCLE expression data (49 cell lines, 19,215 genes) → GPR scaling: constrains reactions where all associated genes have TPM < 1.0
3. **Media contextualization** — CCLE available → `human1_minimal` + GPR; no CCLE → `cancer_warburg` (glucose-limited Warburg metabolism)
4. **FBA simulation** — baseline and perturbed flux balance analysis; 90% inhibition on drug-targeted reactions
5. **GDSC2 validation** — experimental IC50 (μM) lookup from 235,748 drug-cell pairs
6. **Citations** — Human-GEM + COBRApy always; ChEMBL/DGIdb/CCLE/GDSC conditionally

### `--cell_line` flag

`--cell_line` personalizes the metabolic model to a specific cancer cell line using its RNA expression profile from CCLE.

**Without `--cell_line`** — uses a generic cancer model:
```
/digital_twin metformin
→ cancer_warburg media (glucose-limited)
→ biomass baseline: 62.43  (generic Human1)
```

**With `--cell_line`** — constrains the model to what that cell line actually expresses:
```
/digital_twin metformin --cell_line MCF7
→ loads MCF7 RNA-seq from CCLE (19,215 genes, TPM values)
→ reactions where ALL driving genes have TPM < 1.0 → upper_bound set to 0.001
→ 1,212 reactions constrained for MCF7
→ biomass baseline: 8.06  (MCF7-specific, much more realistic)
→ human1_minimal media + GPR scaling
```

This means the simulation reflects which metabolic pathways are actually active in that cell line — a breast cancer cell (MCF7) has a very different metabolic profile from a colon cancer cell (HCT116), and `--cell_line` captures that difference.

**Supported cell lines (49):**
MCF7, HeLa, A549, HCT116, PC3, LNCaP, U87MG, HepG2, K562, Jurkat, T98G, MDA-MB-231, SK-BR-3, BT474, ZR75-1, PANC1, and 33 more.

If you pass an unknown cell line, GPR scaling is skipped gracefully and the simulation falls back to `cancer_warburg` media with no crash.

### Sample output — `/digital_twin 5-fluorouracil --cell_line HCT116`

```
Drug target: TYMS → 1 Human1 reaction
Cell line (HCT116): human1_minimal + GPR scaling
  → 1,104 reactions constrained (TPM < 1.0)
  → Biomass: 62.43 (generic) → 12.08 (HCT116-personalized)
Biomass change from 5-FU: 0.00% (TYMS not bottleneck in LP solution)
GDSC2 IC50: 15.04 μM  AUC: 0.830
Citations: Human-GEM, COBRApy, ChEMBL, CCLE, GDSC2 (5 total)
Report: report_*.html (26KB)
```

### Sample output — `/digital_twin imatinib --cell_line MCF7`

```
Drug targets: ABL1, PDGFRB, KIT, BCR (ChEMBL) + 72 interactions (DGIdb)
Human1 reactions found: 0  (signaling kinases, not in metabolic model)
Cell line (MCF7): human1_minimal + GPR scaling
  → 1,212 reactions constrained
  → Biomass: 62.43 → 8.06 (MCF7-personalized)
Biomass change from imatinib: 0.00% (expected — kinase not in model)
Citations: Human-GEM, COBRApy, ChEMBL, DGIdb, CCLE (5 total)
```

### Known scientific limitations

| Limitation | Root Cause | Impact |
|-----------|-----------|--------|
| TKIs always show 0% biomass change | ABL1/EGFR/PDGFRA are signaling kinases not encoded in Human1 | Annotation + GPR still work; no direct flux inhibition |
| Most drugs show 0% biomass change | FBA has degrees of freedom — solver routes around single enzyme blocks | Hardcoded targets (glucose/ATP synthase) and Complex I drugs show real effects |
| 275+ spurious flux shifts | LP degeneracy with 1,100+ constrained reactions = many equivalent optima | Reported shifts are noise; biomass % change is the reliable metric |

### Best drugs to test (show real metabolic effects)

| Drug | Target | Effect |
|------|--------|--------|
| `glucose_inhibitor` | MAR09034 (glucose exchange) | Hardcoded — biomass drops >10% |
| `atp_synthase_inhibitor` | MAR04137 (ATP synthase) | Hardcoded — ATP production blocked |
| `metformin` | MT-ND1 (Complex I) | Mitochondrial ETC target |
| `5-fluorouracil` | TYMS (thymidylate synthase) | Nucleotide synthesis |
| `methotrexate` | DHFR (dihydrofolate reductase) | Folate metabolism |
| `2-deoxyglucose` | HK1/HK2 (hexokinase) | Glycolysis entry point |

### Setup (one-time)

```bash
# Inside container — downloads GDSC2 (~10MB), creates SQLite drug cache
docker exec cryo-api-1 python /app/scripts/setup_digital_twin.py

# Preprocess CCLE data (requires manual download from depmap.org/portal/download/
# → OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv → place in /cryo-data/ccle/)
docker exec cryo-api-1 python /app/scripts/preprocess_ccle.py
```

**Supported cell lines (49, with CCLE data):**
MCF7, HeLa, A549, HCT116, PC3, LNCaP, U87MG, HepG2, K562, Jurkat, T98G, MDA-MB-231, SK-BR-3, BT474, ZR75-1, PANC1, and 33 more.

## Data

```
cryo-data/                              ← bind-mounted from host
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

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google AI Studio API key | **required** |
| `HERMES_MODEL` | LLM model | `gemini-3-pro-preview` |
| `HERMES_MAX_ITERATIONS` | Max tool loops | `15` |
| `CRYO_DATA_DIR` | Persistent data dir | `/cryo-data` |
| `CRYO_MAX_WORKSPACES_PER_USER` | Max workspaces | `10` |
| `CRYO_MAX_NODES_PER_WORKSPACE` | Max nodes | `50` |
| `CRYO_MAX_CONVERSATIONS_PER_USER` | Max conversation dirs | `50` |
| `POSTGRES_*` | Database config | `cryo:5432/cryo` |
| `JWT_SECRET` | JWT signing secret | **required** |

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
# 11 passed, 4 errors (test_api.py event loop errors — async fixture issue, not production)
```

## Project Structure

```
cryo/
├── api/                             # FastAPI backend
│   ├── routers/
│   │   ├── auth.py                  # JWT auth
│   │   ├── chat.py                  # SSE chat + conversations
│   │   ├── workspace.py             # Workspace CRUD + save
│   │   └── digital_twin.py          # Simulation REST endpoints
│   └── services/
│       ├── hermes_bridge.py         # Agent wrapper + slash dispatch
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
│   │   ├── ChatInput.tsx            # Slash command input
│   │   ├── ChatNode.tsx             # Workspace node (mini chat)
│   │   ├── ChatMessage.tsx          # Markdown + bionic reading
│   │   ├── SlashMenu.tsx            # Command dropdown
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
│   └── cryo_reports.py              # Report/chart/export tools
├── scripts/
│   ├── setup_digital_twin.py        # One-time data setup (GDSC + cache)
│   ├── preprocess_ccle.py           # CCLE CSV → parquet (49 cell lines)
│   └── verify_human1_exchanges.py   # Inspect Human1 reaction IDs
├── tests/
│   ├── test_digital_twin.py         # 8 integration tests
│   └── test_api.py                  # API endpoint tests
├── cryo-data/                       # Persistent data (bind-mounted)
├── db/schema.sql                    # PostgreSQL schema (20+ tables)
├── SOUL.md                          # Agent persona + :::block examples
└── docker-compose.yml               # 3 services: db, api, frontend
```

## License

MIT
