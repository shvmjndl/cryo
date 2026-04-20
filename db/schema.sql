-- CRYO Database Schema
-- Comprehensive Research Yielding Outcomes
-- PostgreSQL 16+

-- ═══════════════════════════════════════════════════════════
-- EXTENSIONS
-- ═══════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";    -- composite GIN indexes

-- ═══════════════════════════════════════════════════════════
-- AUTH & USERS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT NOT NULL UNIQUE,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'researcher'
                    CHECK (role IN ('admin', 'researcher', 'viewer')),
    avatar_url      TEXT,
    institution     TEXT,
    bio             TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash        TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
-- RESEARCH PROJECTS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived', 'completed')),
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user ON projects(user_id);
CREATE INDEX idx_projects_tags ON projects USING GIN(tags);

-- ═══════════════════════════════════════════════════════════
-- CHAT & CONVERSATIONS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
    title           TEXT,
    model           TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
    system_prompt   TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived')),
    token_count     INTEGER DEFAULT 0,
    message_count   INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_project ON conversations(project_id);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content         TEXT,
    tool_calls      JSONB,               -- [{name, arguments, id}]
    tool_call_id    TEXT,                 -- for tool response messages
    token_count     INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX idx_messages_role ON messages(conversation_id, role);

-- ═══════════════════════════════════════════════════════════
-- TOOL EXECUTIONS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE tool_executions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id      UUID REFERENCES messages(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tool_name       TEXT NOT NULL,
    tool_input      JSONB NOT NULL DEFAULT '{}',
    tool_output     JSONB,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    duration_ms     INTEGER,
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_exec_conversation ON tool_executions(conversation_id);
CREATE INDEX idx_tool_exec_tool ON tool_executions(tool_name);

-- ═══════════════════════════════════════════════════════════
-- MODULE 1: LITERATURE / PAPERS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE papers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pmid            TEXT UNIQUE,          -- PubMed ID
    doi             TEXT UNIQUE,
    title           TEXT NOT NULL,
    abstract        TEXT,
    authors         JSONB DEFAULT '[]',   -- [{name, affiliation}]
    journal         TEXT,
    publish_date    DATE,
    source          TEXT CHECK (source IN ('pubmed', 'biorxiv', 'medrxiv', 'arxiv', 'manual')),
    keywords        TEXT[] DEFAULT '{}',
    mesh_terms      TEXT[] DEFAULT '{}',
    citation_count  INTEGER DEFAULT 0,
    full_text_url   TEXT,
    pdf_url         TEXT,
    metadata        JSONB DEFAULT '{}',
    embedding       BYTEA,               -- for semantic search later
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_papers_pmid ON papers(pmid);
CREATE INDEX idx_papers_doi ON papers(doi);
CREATE INDEX idx_papers_keywords ON papers USING GIN(keywords);
CREATE INDEX idx_papers_mesh ON papers USING GIN(mesh_terms);
CREATE INDEX idx_papers_title_trgm ON papers USING GIN(title gin_trgm_ops);

-- papers saved/bookmarked by users
CREATE TABLE user_papers (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    paper_id        UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
    notes           TEXT,
    tags            TEXT[] DEFAULT '{}',
    is_starred      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, paper_id)
);

-- cross-references between papers
CREATE TABLE paper_relations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paper_a_id      UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    paper_b_id      UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL CHECK (relation_type IN (
                        'cites', 'contradicts', 'supports', 'extends', 'reviews'
                    )),
    confidence      REAL CHECK (confidence BETWEEN 0 AND 1),
    evidence        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(paper_a_id, paper_b_id, relation_type)
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 2: PROTEINS & GENES
-- ═══════════════════════════════════════════════════════════
CREATE TABLE genes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol          TEXT NOT NULL,        -- e.g. TP53, EGFR
    name            TEXT,                 -- full name
    entrez_id       TEXT UNIQUE,
    ensembl_id      TEXT UNIQUE,
    organism        TEXT DEFAULT 'Homo sapiens',
    chromosome      TEXT,
    description     TEXT,
    gene_type       TEXT,                 -- protein_coding, lncRNA, etc.
    aliases         TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_genes_symbol ON genes(symbol);
