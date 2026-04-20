# CRYO — Comprehensive Research Yielding Outcomes

AI-powered biology research platform. Mine literature, annotate proteins, repurpose drugs, interpret genomic variants, generate interactive research reports — all from one chat interface.

Built on [Hermes Agent](https://github.com/nousresearch/hermes-agent) with 18 custom biology tools, powered by Gemini 3 Pro Preview.

## Quick Start

```bash
git clone <repo-url> cryo && cd cryo
cp .env.example .env       # Set GEMINI_API_KEY
docker compose up -d
open http://localhost:3000
```

Default superuser: `creator@cryo.in` / `creator@shivam0705`

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       BROWSER (localhost:3000)                        │
│  React 19 · TypeScript · Tailwind 4 · Vite 6                        │
│  ┌────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  Auth Page  │  │    Chat Page     │  │     Slash Menu           │  │
│  │  Login/     │  │  SSE streaming   │  │  14 commands with icons  │  │
│  │  Signup     │  │  Markdown render │  │  /pubmed /protein /drug  │  │
│  └────────────┘  │  File downloads  │  │  /variant /report /chart │  │
│                   │  Tool indicators │  │  Arrow nav, fuzzy filter │  │
│                   └──────────────────┘  └──────────────────────────┘  │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ HTTP + SSE (Vite proxy → api:8000)
┌───────────────────────────▼──────────────────────────────────────────┐
│                    FastAPI Backend (localhost:8000)                    │
│                                                                       │
│  ┌─ Routers ──────────────┐  ┌─ Services ────────────────────────┐   │
│  │ /api/auth/*             │  │ HermesBridge                      │   │
│  │   POST /signup          │  │   Slash command → prompt translate │   │
│  │   POST /login           │  │   Conversation history from PG    │   │
│  │   GET  /me              │  │   :::block format injection       │   │
│  │                         │  │   SSE streaming with tool events  │   │
│  │ /api/chat/*             │  │                                   │   │
│  │   GET  /conversations   │  │ Report Engine v4                  │   │
│  │   GET  /messages        │  │   Markdown parser (:::blocks)     │   │
│  │   POST /send (SSE)      │  │   Plotly.js chart builder         │   │
│  │   GET  /tools           │  │   Mermaid.js diagram renderer     │   │
│  │                         │  │   Sortable table generator        │   │
│  │ /api/reports/{file}     │  │   Callout/progress/timeline       │   │
│  │   Serves HTML/Excel/PNG │  │   Full HTML template assembly     │   │
│  │                         │  │                                   │   │
│  │ /api/health             │  │ Structured Logging (cryo.*)       │   │
│  └─────────────────────────┘  └───────────────────────────────────┘   │
│                                                                       │
│  ┌─ Auth ───────────┐  ┌─ Config ─────────────────────────────────┐  │
│  │ JWT (HS256)       │  │ All from .env                            │  │
│  │ bcrypt passwords  │  │ GEMINI_API_KEY · HERMES_MODEL            │  │
│  │ Bearer tokens     │  │ CRYO_DATA_DIR · POSTGRES_* · JWT_*       │  │
│  └───────────────────┘  └─────────────────────────────────────────┘  │
└──────────┬──────────────────────────────────┬────────────────────────┘
           │                                  │
┌──────────▼──────────┐         ┌─────────────▼───────────────────────┐
│   PostgreSQL 17     │         │   Hermes Agent (in-process)          │
│   20+ tables        │         │   Model: gemini-3-pro-preview        │
│                     │         │   Max tokens: 32K · Iterations: 15   │
│  Auth & Chat:       │         │                                      │
│   users, api_keys   │         │  ┌─ 18 CRYO Tools (9 toolsets) ───┐ │
│   conversations     │         │  │                                 │ │
│   messages          │         │  │  Literature:                    │ │
│                     │         │  │   pubmed_search · biorxiv_search│ │
│  Biology Modules:   │         │  │   fetch_citation                │ │
│   papers            │         │  │                                 │ │
│   genes, proteins   │         │  │  Protein:                      │ │
│   drugs, diseases   │         │  │   uniprot_lookup · pdb_search   │ │
│   variants          │         │  │                                 │ │
│   drug_targets      │         │  │  Drug:                         │ │
│   repurpose_cand.   │         │  │   chembl_search                │ │
│                     │         │  │   opentargets_search            │ │
│  Cross-Module:      │         │  │                                 │ │
│   knowledge_edges   │         │  │  Variant:                      │ │
│   activity_log      │         │  │   clinvar_lookup · ensembl_vep  │ │
│                     │         │  │                                 │ │
│  Extensions:        │         │  │  Reports:                      │ │
│   uuid-ossp         │         │  │   compile_report · get_last_   │ │
│   pg_trgm           │         │  │   report · generate_excel ·    │ │
│   btree_gin         │         │  │   generate_chart               │ │
│                     │         │  │                                 │ │
└─────────────────────┘         │  │  Advanced:                     │ │
                                │  │   verify_claim (Co-Sight)       │ │
┌─────────────────────┐         │  │   analyze_image_vlm             │ │
│  cryo-data/         │         │  │   deep_research                 │ │
│  (bind-mounted)     │         │  │   multi_agent_research          │ │
│                     │         │  │   scientific_skill              │ │
│  users/{uid}/       │         │  └─────────────────────────────────┘ │
│   conversations/    │         │                                      │
│    {cid}/           │         │  Conversation history from PG ──────┐│
│     reports/*.html  │         │  (run_conversation with history)    ││
│     sources/*.json  │         └────────────────────────────────────┘│
│                     │                                                │
│  Max 50 convos/user │                                                │
│  Auto-cleanup       │                                                │
└─────────────────────┘                                                │
```

## How It Works

### 1. Chat Query
User types `/report EGFR mutations in lung cancer` in the browser.

### 2. Slash Translation
`HermesBridge` translates the slash command into a detailed prompt with `:::block` format instructions (charts, diagrams, callouts, timelines).

### 3. Conversation Context
All prior messages are loaded from PostgreSQL and passed to Hermes via `run_conversation(conversation_history=...)`. The agent has full context across turns.

### 4. Tool Chaining
The agent autonomously picks tools:
```
pubmed_search("EGFR TKI resistance")     → real NCBI API
opentargets_search("EGFR lung cancer")   → real OpenTargets GraphQL
fetch_citation("EGFR NSCLC review")      → real CrossRef API
compile_report(title, content, citations) → report engine v4
```

### 5. Report Engine v4
The `compile_report` tool receives 2000+ words of markdown with special blocks:
```
:::chart {"type":"bar","title":"Mutation Freq","labels":["EGFR","BRAF"],"values":[15,8]} :::
:::diagram graph TD A[Gene] --> B[Protein] --> C[Cancer] :::
:::callout success  Key FDA approval finding here  :::
:::timeline  - **2015**: Osimertinib approved  :::
:::progress  - EGFR: 15% (NSCLC)  :::
| Drug | Target | Phase |   ← markdown tables
```

The report engine parses these into:
- **Plotly.js interactive charts** (hover, zoom, pan)
- **Mermaid.js pathway diagrams** (flowcharts, sequence diagrams)
- **Sortable tables** (click column headers)
- **Callout boxes** (info/warning/success/danger with icons)
- **Progress bars** (animated percentage comparisons)
- **Timelines** (chronological event display)

Output: standalone HTML with sidebar TOC, search bar, dark/light toggle, print button.

### 6. Report Editing
User: "add more citations" → Agent calls `get_last_report` (reads raw markdown from `cryo-data/sources/`) → modifies content → calls `compile_report` again → updated HTML.

### 7. Data Persistence
- **PostgreSQL**: users, conversations, messages (source of truth)
- **cryo-data/**: generated reports + raw sources (per user/conversation, bind-mounted)
- **Hermes SQLite**: not used — we pass history from PG directly

## All 18 Tools (9 Toolsets)

| Tool | Toolset | Source | What It Does |
|------|---------|--------|-------------|
| `pubmed_search` | cryo_literature | NCBI E-utilities | Search papers, returns titles/authors/abstracts/PMIDs |
| `biorxiv_search` | cryo_literature | bioRxiv API | Search preprints |
| `fetch_citation` | cryo_literature | CrossRef + PubMed | APA/MLA/Chicago citations with DOIs |
| `uniprot_lookup` | cryo_protein | UniProt REST | Protein function, domains, GO terms, PDB IDs |
| `pdb_search` | cryo_protein | RCSB PDB | 3D structures, resolution, method |
| `chembl_search` | cryo_drug | ChEMBL REST | Drug properties, SMILES, approval status |
| `opentargets_search` | cryo_drug | OpenTargets GraphQL | Disease-target associations |
| `clinvar_lookup` | cryo_variant | ClinVar/NCBI | Variant pathogenicity, conditions |
| `ensembl_vep` | cryo_variant | Ensembl REST | SIFT/PolyPhen scores, consequences |
| `compile_report` | cryo_reports | Report Engine v4 | Markdown → interactive HTML with charts/diagrams |
| `get_last_report` | cryo_reports | Disk (cryo-data/) | Retrieve raw markdown for report editing |
| `generate_excel` | cryo_reports | openpyxl | Multi-sheet Excel spreadsheets |
| `generate_chart` | cryo_reports | matplotlib | Standalone chart PNGs |
| `verify_claim` | cryo_cosight | Multi-source | Cross-check claims (PubMed + OpenTargets + CrossRef) |
| `analyze_image_vlm` | cryo_vlm | Gemini Vision | Analyze microscopy, gels, structures |
| `deep_research` | cryo_deep_research | gpt-researcher | Autonomous multi-source research |
| `multi_agent_research` | cryo_deep_research | open_deep_research | Supervisor-researcher pattern |
| `scientific_skill` | cryo_scientific_skills | 133 skill packs | Biopython, DeepChem, ESM, MedChem, etc. |

All biology tools hit free public APIs — no extra keys needed beyond `GEMINI_API_KEY`.

## Slash Commands

| Command | What It Does |
|---------|-------------|
| `/pubmed <query>` | Search PubMed literature |
| `/protein <gene>` | Protein/gene deep lookup |
| `/drug <name>` | Drug/compound info |
| `/variant <rsid>` | Variant clinical significance |
| `/vep <chr:pos:ref:alt>` | Variant effect prediction |
| `/targets <disease>` | Disease-target associations |
| `/structure <pdb_id>` | 3D protein structures |
| `/biorxiv <query>` | Preprint search |
| `/report <topic>` | Generate interactive HTML report |
| `/chart <topic>` | Generate visualization |
| `/export <topic>` | Export data to Excel |
| `/repurpose <disease>` | Drug repurposing analysis |
| `/pathway <name>` | Biological pathway exploration |
| `/compare <A> <B>` | Compare genes/proteins/drugs |

## Proven Report Pipeline

Tested `/report CAR-T cell therapy` with `gemini-3-pro-preview`:

```
21:36:32  pubmed_search          → "CAR-T solid tumors 2025-2026"
21:36:37  biorxiv_search         → "CAR-T solid tumor"
21:36:59  fetch_citation         → 8 APA citations
21:37:53  compile_report         → 18,070 chars, 8 sections, 8 citations
21:37:53  Report Engine v4       → 44.5KB interactive HTML
```

Report features rendered: Mermaid diagrams, Plotly charts, callout boxes, timelines, progress bars, sortable tables, sidebar TOC, search, dark/light toggle.

## Data Directory

```
cryo-data/                              ← bind-mounted from host
  └── users/{user_id}/
      └── conversations/                ← max 50 per user, oldest auto-deleted
          └── {conversation_id}/
              ├── reports/*.html        ← generated interactive reports
              └── sources/*.json        ← raw markdown for editing
```

## Project Structure

```
cryo/
├── .env                                # All configuration
├── SOUL.md                             # Agent persona + :::block examples
├── docker-compose.yml                  # 3 services (db, api, frontend)
├── test_queries.md                     # 30+ graded test queries
│
├── api/
│   ├── main.py                         # FastAPI app + report file serving
│   ├── requirements.txt                # Pinned Python deps
│   ├── core/                           # Config, DB, auth, logging
│   ├── models/                         # SQLAlchemy ORM
│   ├── routers/                        # Auth + chat endpoints
│   └── services/
│       ├── hermes_bridge.py            # Slash translate + AIAgent wrapper
│       └── report_engine.py            # v4: markdown → interactive HTML
│
├── frontend/src/
│   ├── components/                     # ChatInput, SlashMenu, MessageBubble, Sidebar
│   ├── pages/                          # AuthPage, ChatPage
│   └── styles/globals.css              # CRYO dark theme
│
├── hermes-agent/tools/                 # 11 CRYO tool files (auto-discovered)
│   ├── cryo_literature.py              # pubmed, biorxiv, citations
│   ├── cryo_protein.py                 # uniprot, pdb
│   ├── cryo_drug.py                    # chembl, opentargets
│   ├── cryo_variant.py                 # clinvar, ensembl vep
│   ├── cryo_reports.py                 # compile_report, get_last_report, excel, chart
│   ├── cryo_cosight.py                 # verify_claim
│   ├── cryo_vlm.py                     # analyze_image_vlm
│   ├── cryo_citation.py                # fetch_citation
│   ├── cryo_deep_research.py           # deep_research
│   ├── cryo_open_deep_research.py      # multi_agent_research
│   └── cryo_scientific_skills.py       # scientific_skill
│
├── cryo-data/                          # Persistent data (bind-mounted)
├── db/schema.sql                       # PostgreSQL schema (20+ tables)
├── docker/                             # Dockerfiles (api + frontend)
└── integrations/                       # gpt-researcher, Co-Sight, open_deep_research, scientific-agent-skills
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google AI Studio API key | **required** |
| `HERMES_MODEL` | LLM model | `gemini-3-pro-preview` |
| `HERMES_PROVIDER` | LLM provider | `gemini` |
| `HERMES_MAX_ITERATIONS` | Max tool loops per turn | `15` |
| `CRYO_DATA_DIR` | Persistent data directory | `/cryo-data` |
| `CRYO_MAX_CONVERSATIONS_PER_USER` | Max conversation dirs per user | `50` |
| `POSTGRES_*` | Database config | `cryo:5432/cryo` |
| `JWT_SECRET` | JWT signing secret (32+ bytes for prod) | **required** |
| `LOG_LEVEL` | Logging level | `INFO` |

## Docker

```yaml
db:        postgres:17.5-alpine3.22     :5432
api:       python:3.12.13-slim          :8000   (hot-reload, structured logging)
frontend:  node:22.15.0-alpine3.21      :3000   (Vite dev server)
```

```bash
docker compose up -d              # Start all
docker compose logs api -f        # Watch tool calls
docker compose restart api        # Reload after .env changes
```

## TODO

### High Priority
- [ ] Add retry with exponential backoff on all external API calls
- [ ] Wire tool_executions table — log every tool call to PostgreSQL
- [ ] Production JWT secret, rate limiting
- [ ] Improve agent's use of :::chart blocks (more numeric data extraction)

### Medium Priority
- [ ] VCF file upload + variant analysis pipeline
- [ ] Knowledge graph auto-population from tool results
- [ ] Paper bookmarking to user_papers table
- [ ] Drug repurposing scoring engine
- [ ] User settings page (model selection, citation style)
- [ ] Better chat UI status messages during tool execution

### Integrations
- [ ] Wire gpt-researcher (needs TAVILY_API_KEY)
- [ ] Wire Co-Sight native module
- [ ] Wire open_deep_research LangGraph pipeline
- [ ] Port scientific-agent-skills as native tools
- [ ] Mol*/py3Dmol for protein 3D visualization
- [ ] Plotly/Dash for interactive dashboards

### Production
- [ ] Multi-stage Dockerfiles
- [ ] Nginx + production Vite build
- [ ] Alembic database migrations
- [ ] CI/CD pipeline
- [ ] Monitoring (Prometheus/Grafana)
- [ ] HTTPS

### Research Ideas
- [ ] Autonomous hypothesis generation
- [ ] Batch variant analysis (1000+ VCF)
- [ ] Literature contradiction detector
- [ ] Clinical trial matcher (ClinicalTrials.gov API)
- [ ] Protein interaction network visualization

## License

MIT
