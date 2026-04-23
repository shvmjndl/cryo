# CRYO — Comprehensive Research Yielding Outcomes

AI-powered biology research platform with multi-canvas workspace. Mine literature, annotate proteins, repurpose drugs, interpret genomic variants, generate interactive research reports — branch and explore like a research flowchart.

Built on [Hermes Agent](https://github.com/nousresearch/hermes-agent) with 18 custom biology tools, powered by Gemini 3 Pro Preview.

## Quick Start

```bash
git clone <repo-url> cryo && cd cryo
cp .env.example .env       # Set GEMINI_API_KEY
docker compose up -d
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
│  /api/health          Health check                                 │
│                                                                    │
│  HermesBridge         Slash translation, conversation history,     │
│                       report format injection, per-request agent   │
│  Report Engine v4     Markdown → interactive HTML (Plotly, Mermaid, │
│                       callouts, timelines, progress bars, tables)  │
└──────────┬───────────────────────────────┬───────────────────────┘
           │                               │
┌──────────▼──────────┐      ┌─────────────▼──────────────────────┐
│   PostgreSQL 17     │      │   Hermes Agent (per-request)        │
│                     │      │   gemini-3-pro-preview · 32K tokens │
│  users, api_keys    │      │                                     │
│  conversations      │      │  18 CRYO Tools:                     │
│  messages           │      │   pubmed_search · biorxiv_search    │
│  workspaces         │      │   fetch_citation · uniprot_lookup   │
│  workspace_nodes    │      │   pdb_search · chembl_search        │
│  workspace_edges    │      │   opentargets_search                │
│  papers, genes      │      │   clinvar_lookup · ensembl_vep      │
│  proteins, drugs    │      │   compile_report · get_last_report  │
│  variants           │      │   generate_excel · generate_chart   │
│  knowledge_edges    │      │   verify_claim · analyze_image_vlm  │
│                     │      │   deep_research                     │
└─────────────────────┘      │   multi_agent_research              │
                              │   scientific_skill                  │
┌─────────────────────┐      └─────────────────────────────────────┘
│  cryo-data/         │
│  (bind-mounted)     │
│  users/{uid}/       │
│   conversations/    │
│    {cid}/           │
│     reports/*.html  │
│     sources/*.json  │
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
- **Progress bars** (mutation frequencies) — via `:::progress` blocks
- **Timelines** (drug approval history) — via `:::timeline` blocks
- **Sortable tables** — auto-parsed from markdown pipe tables
- **Sidebar TOC** with scroll-spy
- **Search bar** for in-report text search
- **Dark/light mode** toggle
- **Print button**
- **Cover page** with CRYO branding

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

## Data

```
cryo-data/                              ← bind-mounted from host
  └── users/{user_id}/
      └── conversations/                ← max 50 per user
          └── {conversation_id}/
              ├── reports/*.html
              └── sources/*.json        ← raw markdown for editing
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
docker compose up -d              # Start all (db, api, frontend)
docker compose logs api -f        # Watch tool calls
docker compose restart api        # Reload after .env changes
bash cryo.sh                      # Shortcut: down + up + logs
```

## Project Structure

```
cryo/
├── api/                             # FastAPI backend
│   ├── routers/auth.py              # JWT auth
│   ├── routers/chat.py              # SSE chat + conversations
│   ├── routers/workspace.py         # Workspace CRUD + save
│   └── services/
│       ├── hermes_bridge.py         # Agent wrapper
│       └── report_engine.py         # v4 HTML report engine
├── frontend/src/
│   ├── components/
│   │   ├── ChatInput.tsx            # Slash command input
│   │   ├── ChatNode.tsx             # Workspace node (mini chat)
│   │   ├── MessageBubble.tsx        # Markdown + bionic reading
│   │   ├── SlashMenu.tsx            # Command dropdown
│   │   └── Sidebar.tsx              # Chat view sidebar
│   └── pages/
│       ├── ChatPage.tsx             # Traditional chat
│       └── WorkspacePage.tsx        # Multi-canvas workspace
├── hermes-agent/tools/              # 11 CRYO tool files
├── cryo-data/                       # Persistent reports (bind-mounted)
├── db/schema.sql                    # PostgreSQL schema (20+ tables)
├── integrations/                    # gpt-researcher, Co-Sight, etc.
├── SOUL.md                          # Agent persona + :::block examples
└── docker-compose.yml               # 3 services
```

## License

MIT