CREATE INDEX idx_genes_aliases ON genes USING GIN(aliases);

CREATE TABLE proteins (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gene_id         UUID REFERENCES genes(id) ON DELETE SET NULL,
    uniprot_id      TEXT UNIQUE,         -- e.g. P04637
    name            TEXT NOT NULL,
    full_name       TEXT,
    organism        TEXT DEFAULT 'Homo sapiens',
    sequence        TEXT,
    length          INTEGER,
    mass_da         REAL,                -- molecular mass in Daltons
    function_desc   TEXT,
    subcellular_loc TEXT[] DEFAULT '{}',
    go_terms        JSONB DEFAULT '[]',  -- [{id, name, aspect}]
    domains         JSONB DEFAULT '[]',  -- [{name, start, end, source}]
    pathways        JSONB DEFAULT '[]',  -- [{id, name, source}]
    pdb_ids         TEXT[] DEFAULT '{}',
    structure_data  JSONB DEFAULT '{}',  -- AlphaFold/ESMFold results
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_proteins_uniprot ON proteins(uniprot_id);
CREATE INDEX idx_proteins_gene ON proteins(gene_id);
CREATE INDEX idx_proteins_pdb ON proteins USING GIN(pdb_ids);

-- protein-protein interactions
CREATE TABLE protein_interactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protein_a_id    UUID NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    protein_b_id    UUID NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    interaction_type TEXT,                -- physical, genetic, coexpression
    score           REAL,                -- confidence score (STRING-style)
    source          TEXT,                -- STRING, BioGRID, IntAct
    evidence        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(protein_a_id, protein_b_id, source)
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 3: DRUGS & COMPOUNDS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE drugs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chembl_id       TEXT UNIQUE,
    drugbank_id     TEXT UNIQUE,
    name            TEXT NOT NULL,
    generic_name    TEXT,
    drug_type       TEXT,                -- small molecule, biologic, antibody
    phase           TEXT,                -- approved, phase3, phase2, phase1, preclinical
    indication      TEXT,
    mechanism       TEXT,
    smiles          TEXT,                -- chemical structure
    molecular_formula TEXT,
    molecular_weight REAL,
    atc_codes       TEXT[] DEFAULT '{}',
    synonyms        TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drugs_chembl ON drugs(chembl_id);
CREATE INDEX idx_drugs_drugbank ON drugs(drugbank_id);
CREATE INDEX idx_drugs_name_trgm ON drugs USING GIN(name gin_trgm_ops);
CREATE INDEX idx_drugs_synonyms ON drugs USING GIN(synonyms);

-- drug-target relationships
CREATE TABLE drug_targets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id         UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    protein_id      UUID REFERENCES proteins(id) ON DELETE SET NULL,
    gene_symbol     TEXT,                -- fallback if protein not in DB
    action_type     TEXT,                -- inhibitor, agonist, antagonist, modulator
    activity_type   TEXT,                -- IC50, Ki, EC50, Kd
    activity_value  REAL,
    activity_unit   TEXT,                -- nM, uM
    pchembl_value   REAL,               -- standardized potency
    source          TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drug_targets_drug ON drug_targets(drug_id);
CREATE INDEX idx_drug_targets_protein ON drug_targets(protein_id);
CREATE INDEX idx_drug_targets_gene ON drug_targets(gene_symbol);

-- diseases and drug-disease associations
CREATE TABLE diseases (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    omim_id         TEXT UNIQUE,
    mondo_id        TEXT UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    synonyms        TEXT[] DEFAULT '{}',
    associated_genes TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_diseases_name_trgm ON diseases USING GIN(name gin_trgm_ops);

CREATE TABLE drug_repurposing_candidates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drug_id         UUID NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
    disease_id      UUID NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    score           REAL,                -- repurposing confidence score
    evidence_type   TEXT,                -- literature, network, structural, clinical
    evidence        JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'hypothesis'
                    CHECK (status IN ('hypothesis', 'validated', 'rejected', 'in_trial')),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 4: GENOMIC VARIANTS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE variants (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gene_id         UUID REFERENCES genes(id) ON DELETE SET NULL,
    gene_symbol     TEXT,
    chromosome      TEXT NOT NULL,
    position        BIGINT NOT NULL,
    ref_allele      TEXT NOT NULL,
    alt_allele      TEXT NOT NULL,
    rsid            TEXT,                -- rs12345
    hgvs_c          TEXT,                -- coding HGVS notation
    hgvs_p          TEXT,                -- protein HGVS notation
    variant_type    TEXT,                -- SNV, insertion, deletion, indel
    consequence     TEXT,                -- missense, nonsense, frameshift, splice
    impact          TEXT,                -- HIGH, MODERATE, LOW, MODIFIER
    -- population frequencies
    gnomad_af       REAL,                -- gnomAD allele frequency
    gnomad_af_popmax REAL,
    -- clinical significance
    clinvar_id      TEXT,
    clinvar_significance TEXT,           -- pathogenic, likely_pathogenic, VUS, benign
    clinvar_conditions TEXT[] DEFAULT '{}',
    -- predictions
    sift_score      REAL,
    sift_pred       TEXT,
    polyphen_score  REAL,
    polyphen_pred   TEXT,
    cadd_score      REAL,
    revel_score     REAL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chromosome, position, ref_allele, alt_allele)
);

CREATE INDEX idx_variants_gene ON variants(gene_id);
CREATE INDEX idx_variants_gene_symbol ON variants(gene_symbol);
CREATE INDEX idx_variants_rsid ON variants(rsid);
CREATE INDEX idx_variants_clinvar ON variants(clinvar_significance);
CREATE INDEX idx_variants_position ON variants(chromosome, position);

-- user-uploaded VCF analyses
CREATE TABLE vcf_analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
    filename        TEXT NOT NULL,
    sample_name     TEXT,
    reference_genome TEXT DEFAULT 'GRCh38',
    total_variants  INTEGER DEFAULT 0,
    pathogenic_count INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    summary         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE vcf_variant_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vcf_analysis_id UUID NOT NULL REFERENCES vcf_analyses(id) ON DELETE CASCADE,
    variant_id      UUID REFERENCES variants(id) ON DELETE SET NULL,
    genotype        TEXT,                -- 0/1, 1/1, 0/0
    quality         REAL,
    depth           INTEGER,
    filter_status   TEXT,
    interpretation  TEXT,                -- AI-generated interpretation
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vcf_entries_analysis ON vcf_variant_entries(vcf_analysis_id);
CREATE INDEX idx_vcf_entries_variant ON vcf_variant_entries(variant_id);

-- ═══════════════════════════════════════════════════════════
-- CROSS-MODULE: KNOWLEDGE GRAPH EDGES
-- ═══════════════════════════════════════════════════════════
CREATE TABLE knowledge_edges (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type     TEXT NOT NULL,       -- gene, protein, drug, disease, variant, paper
    source_id       UUID NOT NULL,
    target_type     TEXT NOT NULL,
    target_id       UUID NOT NULL,
    relation        TEXT NOT NULL,       -- targets, causes, treats, associated_with, mentioned_in
    confidence      REAL DEFAULT 1.0,
    source_db       TEXT,                -- which database this came from
    evidence        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_type, source_id, target_type, target_id, relation)
);

CREATE INDEX idx_knowledge_source ON knowledge_edges(source_type, source_id);
CREATE INDEX idx_knowledge_target ON knowledge_edges(target_type, target_id);
CREATE INDEX idx_knowledge_relation ON knowledge_edges(relation);

-- ═══════════════════════════════════════════════════════════
-- ACTIVITY LOG
-- ═══════════════════════════════════════════════════════════
CREATE TABLE activity_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,       -- search, analyze, annotate, chat
    entity_type     TEXT,
    entity_id       UUID,
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_user ON activity_log(user_id, created_at DESC);

-- ═══════════════════════════════════════════════════════════
-- UPDATED_AT TRIGGER
-- ═══════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_proteins_updated_at BEFORE UPDATE ON proteins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
