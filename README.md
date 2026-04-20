# CRYO Architecture

**Comprehensive Research Yielding Outcomes** — AI-powered biology research platform.

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         BROWSER (localhost:3000)                      │
│  React 19 + TypeScript + Tailwind 4 + Vite 6                        │
│  ┌──────────┐ ┌──────────────────────┐ ┌──────────────────────────┐  │
│  │ AuthPage │ │     ChatPage         │ │     SlashMenu            │  │
│  │ Login/   │ │ SSE Streaming        │ │ 14 biology commands      │  │
│  │ Signup   │ │ Markdown rendering   │ │ /pubmed /protein /drug   │  │
│  └──────────┘ │ Tool exec indicators │ │ /variant /report /chart  │  │
│               │ File download links  │ │ Arrow nav, fuzzy filter  │  │
│               └──────────────────────┘ └──────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTP + SSE (Vite proxy → api:8000)
┌────────────────────────────▼─────────────────────────────────────────┐
│                    FastAPI Backend (localhost:8000)                    │
│  Python 3.12 + SQLAlchemy 2 + asyncpg                                │
│                                                                       │
│  ┌─ Routers ──────────────┐  ┌─ Services ─────────────────────────┐  │
│  │ /api/auth/*            │  │ HermesBridge                       │  │
│  │   POST /signup         │  │   - Slash command translation      │  │
│  │   POST /login          │  │   - AIAgent lifecycle management   │  │
│  │   GET  /me             │  │   - SSE streaming with tool events │  │
│  │                        │  │   - Error logging (structured)     │  │
│  │ /api/chat/*            │  │                                    │  │
│  │   GET  /conversations  │  │ Logging (cryo.* loggers)           │  │
│  │   GET  /messages       │  │   - All tool calls logged          │  │
│  │   POST /send (SSE)     │  │   - All errors with tracebacks     │  │
│  │   GET  /tools          │  │   - Structured format              │  │
│  │                        │  └────────────────────────────────────┘  │
│  │ /api/reports/{file}    │                                          │
│  │   Serves PDF/Excel/PNG │                                          │
│  │                        │                                          │
│  │ /api/health            │                                          │
│  └────────────────────────┘                                          │
│                                                                       │
│  ┌─ Auth ─────────────────┐  ┌─ Config ──────────────────────────┐  │
│  │ JWT (HS256)            │  │ All from .env                     │  │
│  │ bcrypt password hash   │  │ GEMINI_API_KEY                    │  │
│  │ Bearer token auth      │  │ HERMES_MODEL / HERMES_VLM_MODEL   │  │
│  └────────────────────────┘  │ POSTGRES_* / JWT_* / API_*        │  │
│                               └──────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌──────────────────────┐          ┌──────────────────────────────────┐
│   PostgreSQL 17      │          │      Hermes Agent (in-process)    │
│   (localhost:5432)   │          │                                    │
│                      │          │  AIAgent class from run_agent.py   │
│  20+ tables:         │          │  Model: gemini-2.5-flash          │
│  - users, api_keys   │          │                                    │
│  - conversations     │          │  ┌─ CRYO Tool Registry ─────────┐ │
│  - messages          │          │  │                               │ │
│  - tool_executions   │          │  │  cryo_literature toolset     │ │
│  - papers            │          │  │    pubmed_search              │ │
│  - genes, proteins   │          │  │    biorxiv_search             │ │
│  - drugs, diseases   │          │  │                               │ │
│  - variants          │          │  │  cryo_protein toolset        │ │
│  - knowledge_edges   │          │  │    uniprot_lookup             │ │
│  - activity_log      │          │  │    pdb_search                 │ │
│                      │          │  │                               │ │
│  Extensions:         │          │  │  cryo_drug toolset           │ │
│  - uuid-ossp         │          │  │    chembl_search              │ │
│  - pg_trgm           │          │  │    opentargets_search         │ │
│  - btree_gin         │          │  │                               │ │
└──────────────────────┘          │  │  cryo_variant toolset        │ │
                                  │  │    clinvar_lookup             │ │
                                  │  │    ensembl_vep                │ │
                                  │  │                               │ │
                                  │  │  cryo_reports toolset        │ │
                                  │  │    generate_pdf               │ │
                                  │  │    generate_excel             │ │
                                  │  │    generate_chart             │ │
                                  │  │                               │ │
                                  │  │  cryo_vlm toolset            │ │
                                  │  │    analyze_image_vlm          │ │
                                  │  └───────────────────────────────┘ │
                                  └────────────────────────────────────┘

```

## Agent Tool Flow

When a user sends a message, the agent autonomously decides which tools to use:

```
User: "/variant rs28934578"
  │
  ▼ (slash translation)
"Look up clinical significance of variant: rs28934578. Use the clinvar_lookup tool."
  │
  ▼ (Hermes AIAgent)
  1. Agent receives prompt + list of available tools
  2. Gemini LLM decides: call clinvar_lookup(query="rs28934578")
  3. Tool executes → hits NCBI ClinVar API → returns JSON
  4. Agent reads result, may call more tools (ensembl_vep, pubmed_search)
  5. Agent synthesizes all data → generates final response
  6. If user asked for report: calls generate_pdf with gathered data
  │
  ▼ (SSE stream back to frontend)
  Events: tool_start → tool_result → delta tokens → done
```

## External APIs (All Free, No Keys Required)

| API | Base URL | Used For |
|-----|----------|----------|
| NCBI E-utilities | eutils.ncbi.nlm.nih.gov | PubMed search, ClinVar lookup |
| UniProt REST | rest.uniprot.org | Protein/gene info, GO terms, domains |
| PDB/RCSB | data.rcsb.org + search.rcsb.org | 3D protein structures |
| ChEMBL | www.ebi.ac.uk/chembl/api | Drug/compound search, targets |
| OpenTargets GraphQL | api.platform.opentargets.org | Disease-target associations |
| Ensembl VEP | rest.ensembl.org | Variant effect prediction |
| bioRxiv API | api.biorxiv.org | Preprint search |

## External APIs (Key Required)

| API | Env Var | Used For |
|-----|---------|----------|
| Gemini (LLM) | GEMINI_API_KEY | Chat responses, reasoning |
| Gemini (VLM) | GEMINI_API_KEY | Image/figure analysis |

## Database Schema Map

```
AUTH                    CHAT                    BIOLOGY MODULES
┌─────────┐            ┌───────────────┐        ┌──────────────────┐
│ users    │──┐         │conversations  │        │ LITERATURE       │
│ api_keys │  │    ┌───▶│ messages      │        │  papers          │
└─────────┘  │    │    │ tool_executions│        │  user_papers     │
             │    │    └───────────────┘        │  paper_relations  │
             ├────┤                              └──────────────────┘
             │    │    ┌───────────────┐        ┌──────────────────┐
             │    └───▶│ projects      │        │ PROTEINS         │
             │         └───────────────┘        │  genes           │
             │                                   │  proteins        │
             │                                   │  protein_inter.  │
             │                                   └──────────────────┘
             │                                   ┌──────────────────┐
             │                                   │ DRUGS            │
             │                                   │  drugs           │
             │                                   │  drug_targets    │
             │                                   │  diseases        │
             │                                   │  repurpose_cand. │
             │                                   └──────────────────┘
             │                                   ┌──────────────────┐
             │                                   │ VARIANTS         │
             │                                   │  variants        │
             │                                   │  vcf_analyses    │
             │                                   │  vcf_var_entries │
             │                                   └──────────────────┘
             │
             │         ┌─────────────────────┐
             └────────▶│ CROSS-MODULE        │
                       │  knowledge_edges    │
                       │  activity_log       │
                       └─────────────────────┘
```

## File Structure

```
cryo/
├── .env                              # All configuration
├── .env.example                      # Template
├── SOUL.md                           # Agent persona (biology researcher)
├── ARCHITECTURE.md                   # This file
├── docker-compose.yml                # 3 services: db, api, frontend
│
├── api/                              # FastAPI backend
│   ├── main.py                       # App entry + report file serving
│   ├── requirements.txt              # Pinned Python deps
│   ├── core/
│   │   ├── config.py                 # Settings from .env
│   │   ├── database.py               # Async SQLAlchemy
│   │   ├── auth.py                   # JWT + bcrypt
│   │   └── logging_config.py         # Structured logging
│   ├── models/
│   │   ├── user.py                   # User ORM
│   │   ├── conversation.py           # Conversation + Message ORM
│   │   └── project.py               # Project ORM
│   ├── routers/
│   │   ├── auth.py                   # /signup, /login, /me
│   │   └── chat.py                   # SSE chat, conversations CRUD
│   └── services/
│       └── hermes_bridge.py          # Agent wrapper + slash translation
│
├── frontend/                         # React UI
│   ├── package.json                  # Pinned Node deps
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                   # Router (auth/chat)
│       ├── lib/api.ts                # API client + SSE streaming
│       ├── hooks/useAuth.ts          # Auth state
│       ├── components/
│       │   ├── ChatInput.tsx         # Input + "/" slash detection
│       │   ├── SlashMenu.tsx         # Command dropdown (14 tools)
│       │   ├── MessageBubble.tsx     # User/assistant/tool messages
│       │   └── Sidebar.tsx           # Conversation list
│       └── pages/
│           ├── AuthPage.tsx          # Login/signup
│           └── ChatPage.tsx          # Main chat interface
│
├── db/
│   └── schema.sql                    # Full PostgreSQL schema (20+ tables)
│
├── docker/
│   ├── Dockerfile.api                # python:3.12.13-slim-bookworm
│   └── Dockerfile.frontend           # node:22.15.0-alpine3.21
│
└── hermes-agent/                     # Hermes Agent (modifiable)
    ├── run_agent.py                  # AIAgent class
    ├── tools/
    │   ├── registry.py               # Tool registration system
    │   ├── cryo_literature.py        # PubMed + bioRxiv tools
    │   ├── cryo_protein.py           # UniProt + PDB tools
    │   ├── cryo_drug.py              # ChEMBL + OpenTargets tools
    │   ├── cryo_variant.py           # ClinVar + Ensembl VEP tools
    │   ├── cryo_reports.py           # PDF + Excel + Chart generation
    │   └── cryo_vlm.py              # Gemini Vision analysis
    └── toolsets.py                   # Toolset definitions
```

## Hermes Tool Registration Pattern

Every CRYO tool follows this pattern:

```python
# hermes-agent/tools/cryo_*.py
from tools.registry import registry

def _handler(args: dict, **kw) -> str:
    # Always returns JSON string
    return json.dumps({"result": data})

registry.register(
    name="tool_name",
    toolset="cryo_category",
    schema={...},              # OpenAI function calling format
    handler=_handler,
    check_fn=lambda: True,    # availability check
    emoji="🧬",
)
```

Tools are auto-discovered by Hermes at startup via AST scanning of `tools/*.py`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| GEMINI_API_KEY | Google AI Studio API key | required |
| HERMES_MODEL | LLM model for chat | gemini-2.5-flash |
| HERMES_VLM_MODEL | Vision model for image analysis | gemini-2.5-flash |
| HERMES_PROVIDER | LLM provider | gemini |
| HERMES_MAX_ITERATIONS | Max tool-calling loops per turn | 90 |
| POSTGRES_HOST | Database host | localhost |
| POSTGRES_PORT | Database port | 5432 |
| POSTGRES_DB | Database name | cryo |
| POSTGRES_USER | Database user | cryo |
| POSTGRES_PASSWORD | Database password | required |
| API_HOST | API bind address | 0.0.0.0 |
| API_PORT | API port | 8000 |
| API_SECRET_KEY | API secret | required |
| API_CORS_ORIGINS | Allowed origins | localhost:3000 |
| JWT_SECRET | JWT signing secret | required |
| JWT_ALGORITHM | JWT algorithm | HS256 |
| JWT_EXPIRE_MINUTES | Token TTL | 1440 |
| CRYO_REPORTS_DIR | Generated files directory | /tmp/cryo-reports |
| LOG_LEVEL | Logging level | INFO |

## Docker Services

```yaml
db:        postgres:17.5-alpine3.22    :5432  (healthcheck: pg_isready)
api:       python:3.12.13-slim         :8000  (healthcheck: /api/health)
frontend:  node:22.15.0-alpine3.21     :3000  (healthcheck: wget spider)
```

Run: `docker compose up -d`
