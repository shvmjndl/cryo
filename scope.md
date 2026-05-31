# CRYO Scope & Roadmap

From autonomous "Search AI" → integrated "Synthesis AI" for global biological research challenges.

---

## Current Status (v3 — May 2026)

### ✅ Completed Features

#### Phase 0: Read-Only Research (Delivered)
- [x] **Multi-interface research platform** — Chat view + multi-canvas workspace
- [x] **28+ biology tools** — Literature, proteins, drugs, variants, omics, analysis
- [x] **Report Engine v4** — Interactive HTML with Plotly charts, Mermaid diagrams, callout blocks, timelines, tables
- [x] **File upload & auto-classification** — Drag-drop with real-time progress; auto-suggests `/deseq`, `/scrna`, `/meta`, etc.
- [x] **Workspace v2** — React Flow canvas with branching, resizable nodes, persistence (PostgreSQL), minimap, 10 workspaces/user
- [x] **Collections v1** — Topic-based artifact organization (papers, genes, drugs, pathways)
- [x] **Digital Twin v3** — Multi-backbone FBA (Human-GEM, iJO1366, Yeast8, Plasmodium)
  - Human-GEM: cancer drug response + 49 CCLE cell line personalization
  - Pathogen models: E. coli (antibacterial), S. cerevisiae (antifungal)
  - ChEMBL/DGIdb drug targets + GDSC2 IC50 validation
  - 8 integration tests (2026-04-30) ✓ all passing
- [x] **GEM Graph API** — Query any backbone (stats, gene/reaction detail)
- [x] **VLM OCR integration** — Gemini Vision 2 for image analysis (gels, microscopy)
- [x] **PostgreSQL schema v2** — users, conversations, messages, workspaces, nodes, edges, uploads, collections

#### Phase 1a: Workspace Hardening (In Progress)
- [x] Workspace CRUD + persistence
- [x] Node branching (context inheritance)
- [x] File upload per node
- [x] Multi-workspace switching (max 10, max 50 nodes each)
- [ ] **Pending:** Node deletion UI, workspace export/import, batch operations

#### Phase 1b: Knowledge Graph (Planned)
- [ ] Auto-link entities (genes, drugs, diseases) in reports
- [ ] Graph visualization (Cytoscape.js) of relationships
- [ ] Search across graph edges

---

## Phase 2: Advanced Analytics & Execution (Q2–Q3 2026)

### 2.1 Multi-Omics Integration
**Problem:** Rare disease diagnosis often requires synthesis of genomics + proteomics + transcriptomics.

**Deliverables:**
- [ ] Unified analysis dashboard: upload genome + transcriptome + proteome → integrated report
- [ ] Variant prioritization: population frequency + expression impact + protein structure
- [ ] Pathway dysregulation score (across omics modalities)

**Stack:** COBRApy + Scanpy + DESeq2; PostgreSQL for omics metadata; Neo4j (optional) for graph queries

**Effort:** 4–6 weeks (architecture + integration + testing)

### 2.2 Protein Design (GPU-Required)
**Problem:** Novel enzyme discovery requires *de novo* design; current tool only predicts folding.

**Deliverables:**
- [ ] `/design_protein enzyme <cofactor> <reaction_class>` → structures + sequences
  - RFdiffusion (backbone generation)
  - ProteinMPNN (sequence design)
  - AlphaFold validation
- [ ] `/design_binder <target_pdb> <affinity_nM>` → multi-candidate ranking
- [ ] Cost estimate + hardware requirements (GPU Docker container)

**Stack:** RFdiffusion + ProteinMPNN + AlphaFold; Docker container; async Celery tasks

**Effort:** 6–8 weeks (model setup + wrapper + validation + UI)

**GPU Requirements:** NVIDIA A100/H100; ~$2–5/design on cloud (AWS SageMaker, GCP)

### 2.3 Drug Synthesis Planning
**Problem:** Identified scaffolds must be synthesized; route planning is manual.

**Deliverables:**
- [ ] `/design_synthesis <molecule_smiles> <preferred_reagents>` → synthetic routes
  - AiZynthFinder (open-source retrosynthesis)
  - RDKIT route feasibility scoring
  - Reagent cost lookup

**Stack:** AiZynthFinder + RDKit + openpyxl (for reagent sheets)

**Effort:** 3–4 weeks

---

## Phase 3: Lab Execution & Feedback Loop (Q3–Q4 2026)

### 3.1 Self-Driving Lab Integration
**Problem:** Designs validated in-silico must be tested *in vitro*; robotic labs enable 24/7 execution.

