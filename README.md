# CRYO — Comprehensive Research Yielding Outcomes

AI-powered biology research platform. Mine literature, annotate proteins, repurpose drugs, interpret genomic variants, generate publication-quality reports — all from one chat interface.

Built on [Hermes Agent](https://github.com/nousresearch/hermes-agent) with 17 custom biology tools, powered by Gemini 3 Flash Preview.

## Quick Start

```bash
# 1. Clone
git clone <repo-url> cryo && cd cryo

# 2. Configure
cp .env.example .env
# Edit .env — set GEMINI_API_KEY (required)

# 3. Run
docker compose up -d

# 4. Open
open http://localhost:3000
```

Default superuser: `creator@cryo.in` / `creator@shivam0705` (role: admin)

## What It Does

Type natural language or use slash commands:

| Command | What It Does | Tools Invoked |
|---------|-------------|---------------|
| `/pubmed CRISPR glioblastoma` | Search PubMed literature | pubmed_search |
| `/protein TP53` | Protein/gene deep lookup | uniprot_lookup |
| `/drug temozolomide` | Drug/compound info | chembl_search |
| `/variant rs28934578` | Variant clinical significance | clinvar_lookup |
| `/vep 17:7675088:C:T` | Variant effect prediction | ensembl_vep |
| `/targets Alzheimer's disease` | Disease-target associations | opentargets_search |
| `/structure EGFR` | 3D protein structures | pdb_search |
| `/biorxiv single-cell RNA-seq` | Preprint search | biorxiv_search |
| `/report <topic>` | Generate PDF research report | opentargets → pubmed → verify_claim → fetch_citation → generate_pdf |
| `/chart <topic>` | Generate data visualization | tool query → generate_chart |
| `/export <topic>` | Export data to Excel | tool query → generate_excel |
| `/repurpose <disease>` | Drug repurposing analysis | chembl + opentargets |
| `/pathway <pathway>` | Biological pathway exploration | knowledge-based |
| `/compare <A> <B>` | Compare genes/proteins/drugs | multi-tool |

The agent autonomously chains tools. Example `/report` flow:
```
opentargets_search → pubmed_search → verify_claim (Co-Sight) → fetch_citation → generate_pdf
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BROWSER (localhost:3000)                       │
│  React 19 + TypeScript + Tailwind 4 + Vite 6                    │
│  Chat UI · Slash commands · SSE streaming · File downloads       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                 FastAPI Backend (localhost:8000)                   │
│  HermesBridge · JWT Auth · Structured Logging · Report Serving   │
└────────────┬───────────────────────────────────┬────────────────┘
             │                                   │
┌────────────▼──────────┐          ┌─────────────▼────────────────┐
│   PostgreSQL 17       │          │   Hermes Agent (in-process)   │
│   20+ tables          │          │   gemini-3-flash-preview      │
│   4 biology modules   │          │   17 CRYO tools (9 toolsets)  │
│   Knowledge graph     │          │   4 integrations              │
└───────────────────────┘          └──────────────────────────────┘
```

## All 17 Tools (9 Toolsets)

### Biology Tools (hit real public APIs — no keys needed)

| Tool | Toolset | API | What It Returns |
|------|---------|-----|-----------------|
| `pubmed_search` | cryo_literature | NCBI E-utilities | Papers with titles, authors, abstracts, PMIDs |
| `biorxiv_search` | cryo_literature | bioRxiv API | Preprints with abstracts |
| `fetch_citation` | cryo_literature | CrossRef + PubMed | Formatted citations (APA/MLA/Chicago/Vancouver) |
| `uniprot_lookup` | cryo_protein | UniProt REST | Protein function, domains, GO terms, PDB IDs, diseases |
| `pdb_search` | cryo_protein | RCSB PDB | 3D structures, resolution, experimental method |
| `chembl_search` | cryo_drug | ChEMBL REST | Drug properties, SMILES, approval status, targets |
| `opentargets_search` | cryo_drug | OpenTargets GraphQL | Disease-target associations with evidence |
| `clinvar_lookup` | cryo_variant | ClinVar/NCBI | Variant pathogenicity, conditions, review status |
| `ensembl_vep` | cryo_variant | Ensembl REST | Consequence type, SIFT/PolyPhen scores, transcripts |

### Report Generation Tools

| Tool | Toolset | Library | Output |
|------|---------|---------|--------|
| `generate_pdf` | cryo_reports | reportlab 4.4.0 | Styled PDF with cover page, sections, tables |
| `generate_excel` | cryo_reports | openpyxl 3.1.5 | Multi-sheet Excel with styled headers |
| `generate_chart` | cryo_reports | matplotlib 3.10.3 | Bar, pie, line, scatter, heatmap (CRYO dark theme) |

### Advanced Tools

| Tool | Toolset | Source | What It Does |
|------|---------|--------|-------------|
| `analyze_image_vlm` | cryo_vlm | Gemini Vision API | Analyze microscopy, gels, structures, figures |
| `verify_claim` | cryo_cosight | Co-Sight (multi-source) | Cross-check claims across PubMed + OpenTargets + CrossRef, returns confidence score |
| `deep_research` | cryo_deep_research | gpt-researcher | Autonomous multi-source deep research reports |
| `multi_agent_research` | cryo_deep_research | open_deep_research | Supervisor-researcher multi-agent research |
| `scientific_skill` | cryo_scientific_skills | scientific-agent-skills | 14 domain skill packs (biopython, deepchem, esm, etc.) |

### Hermes Tool Registration Pattern

```python
# hermes-agent/tools/cryo_*.py — auto-discovered at startup
from tools.registry import registry

def _handler(args: dict, **kw) -> str:
    return json.dumps({"result": data})  # Always return JSON string

registry.register(
    name="tool_name",
    toolset="cryo_category",
    schema={...},              # OpenAI function calling format
    handler=_handler,
    check_fn=lambda: True,
    emoji="🧬",
)
```

## Database Schema (20+ tables)

```
AUTH                    CHAT                    BIOLOGY MODULES
┌─────────┐            ┌───────────────┐       ┌──────────────────┐
│ users    │──┐         │conversations  │       │ LITERATURE       │
│ api_keys │  │    ┌───▶│ messages      │       │  papers          │
└─────────┘  │    │    │ tool_executions│       │  user_papers     │
             ├────┤    └───────────────┘       │  paper_relations  │
             │    │    ┌───────────────┐       └──────────────────┘
             │    └───▶│ projects      │       ┌──────────────────┐
             │         └───────────────┘       │ PROTEINS         │
             │                                  │  genes, proteins │
             │                                  │  protein_inter.  │
             │                                  └──────────────────┘
             │                                  ┌──────────────────┐
             │                                  │ DRUGS            │
             │                                  │  drugs           │
             │                                  │  drug_targets    │
             │                                  │  diseases        │
             │                                  │  repurpose_cand. │
             │                                  └──────────────────┘
             │                                  ┌──────────────────┐
             │                                  │ VARIANTS         │
             │                                  │  variants        │
             │                                  │  vcf_analyses    │
             │                                  │  vcf_var_entries │
             │                                  └──────────────────┘
             │         ┌─────────────────────┐
             └────────▶│ CROSS-MODULE        │
                       │  knowledge_edges    │
                       │  activity_log       │
                       └─────────────────────┘
```

Full schema: `db/schema.sql`

## Project Structure

```
cryo/
├── .env / .env.example              # All configuration
├── SOUL.md                          # Agent persona + behavior rules
├── ARCHITECTURE.md                  # Detailed architecture docs
├── test_queries.md                  # 40+ graded test queries
├── docker-compose.yml               # 3 services + health checks
│
├── api/                             # FastAPI backend
│   ├── main.py                      # App entry + report file serving
│   ├── requirements.txt             # Pinned Python deps
│   ├── core/
│   │   ├── config.py                # All settings from .env
│   │   ├── database.py              # Async SQLAlchemy + asyncpg
│   │   ├── auth.py                  # JWT + bcrypt
│   │   └── logging_config.py        # Structured colored logging
│   ├── models/                      # SQLAlchemy ORM (User, Conversation, Message, Project)
│   ├── routers/
│   │   ├── auth.py                  # POST /signup, /login, GET /me
│   │   └── chat.py                  # POST /send (SSE), GET /conversations, /tools
│   └── services/
│       └── hermes_bridge.py         # Slash translation + AIAgent wrapper
│
├── frontend/                        # React UI
│   └── src/
│       ├── components/
│       │   ├── ChatInput.tsx         # "/" slash command detection
│       │   ├── SlashMenu.tsx         # 14 commands with icons + fuzzy filter
│       │   ├── MessageBubble.tsx     # Markdown + file download cards
│       │   └── Sidebar.tsx           # Conversation list
│       ├── pages/
│       │   ├── AuthPage.tsx          # Login/signup with bio branding
│       │   └── ChatPage.tsx          # Main chat + SSE streaming
│       ├── lib/api.ts               # API client + auth
│       └── styles/globals.css       # CRYO dark theme (cyan/emerald)
│
├── db/schema.sql                    # PostgreSQL schema (20+ tables)
├── docker/
│   ├── Dockerfile.api               # python:3.12.13-slim-bookworm
│   └── Dockerfile.frontend          # node:22.15.0-alpine3.21
│
├── hermes-agent/                    # Hermes Agent source (modifiable)
│   ├── run_agent.py                 # AIAgent class
│   └── tools/
│       ├── cryo_literature.py       # pubmed_search, biorxiv_search
│       ├── cryo_protein.py          # uniprot_lookup, pdb_search
│       ├── cryo_drug.py             # chembl_search, opentargets_search
│       ├── cryo_variant.py          # clinvar_lookup, ensembl_vep
│       ├── cryo_reports.py          # generate_pdf, generate_excel, generate_chart
│       ├── cryo_vlm.py              # analyze_image_vlm
│       ├── cryo_citation.py         # fetch_citation
│       ├── cryo_cosight.py          # verify_claim
│       ├── cryo_deep_research.py    # deep_research
│       ├── cryo_open_deep_research.py # multi_agent_research
│       └── cryo_scientific_skills.py  # scientific_skill
│
└── integrations/                    # Cloned open-source tools
    ├── gpt-researcher/              # Autonomous deep research
    ├── Co-Sight/                    # Conflict-aware verification
    ├── open_deep_research/          # LangChain multi-agent research
    └── scientific-agent-skills/     # 133 scientific skill packs
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google AI Studio API key | **required** |
| `HERMES_MODEL` | LLM model | `gemini-3-flash-preview` |
| `HERMES_VLM_MODEL` | Vision model | `gemini-2.5-flash` |
| `HERMES_PROVIDER` | LLM provider | `gemini` |
| `HERMES_MAX_ITERATIONS` | Max tool loops per turn | `90` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `cryo` |
| `POSTGRES_USER` | Database user | `cryo` |
| `POSTGRES_PASSWORD` | Database password | **required** |
| `API_PORT` | API port | `8000` |
| `API_SECRET_KEY` | API secret | **required** |
| `JWT_SECRET` | JWT signing secret (32+ bytes for prod) | **required** |
| `JWT_EXPIRE_MINUTES` | Token TTL | `1440` |
| `CRYO_REPORTS_DIR` | Generated files directory | `/tmp/cryo-reports` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Docker Services

```yaml
db:        postgres:17.5-alpine3.22     :5432  healthcheck: pg_isready
api:       python:3.12.13-slim          :8000  healthcheck: /api/health
frontend:  node:22.15.0-alpine3.21      :3000  healthcheck: wget spider
```

```bash
docker compose up -d          # Start all
docker compose logs api -f    # Watch agent tool calls
docker compose down           # Stop all
```

## Pinned Dependencies

### Python (api/requirements.txt)
```
fastapi==0.136.0    uvicorn==0.34.3     sqlalchemy==2.0.41
asyncpg==0.30.0     pydantic==2.13.2    bcrypt==4.3.0
PyJWT==2.12.1       httpx==0.28.1       reportlab==4.4.0
openpyxl==3.1.5     matplotlib==3.10.3  python-dotenv==1.2.2
```

### Node (frontend/package.json)
```
react==19.1.0       react-dom==19.1.0     vite==6.3.4
tailwindcss==4.1.4  typescript==5.8.3     react-markdown==10.1.0
lucide-react==0.503.0  react-router-dom==7.5.0
```

## Agent Report Pipeline (Proven Working)

Tested `/report TP53 mutations in cancer with clinical significance`:

```
01:30:49  opentargets_search     → query='TP53'
01:30:50  pubmed_search          → query='TP53 mutations clinical significance cancer'
01:30:55  verify_claim (Co-Sight)→ 'TP53 mutations associated with poor prognosis...'
01:31:00  fetch_citation         → query='TP53 mutations cancer' (APA format)
01:31:12  generate_pdf           → 5 sections, 6950 bytes
```

Output: PDF with executive summary, findings, verification, citations.

## Known Issues

1. **Empty responses (~5% with gemini-3-flash-preview)**: Model occasionally returns empty after tool calls. Hermes retries 3x.
2. **PubMed rate limiting**: NCBI occasionally disconnects. Agent retries with rephrased query.
3. **JWT key warning**: Dev secret is 29 bytes, need 32+ for production.
4. **PDF styling**: Currently basic reportlab. Needs upgrade to publication quality.

## TODO

### High Priority
- [ ] Upgrade PDF generator — cover page with logo, colored section bars, headers/footers, page numbers, professional typography, table of contents
- [ ] Implement Plan → Execute → Reflect agent pattern (dynamic tool selection instead of loading all 17)
- [ ] Add retry logic with exponential backoff on all external API calls (NCBI, ChEMBL, CrossRef)
- [ ] Wire tool_executions table — save every tool call to PostgreSQL with args, result, duration
- [ ] Production JWT secret (32+ bytes), rate limiting on auth endpoints

### Medium Priority
- [ ] VCF file upload endpoint + variant analysis pipeline
- [ ] Knowledge graph population — auto-fill knowledge_edges table from tool results
- [ ] Paper bookmarking — save PubMed results to user_papers table
- [ ] Drug repurposing scoring engine — rank candidates using network proximity + literature evidence
- [ ] Conversation search — full-text search across all messages
- [ ] User settings page — model selection, default citation style, export preferences

### Integrations TODO
- [ ] Wire gpt-researcher for autonomous deep research (needs TAVILY_API_KEY or similar)
- [ ] Wire open_deep_research LangGraph pipeline (needs langchain deps)
- [ ] Wire Co-Sight native module (needs its own LLM config)
- [ ] Port more scientific-agent-skills as native Hermes tools (biopython, deepchem, esm)
- [ ] Add Mol* / py3Dmol for protein 3D visualization in browser
- [ ] Add Plotly/Dash for interactive dashboards

### Production TODO
- [ ] Multi-stage Dockerfiles (smaller images, no dev deps)
- [ ] Nginx reverse proxy for frontend (production Vite build)
- [ ] Remove `--reload` flag from uvicorn in production
- [ ] Database migrations with Alembic (instead of raw schema.sql)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Monitoring — Prometheus metrics, Grafana dashboards
- [ ] Backup strategy for PostgreSQL
- [ ] HTTPS with Let's Encrypt

### Research Ideas
- [ ] Autonomous hypothesis generation — agent proposes novel drug-target combinations
- [ ] Batch variant analysis — upload 1000+ variants, get prioritized report
- [ ] Literature contradiction detector — find papers that disagree on the same claim
- [ ] Protein-protein interaction explorer — visual network graphs
- [ ] Clinical trial matcher — match patient variants to active trials (ClinicalTrials.gov API)

## License

MIT