**Deliverables:**
- [ ] `/lab_connect synthesize <molecule_smiles> <target_assay>` → generates Opentrons protocol
  - Chemical synthesis (liquid handling, heating, mixing)
  - Binding assay (ELISA or fluorescence)
  - MIC determination (antibacterial context)
- [ ] Live progress dashboard: status updates + image uploads from robot
- [ ] Result feedback loop: agent learns from failures

**Stack:** Opentrons API + PyLabRobot; async SSH/WebSocket to robot; result parser

**Hardware:** Opentrons OT-2 or similar (~$100k capital) OR cloud lab subscription (SciLifeLab, Emerald Cloud Lab)

**Effort:** 8–10 weeks (protocol generation + lab API + parsing + UI)

### 3.2 Adaptive Workflow
**Problem:** Negative results should trigger re-design; current flow is linear.

**Deliverables:**
- [ ] Multi-round optimization: failed compound → RFdiffusion variant → re-synthesize → re-test
- [ ] Reward signal from wet lab integrated into agent reasoning
- [ ] Cost tracking (synthesis + assay + staff time)

**Effort:** 4–6 weeks (workflow orchestration + feedback parsing)

---

## Phase 4: CRISPR Therapeutic Design (Q4 2026–Q1 2027)

### 4.1 gRNA Design & Off-Target Assessment
**Problem:** Rare genetic diseases identified; CRISPR therapy requires precise targeting.

**Deliverables:**
- [ ] `/crispr_design target_gene:<TP53> mutation:<c.217G>A>` → top 10 gRNA candidates
  - On-target scoring (MIT specificity, GC content, secondary structure)
  - Off-target search (CHOPCHOP, Cas-OFFinder)
  - Cell delivery assessment (AAV packaging constraints)
- [ ] PAM variants: SpCas9 + xCas9 + new Cas orthologs
- [ ] Prime editing support: pegRNA + nicking sgRNA co-design

**Stack:** Biopython + off-target tools; CHOPCHOP API; public gRNA DB

**Effort:** 6–8 weeks (algorithm integration + scoring + UI)

### 4.2 Clinical Trial Readiness
**Problem:** Designed therapies must meet regulatory standards.

**Deliverables:**
- [ ] Toxicity prediction (ChEMBL + DeepTox models)
- [ ] Off-target effect modeling (RNA-seq + transcript prediction)
- [ ] CMC (Chemistry, Manufacturing, Control) report generation
- [ ] IND application template (FDA 1571)

**Stack:** DeepTox models + template engines

**Effort:** 8–10 weeks

---

## Resource Requirements & Constraints

### Infrastructure

| Component | Current | Phase 2 | Phase 3 | Phase 4 |
|-----------|---------|---------|---------|---------|
| **CPU** | 4c / 8GB | 8c / 16GB | 16c / 32GB | 16c / 32GB |
| **GPU** | None | A100 (40GB) | A100 | A100 |
| **Storage** | 100GB | 500GB | 1TB | 1TB |
| **Monthly Cost (Cloud)** | ~$100 | ~$400 | ~$1500 (+ lab fees) | ~$400 |

### Timeline & Effort Estimate

```
2026-06 ──── 2026-07 ──── 2026-08 ──── 2026-09 ──── 2026-10 ──── 2026-11 ──── 2026-12 ──── 2027-01
│           │           │           │           │           │           │           │
Phase 2a    Phase 2b    Phase 2c    Phase 3.1   Phase 3.2   Phase 4.1   Phase 4.2   Deploy
Multi-Omics Protein     Synthesis   Lab Exec    Feedback    CRISPR      Clinical    v1.0
(4–6w)      Design      Planning    Integration (4–6w)      Design      Readiness
            (6–8w)      (3–4w)      (8–10w)                 (6–8w)      (8–10w)
```

**Total Effort:** ~50–60 person-weeks → 3–4 months with 2–3 FTE

### Funding & Partnerships

- **Phase 2 (Analytics):** Open-source libraries; ~$2k cloud compute/month
- **Phase 3 (Lab):** **Lab hardware or subscription required**
  - Opentrons OT-2: ~$100k capital + ~$5k/month supplies
  - Cloud lab (Emerald, SciLifeLab): ~$500–2k per experiment
  - **Partnership suggested:** University biotech core facility
- **Phase 4 (CRISPR):** FDA pathway consulting recommended (~$50–100k)

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| GPU compute costs | High | Use CPU variants first; apply for research credits (AWS, GCP) |
| Lab hardware procurement | Critical | Partner with university; cloud lab subscription fallback |
| Model training data drift | Medium | Quarterly validation against literature + wet lab results |
| Regulatory compliance (FDA) | High | Engage regulatory consultant early (Phase 3) |
| Tool versioning (ChEMBL, PDB) | Medium | SQLite cache + version pinning; 6-month refresh cycle |

---

## Success Metrics

### By Phase

**Phase 2:** 
- [ ] 10 multi-omics analysis results published / validated
- [ ] 5 novel protein designs tested *in silico* (FAPE < 2.5 Å)

**Phase 3:**
- [ ] 20 synthesized compounds from designed scaffolds
- [ ] 5+ verified hits in binding assay
- [ ] <2 week design-to-lab turnaround time

**Phase 4:**
- [ ] 3 gRNA panels designed for clinical rare disease targets
- [ ] 1 IND application pre-submission package (FDA-ready)
- [ ] <$50k cost per therapy design (vs. $1M+ traditional)

### Overall (v1.0 Release)
- 100+ active users
- 50+ published reports
- 5+ clinical collaboration partnerships
- Demonstrated cost reduction vs. traditional drug discovery (10x)

---

## Code Organization for Phase 2+

```
cryo/
├── api/
│   ├── services/
│   │   ├── omics_integration/      # Phase 2a
│   │   │   ├── variant_prioritizer.py
│   │   │   ├── pathway_dysregulation.py
│   │   │   └── multi_omics_report.py
│   │   ├── protein_design/         # Phase 2b (GPU)
│   │   │   ├── rfdiffusion_wrapper.py
│   │   │   ├── proteinmpnn_wrapper.py
│   │   │   └── design_orchestrator.py
│   │   ├── synthesis_planning/     # Phase 2c
│   │   │   ├── retrosynthesis.py
│   │   │   └── route_optimizer.py
│   │   ├── lab_automation/         # Phase 3.1
│   │   │   ├── opentrons_protocol.py
│   │   │   ├── lab_api_client.py
│   │   │   └── result_parser.py
│   │   └── crispr_design/          # Phase 4.1
│   │       ├── grna_designer.py
│   │       ├── off_target_finder.py
│   │       └── prime_editor.py
│   └── routers/
│       ├── omics.py                # /api/omics/*
│       ├── protein_design.py       # /api/design/*
│       ├── synthesis.py            # /api/synthesis/*
│       ├── lab.py                  # /api/lab/*
│       └── crispr.py               # /api/crispr/*
├── hermes-agent/tools/
│   ├── cryo_omics_integration.py    # Multi-omics tool
│   ├── cryo_protein_design.py       # Protein design tool
│   ├── cryo_synthesis.py            # Synthesis planning tool
│   ├── cryo_lab_connect.py          # Lab execution tool
│   └── cryo_crispr.py               # CRISPR design tool
├── frontend/src/
│   ├── pages/
│   │   ├── OmicsPage.tsx            # Phase 2a UI
│   │   ├── ProteinDesignPage.tsx    # Phase 2b UI
│   │   ├── LabDashboard.tsx         # Phase 3 UI
│   │   └── CRISPRPage.tsx           # Phase 4 UI
│   └── components/
│       ├── OmicsUpload.tsx
│       ├── ProteinViewer3D.tsx
│       └── LabProgressMonitor.tsx
└── tests/
    ├── test_omics_integration.py
    ├── test_protein_design.py
    ├── test_synthesis.py
    ├── test_lab_automation.py
    └── test_crispr_design.py
```

---

## Notes & Decisions

### On Digital Twin v3
- **Why multi-backbone?** Different organisms require different models; E. coli iJO1366 needed for antibiotics
- **Why CCLE personalization?** Cell line RNA expression constraints are the only way to get realistic drug effects
- **Why not GTEx?** Disease context matters; tissue-specific models easier with cancer lines

### On Workspace Branching
- **Node inheritance:** Child nodes inherit parent conversation context (enables hypothesis trees)
- **Max 50 nodes/workspace:** Prevents UI performance degradation; users typically use 5–10 per project

### On Report Engine v4
- **Why :::blocks?** Markdown extensible without HTML; integrates with agent reasoning
- **Why Plotly?** Interactive JS charts render client-side; no server-side image generation overhead

### On Phase Ordering
1. **Phase 2 first:** Analytics unlocks the most immediate research value; no lab required
2. **Phase 3 depends on Phase 2:** Lab execution needs high-confidence designs from multi-omics
3. **Phase 4 parallel to 3:** CRISPR design independent; can run in parallel if resources allow

