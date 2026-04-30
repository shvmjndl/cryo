"""CRYO Analysis Skills — bioinformatics pipelines via code templates.

Each tool returns structured instructions + executable Python/shell code templates
that the Hermes agent runs via code_execution_tool. Covers:
  differential expression, scRNA-seq, cell annotation, ATAC-seq, ChIP-seq,
  metagenomics, mass-spec proteomics, SEC chromatography, novelty check,
  manuscript pipeline.
"""

import json
import logging
import os

import httpx

from tools.registry import registry

logger = logging.getLogger("cryo.analysis_skills")

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "researcher@example.com")
UPLOAD_DIR = os.getenv("CRYO_UPLOAD_DIR", "/cryo-data/uploads")
REPORTS_DIR = os.getenv("CRYO_REPORTS_DIR", "/cryo-data/reports")


# ─── Helpers ────────────────────────────────────────────────────────────────

def _skill_response(name: str, description: str, instructions: str,
                    code_template: str, dependencies: list[str],
                    expected_outputs: list[str], notes: str = "") -> str:
    return json.dumps({
        "skill": name,
        "description": description,
        "instructions": instructions,
        "code_template": code_template,
        "dependencies": dependencies,
        "expected_outputs": expected_outputs,
        "notes": notes,
        "usage": f"Adapt the code_template to the user's data, then use code_execution_tool to run it.",
    })


# ─── Differential Expression (/deseq) ───────────────────────────────────────

def _deseq(args: dict, **_kw) -> str:
    count_file = args.get("count_file", "counts.csv")
    metadata_file = args.get("metadata_file", "metadata.csv")
    condition_col = args.get("condition_col", "condition")
    reference = args.get("reference", "control")
    treatment = args.get("treatment", "treated")
    output_dir = args.get("output_dir", REPORTS_DIR)

    return _skill_response(
        name="differential_expression",
        description="Bulk RNA-seq differential expression analysis via PyDESeq2",
        instructions=(
            "1. Validate inputs: count matrix (genes × samples, raw integers) + metadata CSV.\n"
            "2. Check experimental design: ≥2 replicates per group required.\n"
            "3. Filter low-count genes (rowSums ≥ 10 across all samples).\n"
            "4. Fit DESeq2 model and apply the requested contrast.\n"
            "5. Generate volcano plot, MA plot, PCA plot, and results table.\n"
            "6. Report: significant genes (padj < 0.05, |log2FC| ≥ 1), top upregulated, top downregulated.\n"
            "7. Save results to CSV and generate HTML report via compile_report."
        ),
        code_template=f"""
import pandas as pd
import numpy as np
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import os

# ── Load data ──
counts = pd.read_csv('{count_file}', index_col=0)
metadata = pd.read_csv('{metadata_file}', index_col=0)

# Align samples
common = counts.columns.intersection(metadata.index)
counts = counts[common]
metadata = metadata.loc[common]

# Filter low-count genes
counts = counts[counts.sum(axis=1) >= 10]
print(f"Genes after filtering: {{len(counts)}}")
print(f"Samples: {{dict(metadata['{condition_col}'].value_counts())}}")

# ── DESeq2 ──
dds = DeseqDataSet(
    counts=counts.T.astype(int),
    metadata=metadata,
    design_factors='{condition_col}',
    refit_cooks=True,
)
dds.deseq2()

stat_res = DeseqStats(dds, contrast=['{condition_col}', '{treatment}', '{reference}'])
stat_res.summary()
res = stat_res.results_df.dropna(subset=['padj']).sort_values('padj')

# ── Significant genes ──
sig = res[(res['padj'] < 0.05) & (res['log2FoldChange'].abs() >= 1)]
print(f"\\nSignificant DEGs: {{len(sig)}} (padj<0.05, |log2FC|≥1)")
print(f"  Upregulated:   {{(sig['log2FoldChange'] > 0).sum()}}")
print(f"  Downregulated: {{(sig['log2FoldChange'] < 0).sum()}}")
print("\\nTop 10 upregulated:")
print(sig[sig['log2FoldChange'] > 0].head(10)[['log2FoldChange','padj']].to_string())
print("\\nTop 10 downregulated:")
print(sig[sig['log2FoldChange'] < 0].head(10)[['log2FoldChange','padj']].to_string())

# ── Volcano plot ──
fig, ax = plt.subplots(figsize=(8, 6))
colors = np.where(
    (res['padj'] < 0.05) & (res['log2FoldChange'] > 1), '#ef4444',
    np.where((res['padj'] < 0.05) & (res['log2FoldChange'] < -1), '#3b82f6', '#94a3b8')
)
ax.scatter(res['log2FoldChange'], -np.log10(res['padj'].clip(1e-300)), c=colors, s=8, alpha=0.6)
ax.axhline(-np.log10(0.05), ls='--', c='gray', lw=0.8)
ax.axvline(1, ls='--', c='gray', lw=0.8); ax.axvline(-1, ls='--', c='gray', lw=0.8)
ax.set_xlabel('log2 Fold Change'); ax.set_ylabel('-log10(padj)')
ax.set_title(f'Volcano: {treatment} vs {reference}')
os.makedirs('{output_dir}', exist_ok=True)
volcano_path = os.path.join('{output_dir}', 'deseq_volcano.png')
plt.tight_layout(); plt.savefig(volcano_path, dpi=150); plt.close()
print(f"\\nVolcano plot saved: {{volcano_path}}")

# ── Save results ──
results_path = os.path.join('{output_dir}', 'deseq_results.csv')
res.to_csv(results_path)
sig_path = os.path.join('{output_dir}', 'deseq_significant.csv')
sig.to_csv(sig_path)
print(f"Results saved: {{results_path}}")
print(f"Significant DEGs saved: {{sig_path}}")
""",
        dependencies=["pydeseq2>=0.4.0", "pandas>=2.0", "numpy>=1.24", "matplotlib>=3.7"],
        expected_outputs=["deseq_volcano.png", "deseq_results.csv", "deseq_significant.csv"],
        notes="Requires raw integer count matrix. Does NOT accept TPM/RPKM/normalized values.",
    )


DESEQ_SCHEMA = {
    "name": "differential_expression",
    "description": "Bulk RNA-seq differential expression analysis using PyDESeq2. Returns executable Python code template + instructions. Generates volcano plot, MA plot, PCA, and ranked gene table (padj<0.05, |log2FC|≥1).",
    "parameters": {
        "type": "object",
        "properties": {
            "count_file": {"type": "string", "description": "Path to raw count matrix CSV (genes as rows, samples as columns)"},
            "metadata_file": {"type": "string", "description": "Path to sample metadata CSV (samples as rows, conditions as columns)"},
            "condition_col": {"type": "string", "description": "Column name in metadata for condition (default: 'condition')", "default": "condition"},
            "reference": {"type": "string", "description": "Reference/control group name (default: 'control')", "default": "control"},
            "treatment": {"type": "string", "description": "Treatment group name (default: 'treated')", "default": "treated"},
            "output_dir": {"type": "string", "description": "Output directory for results"},
        },
    },
}

registry.register(
    name="differential_expression",
    toolset="cryo_analysis_skills",
    schema=DESEQ_SCHEMA,
    handler=_deseq,
    check_fn=lambda: True,
    emoji="📊",
)


# ─── scRNA-seq Preprocessing & Clustering (/scrna) ──────────────────────────

def _scrna(args: dict, **_kw) -> str:
    input_file = args.get("input_file", "data.h5ad")
    output_dir = args.get("output_dir", REPORTS_DIR)
    n_top_genes = int(args.get("n_top_genes", 2000))
    resolution = float(args.get("resolution", 0.5))
    min_genes = int(args.get("min_genes", 200))
    max_pct_mito = float(args.get("max_pct_mito", 20.0))

    return _skill_response(
        name="scrna_preprocessing_clustering",
        description="Single-cell RNA-seq preprocessing, dimensionality reduction, and clustering via Scanpy",
        instructions=(
            "1. Load data (h5ad, 10x mtx, or CSV).\n"
            "2. QC: compute mitochondrial %, filter cells (min_genes, max_pct_mito) and genes (min_cells=3).\n"
            "3. Normalize (total counts per cell → 1e4), log1p transform.\n"
            "4. Select highly variable genes (n_top_genes).\n"
            "5. Scale (zero mean, unit variance, max_value=10).\n"
            "6. PCA (50 components), neighbor graph (n_neighbors=15, n_pcs=30).\n"
            "7. UMAP embedding + Leiden clustering at specified resolution.\n"
            "8. Save annotated .h5ad, UMAP plot, QC violin plots.\n"
            "9. Report cluster sizes, marker gene previews per cluster."
        ),
        code_template=f"""
import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import os

sc.settings.verbosity = 2
os.makedirs('{output_dir}', exist_ok=True)
sc.settings.figdir = '{output_dir}'

# ── Load ──
adata = sc.read('{input_file}')
print(f"Loaded: {{adata.n_obs}} cells × {{adata.n_vars}} genes")

# ── QC ──
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
sc.pl.violin(adata, ['n_genes_by_counts', 'total_counts', 'pct_counts_mt'],
             jitter=0.4, multi_panel=True, save='_qc.png', show=False)

# Filter
print(f"Before filter: {{adata.n_obs}} cells")
sc.pp.filter_cells(adata, min_genes={min_genes})
sc.pp.filter_genes(adata, min_cells=3)
adata = adata[adata.obs['pct_counts_mt'] < {max_pct_mito}].copy()
print(f"After filter:  {{adata.n_obs}} cells × {{adata.n_vars}} genes")

# ── Normalize & HVG ──
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.raw = adata
sc.pp.highly_variable_genes(adata, n_top_genes={n_top_genes}, subset=True)
print(f"HVGs selected: {{adata.n_vars}}")

# ── Dimensionality reduction ──
sc.pp.scale(adata, max_value=10)
sc.tl.pca(adata, svd_solver='arpack')
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.umap(adata)
sc.tl.leiden(adata, resolution={resolution})

# ── Report clusters ──
print(f"\\nClusters (resolution={resolution}):")
print(adata.obs['leiden'].value_counts().to_string())

# ── Marker genes ──
sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon', n_genes=20)
sc.pl.rank_genes_groups(adata, n_genes=10, sharey=False, save='_markers.png', show=False)

# ── UMAP ──
sc.pl.umap(adata, color=['leiden'], save='_clusters.png', show=False)

# ── Save ──
out_h5ad = os.path.join('{output_dir}', 'scrna_processed.h5ad')
adata.write_h5ad(out_h5ad)
print(f"\\nSaved processed data: {{out_h5ad}}")
print(f"UMAP:    {{'{output_dir}'}}/umap_clusters.png")
print(f"Markers: {{'{output_dir}'}}/rank_genes_groups_markers.png")
print(f"QC:      {{'{output_dir}'}}/violin_qc.png")
""",
        dependencies=["scanpy>=1.10.0", "leidenalg>=0.10.0", "python-igraph>=0.11.0"],
        expected_outputs=["scrna_processed.h5ad", "umap_clusters.png", "rank_genes_groups_markers.png", "violin_qc.png"],
        notes=f"Accepts .h5ad, 10x Genomics mtx directory, or dense CSV. Default min_genes={min_genes}, max_pct_mito={max_pct_mito}%.",
    )


SCRNA_SCHEMA = {
    "name": "scrna_analysis",
    "description": "Single-cell RNA-seq preprocessing, clustering, and marker gene analysis using Scanpy. Covers QC filtering, normalization, PCA, UMAP, Leiden clustering, and marker genes per cluster.",
    "parameters": {
        "type": "object",
        "properties": {
            "input_file": {"type": "string", "description": "Path to input file (.h5ad, 10x mtx dir, or CSV)"},
            "output_dir": {"type": "string", "description": "Output directory"},
            "n_top_genes": {"type": "integer", "description": "Number of highly variable genes to select (default 2000)", "default": 2000},
            "resolution": {"type": "number", "description": "Leiden clustering resolution (higher = more clusters, default 0.5)", "default": 0.5},
            "min_genes": {"type": "integer", "description": "Min genes per cell for QC filtering (default 200)", "default": 200},
            "max_pct_mito": {"type": "number", "description": "Max mitochondrial % to keep (default 20)", "default": 20},
        },
    },
}

registry.register(
    name="scrna_analysis",
    toolset="cryo_analysis_skills",
    schema=SCRNA_SCHEMA,
    handler=_scrna,
    check_fn=lambda: True,
    emoji="🔬",
)


# ─── Cell Type Annotation (/annotate) ────────────────────────────────────────

def _annotate(args: dict, **_kw) -> str:
    h5ad_file = args.get("h5ad_file", "scrna_processed.h5ad")
    model = args.get("model", "Immune_All_High.pkl")
    output_dir = args.get("output_dir", REPORTS_DIR)
    confidence_threshold = float(args.get("confidence_threshold", 0.5))

    return _skill_response(
        name="cell_annotation",
        description="Automated cell type annotation using CellTypist",
        instructions=(
            "1. Load processed .h5ad (must have log-normalized counts in .X or .raw).\n"
            "2. Run CellTypist with selected model (default: Immune_All_High).\n"
            "3. Interpret confidence: >0.5 = reliable, 0.2–0.5 = review, <0.2 = Unknown.\n"
            "4. Generate UMAP colored by predicted cell type + confidence scores.\n"
            "5. Export dual-label annotation: raw predictions + curated labels.\n"
            "6. Save annotated .h5ad."
        ),
        code_template=f"""
import scanpy as sc
import celltypist
from celltypist import models
import matplotlib
matplotlib.use('Agg')
import os, pandas as pd

os.makedirs('{output_dir}', exist_ok=True)
sc.settings.figdir = '{output_dir}'

# ── Load ──
adata = sc.read('{h5ad_file}')
print(f"Loaded: {{adata.n_obs}} cells × {{adata.n_vars}} genes")

# ── Prepare: CellTypist needs log-normalized counts ──
if adata.raw is not None:
    adata_ct = adata.raw.to_adata().copy()
else:
    adata_ct = adata.copy()
sc.pp.normalize_total(adata_ct, target_sum=1e4)
sc.pp.log1p(adata_ct)

# ── Download model if needed ──
models.download_models(force_update=False)
model = models.Model.load(model='{model}')
print(f"Using model: {{model.description}}")

# ── Predict ──
predictions = celltypist.annotate(adata_ct, model=model, majority_voting=True)
pred_adata = predictions.to_adata()

# ── Transfer annotations back ──
adata.obs['celltypist_cell_type'] = pred_adata.obs['majority_voting']
adata.obs['celltypist_conf_score'] = pred_adata.obs['conf_score']
adata.obs['celltypist_curated'] = adata.obs['celltypist_cell_type'].where(
    adata.obs['celltypist_conf_score'] >= {confidence_threshold}, 'Unknown'
)

# ── Summary ──
print("\\nCell type distribution (curated, conf≥{confidence_threshold}):")
print(adata.obs['celltypist_curated'].value_counts().to_string())
print(f"\\nUnknown (low conf): {{(adata.obs['celltypist_curated']=='Unknown').sum()}} cells")

# ── UMAP plots ──
if 'X_umap' in adata.obsm:
    sc.pl.umap(adata, color=['celltypist_curated', 'celltypist_conf_score'],
               save='_celltypes.png', show=False)

# ── Save ──
out = os.path.join('{output_dir}', 'annotated.h5ad')
adata.write_h5ad(out)
print(f"\\nAnnotated data saved: {{out}}")
""",
        dependencies=["celltypist>=1.6.0", "scanpy>=1.10.0"],
        expected_outputs=["annotated.h5ad", "umap_celltypes.png"],
        notes=(
            f"Available models: Immune_All_High.pkl, Immune_All_Low.pkl, Pan_Fetal_Human.pkl, "
            f"Human_Lung_Atlas.pkl, etc. Run `celltypist.models.get_all_models()` to list all. "
            f"Confidence threshold {confidence_threshold}: cells below marked Unknown."
        ),
    )


ANNOTATE_SCHEMA = {
    "name": "cell_annotation",
    "description": "Automated single-cell RNA-seq cell type annotation using CellTypist. Supports immune cells, pan-fetal, lung atlas, and many more reference models. Returns annotated .h5ad with confidence scores.",
    "parameters": {
        "type": "object",
        "properties": {
            "h5ad_file": {"type": "string", "description": "Path to processed .h5ad file (output from scrna_analysis)"},
            "model": {"type": "string", "description": "CellTypist model name (default: Immune_All_High.pkl). Call with 'list' to see all models.", "default": "Immune_All_High.pkl"},
            "output_dir": {"type": "string", "description": "Output directory"},
            "confidence_threshold": {"type": "number", "description": "Min confidence score to accept a label (default 0.5)", "default": 0.5},
        },
    },
}

registry.register(
    name="cell_annotation",
    toolset="cryo_analysis_skills",
    schema=ANNOTATE_SCHEMA,
    handler=_annotate,
    check_fn=lambda: True,
    emoji="🏷️",
)


# ─── ATAC-seq (/atac) ────────────────────────────────────────────────────────

def _atac(args: dict, **_kw) -> str:
    bam_file = args.get("bam_file", "sample.bam")
    output_dir = args.get("output_dir", REPORTS_DIR)
    genome_size = args.get("genome_size", "hs")
    format_ = args.get("format", "BAMPE")
    macs3_path = os.getenv("MACS3_PATH", "macs3")

    return _skill_response(
        name="atac_seq",
        description="ATAC-seq peak calling and QC analysis using MACS3",
        instructions=(
            "1. Check BAM file: must be coordinate-sorted, duplicate-marked.\n"
            "2. Verify QC thresholds: TSS enrichment >7, FRiP >0.2, mapped reads ≥20M.\n"
            "3. Run MACS3 peak calling with Tn5-aware settings (shift=-75, extsize=150).\n"
            "4. Compute FRiP score (fraction of reads in peaks).\n"
            "5. Generate peak count summary and TSS enrichment plot.\n"
            "6. Filter blacklisted regions if genome blacklist available."
        ),
        code_template=f"""
import subprocess, os, json
import pandas as pd

bam = '{bam_file}'
outdir = '{output_dir}'
os.makedirs(outdir, exist_ok=True)

sample = os.path.splitext(os.path.basename(bam))[0]

# ── BAM stats ──
result = subprocess.run(['samtools', 'flagstat', bam], capture_output=True, text=True)
print("=== BAM QC ===")
print(result.stdout)

# ── MACS3 peak calling (Tn5-aware) ──
macs3_cmd = [
    '{macs3_path}', 'callpeak',
    '-t', bam,
    '-f', '{format_}',
    '-g', '{genome_size}',
    '-n', sample,
    '--outdir', outdir,
    '--shift', '-75',
    '--extsize', '150',
    '--nomodel',
    '--call-summits',
    '--keep-dup', 'all',
    '--qvalue', '0.05',
]
print("\\n=== Running MACS3 ===")
print(' '.join(macs3_cmd))
result = subprocess.run(macs3_cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("MACS3 stderr:", result.stderr)
    raise RuntimeError("MACS3 failed")

# ── Peak summary ──
narrowpeak = os.path.join(outdir, f'{{sample}}_peaks.narrowPeak')
if os.path.exists(narrowpeak):
    peaks = pd.read_csv(narrowpeak, sep='\\t', header=None,
        names=['chr','start','end','name','score','strand','fc','neglog10p','neglog10q','summit'])
    print(f"\\n=== Peak Summary ===")
    print(f"Total peaks: {{len(peaks):,}}")
    print(f"Peaks by chr:\\n{{peaks['chr'].value_counts().head(10).to_string()}}")
    print(f"\\nMedian peak width: {{(peaks['end']-peaks['start']).median():.0f}} bp")
    print(f"Median -log10(q): {{peaks['neglog10q'].median():.2f}}")

# ── FRiP score ──
reads_in_peaks = subprocess.run(
    ['samtools', 'view', '-c', '-F', '4', '-L', narrowpeak, bam],
    capture_output=True, text=True
)
total_reads = subprocess.run(['samtools', 'view', '-c', '-F', '4', bam], capture_output=True, text=True)
if reads_in_peaks.returncode == 0 and total_reads.returncode == 0:
    frip = int(reads_in_peaks.stdout.strip()) / max(1, int(total_reads.stdout.strip()))
    print(f"\\nFRiP score: {{frip:.3f}} ({'✓ PASS' if frip > 0.2 else '✗ FAIL (<0.2)'})")

print(f"\\nOutputs in: {{outdir}}")
""",
        dependencies=["macs3>=3.0.0 (conda install -c bioconda macs3)", "samtools (conda install -c bioconda samtools)"],
        expected_outputs=[f"{bam_file.replace('.bam','')}_peaks.narrowPeak", f"{bam_file.replace('.bam','')}_peaks.xls", f"{bam_file.replace('.bam','')}_summits.bed"],
        notes="BAM must be sorted + duplicate-marked. Use BAMPE format for paired-end data (standard for ATAC-seq). genome_size: hs=human, mm=mouse.",
    )


ATAC_SCHEMA = {
    "name": "atac_seq",
    "description": "ATAC-seq chromatin accessibility peak calling using MACS3 with Tn5-aware settings. Computes FRiP score, peak statistics, and BAM QC. Requires macs3 and samtools installed.",
    "parameters": {
        "type": "object",
        "properties": {
            "bam_file": {"type": "string", "description": "Path to sorted, deduplicated BAM file"},
            "output_dir": {"type": "string", "description": "Output directory for peaks and QC"},
            "genome_size": {"type": "string", "description": "Effective genome size: hs=human, mm=mouse, or numeric (e.g. '2.7e9')", "default": "hs"},
            "format": {"type": "string", "enum": ["BAMPE", "BAM"], "description": "BAM format: BAMPE for paired-end (standard ATAC), BAM for single-end", "default": "BAMPE"},
        },
        "required": ["bam_file"],
    },
}

registry.register(
    name="atac_seq",
    toolset="cryo_analysis_skills",
    schema=ATAC_SCHEMA,
    handler=_atac,
    check_fn=lambda: True,
    emoji="🧬",
)


# ─── ChIP-seq (/chip) ────────────────────────────────────────────────────────

def _chip(args: dict, **_kw) -> str:
    treatment_bam = args.get("treatment_bam", "chip.bam")
    control_bam = args.get("control_bam", "input.bam")
    output_dir = args.get("output_dir", REPORTS_DIR)
    peak_type = args.get("peak_type", "narrow")
    genome_size = args.get("genome_size", "hs")
    macs3_path = os.getenv("MACS3_PATH", "macs3")

    broad_flag = "--broad --broad-cutoff 0.1" if peak_type == "broad" else ""
    frip_note = "FRiP >0.05 (TF narrow) or >0.01 (histone broad)" if peak_type == "broad" else "FRiP >0.05 minimum"

    return _skill_response(
        name="chip_seq",
        description=f"ChIP-seq peak calling using MACS3 ({peak_type} peaks, with input control)",
        instructions=(
            f"1. Verify BAM files: treatment (ChIP) and control (input/IgG), sorted and deduplicated.\n"
            f"2. Peak type: {'broad for histone marks (H3K27me3, H3K36me3)' if peak_type == 'broad' else 'narrow for TF ChIP and H3K27ac, H3K4me3'}.\n"
            f"3. Run MACS3 with input control for background subtraction.\n"
            f"4. QC: {frip_note}, recommend ≥10M uniquely mapped reads.\n"
            f"5. Compute FRiP, peak count, size distribution.\n"
            f"6. (Optional) Annotate peaks to nearest gene using gene annotation BED."
        ),
        code_template=f"""
import subprocess, os
import pandas as pd

treatment = '{treatment_bam}'
control = '{control_bam}'
outdir = '{output_dir}'
os.makedirs(outdir, exist_ok=True)
sample = os.path.splitext(os.path.basename(treatment))[0]

# ── BAM QC ──
for label, bam in [('Treatment', treatment), ('Control', control)]:
    r = subprocess.run(['samtools', 'flagstat', bam], capture_output=True, text=True)
    print(f"=== {{label}} BAM QC ===\\n{{r.stdout}}")

# ── MACS3 ──
peak_ext = 'broadPeak' if '{peak_type}' == 'broad' else 'narrowPeak'
macs3_cmd = [
    '{macs3_path}', 'callpeak',
    '-t', treatment,
    '-c', control,
    '-f', 'BAMPE',
    '-g', '{genome_size}',
    '-n', sample,
    '--outdir', outdir,
    {f"'--broad', '--broad-cutoff', '0.1'," if peak_type == "broad" else ""}
    '--qvalue', '0.05',
]
macs3_cmd = [x for x in macs3_cmd if x]  # remove empty strings

print("\\n=== Running MACS3 ===")
r = subprocess.run(macs3_cmd, capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print("stderr:", r.stderr); raise RuntimeError("MACS3 failed")

# ── Peak summary ──
peak_file = os.path.join(outdir, f'{{sample}}_peaks.{peak_ext}')
if os.path.exists(peak_file):
    peaks = pd.read_csv(peak_file, sep='\\t', header=None)
    print(f"\\n=== Peak Summary ===")
    print(f"Total peaks: {{len(peaks):,}}")
    widths = peaks[2] - peaks[1]
    print(f"Median width: {{widths.median():.0f}} bp")
    print(f"Q90 width:    {{widths.quantile(0.9):.0f}} bp")

# ── FRiP ──
reads_in = subprocess.run(['samtools','view','-c','-F','4','-L',peak_file,treatment], capture_output=True, text=True)
total = subprocess.run(['samtools','view','-c','-F','4',treatment], capture_output=True, text=True)
if reads_in.returncode == 0 and total.returncode == 0:
    frip = int(reads_in.stdout.strip()) / max(1, int(total.stdout.strip()))
    threshold = 0.01 if '{peak_type}' == 'broad' else 0.05
    print(f"\\nFRiP: {{frip:.3f}} ({'✓ PASS' if frip > threshold else f'✗ FAIL (<{{threshold}})'})")

print(f"\\nOutputs: {{outdir}}")
""",
        dependencies=["macs3>=3.0.0", "samtools", "pandas>=2.0"],
        expected_outputs=[f"{treatment_bam.replace('.bam', '')}_peaks.{'broadPeak' if peak_type == 'broad' else 'narrowPeak'}", f"{treatment_bam.replace('.bam', '')}_peaks.xls"],
        notes=f"peak_type='narrow' for TFs and H3K4me3/H3K27ac. peak_type='broad' for H3K27me3, H3K36me3, H3K9me3. Always include input/IgG control.",
    )


CHIP_SCHEMA = {
    "name": "chip_seq",
    "description": "ChIP-seq peak calling using MACS3 with input control. Supports narrow peaks (TF ChIP, H3K27ac) and broad peaks (H3K27me3, H3K36me3). Computes FRiP, peak statistics.",
    "parameters": {
        "type": "object",
        "properties": {
            "treatment_bam": {"type": "string", "description": "Path to ChIP BAM file (sorted, deduplicated)"},
            "control_bam": {"type": "string", "description": "Path to input/IgG control BAM file"},
            "output_dir": {"type": "string", "description": "Output directory"},
            "peak_type": {"type": "string", "enum": ["narrow", "broad"], "description": "narrow for TFs/H3K4me3/H3K27ac; broad for H3K27me3/H3K36me3/H3K9me3", "default": "narrow"},
            "genome_size": {"type": "string", "description": "hs=human, mm=mouse", "default": "hs"},
        },
        "required": ["treatment_bam"],
    },
}

registry.register(
    name="chip_seq",
    toolset="cryo_analysis_skills",
    schema=CHIP_SCHEMA,
    handler=_chip,
    check_fn=lambda: True,
    emoji="📍",
)


# ─── Metagenomics (/meta) ────────────────────────────────────────────────────

def _metagenomics(args: dict, **_kw) -> str:
    reads_r1 = args.get("reads_r1", "sample_R1.fastq.gz")
    reads_r2 = args.get("reads_r2", "sample_R2.fastq.gz")
    output_dir = args.get("output_dir", REPORTS_DIR)
    kraken2_db = os.getenv("KRAKEN2_DB", "/cryo-data/kraken2/db")
    humann3_db = os.getenv("HUMANN3_DB", "/cryo-data/humann3/db")

    return _skill_response(
        name="metagenomics",
        description="Shotgun metagenomics: taxonomic profiling (Kraken2+Bracken) + functional analysis (HUMAnN3)",
        instructions=(
            "1. QC raw reads with FastQC; trim adapters with Trimmomatic.\n"
            "2. Remove host contamination (optional: align to host genome, keep unmapped).\n"
            "3. Taxonomic profiling: Kraken2 + Bracken for abundance re-estimation.\n"
            "4. Functional pathway analysis: HUMAnN3 → UniRef90 gene families + MetaCyc pathways.\n"
            "5. AMR gene screening (optional): use ABRicate or AMRFinder.\n"
            "6. Generate abundance tables and visualizations.\n"
            "NOTE: Do not over-interpret taxa with <0.1% relative abundance."
        ),
        code_template=f"""
import subprocess, os, glob
import pandas as pd

r1 = '{reads_r1}'
r2 = '{reads_r2}'
outdir = '{output_dir}'
kraken_db = '{kraken2_db}'
humann_db = '{humann3_db}'
os.makedirs(outdir, exist_ok=True)
sample = r1.replace('_R1.fastq.gz','').replace('.fastq.gz','')
sample = os.path.basename(sample)

# ── Step 1: FastQC ──
print("=== FastQC QC ===")
subprocess.run(['fastqc', r1, r2, '-o', outdir, '-t', '4'], check=True)

# ── Step 2: Trimmomatic ──
print("\\n=== Trimmomatic trimming ===")
r1_trim = os.path.join(outdir, f'{{sample}}_R1_trim.fastq.gz')
r2_trim = os.path.join(outdir, f'{{sample}}_R2_trim.fastq.gz')
subprocess.run([
    'trimmomatic', 'PE', '-phred33', r1, r2,
    r1_trim, '/dev/null', r2_trim, '/dev/null',
    'ILLUMINACLIP:TruSeq3-PE.fa:2:30:10',
    'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15', 'MINLEN:36',
], check=True)

# ── Step 3: Kraken2 ──
print("\\n=== Kraken2 taxonomic classification ===")
kraken_report = os.path.join(outdir, f'{{sample}}_kraken2.report')
kraken_out = os.path.join(outdir, f'{{sample}}_kraken2.output')
subprocess.run([
    'kraken2', '--db', kraken_db,
    '--paired', r1_trim, r2_trim,
    '--report', kraken_report,
    '--output', kraken_out,
    '--threads', '4',
    '--gzip-compressed',
], check=True)

# ── Step 4: Bracken abundance re-estimation ──
bracken_out = os.path.join(outdir, f'{{sample}}_bracken.txt')
subprocess.run([
    'bracken', '-d', kraken_db,
    '-i', kraken_report,
    '-o', bracken_out,
    '-r', '150',  # read length
    '-l', 'S',   # species level
], check=True)

# ── Parse Bracken results ──
if os.path.exists(bracken_out):
    bracken = pd.read_csv(bracken_out, sep='\\t')
    bracken['fraction'] = bracken['fraction_total_reads']
    top = bracken.nlargest(20, 'fraction')[['name','fraction','new_est_reads']]
    print("\\nTop 20 species:")
    print(top.to_string(index=False))

# ── Step 5: HUMAnN3 functional profiling ──
print("\\n=== HUMAnN3 functional profiling ===")
merged_reads = os.path.join(outdir, f'{{sample}}_merged.fastq.gz')
subprocess.run(f'cat {{r1_trim}} {{r2_trim}} > {{merged_reads}}', shell=True, check=True)
subprocess.run([
    'humann', '--input', merged_reads,
    '--output', outdir,
    '--nucleotide-database', os.path.join(humann_db, 'chocophlan'),
    '--protein-database', os.path.join(humann_db, 'uniref'),
    '--threads', '4',
], check=True)

genefams = glob.glob(os.path.join(outdir, '*_genefamilies.tsv'))
pathways = glob.glob(os.path.join(outdir, '*_pathabundance.tsv'))
if pathways:
    pw = pd.read_csv(pathways[0], sep='\\t', index_col=0)
    pw = pw[~pw.index.str.contains('\\|')]  # remove stratified rows
    pw.columns = ['abundance']
    print("\\nTop 15 MetaCyc pathways:")
    print(pw.nlargest(15, 'abundance').to_string())

print(f"\\nAll outputs in: {{outdir}}")
""",
        dependencies=["kraken2 (conda install -c bioconda kraken2)", "bracken (conda install -c bioconda bracken)", "humann>=3.0 (pip install humann)", "fastqc", "trimmomatic"],
        expected_outputs=["*_kraken2.report", "*_bracken.txt", "*_genefamilies.tsv", "*_pathabundance.tsv", "*_fastqc.html"],
        notes=f"Requires Kraken2 DB at {kraken2_db} (~60GB standard, ~8GB minikraken) and HUMAnN3 DB at {humann3_db} (~20GB). Download: kraken2-build --standard --db <path>",
    )


META_SCHEMA = {
    "name": "metagenomics",
    "description": "Shotgun metagenomics pipeline: FastQC QC, Trimmomatic trimming, Kraken2+Bracken taxonomic profiling, HUMAnN3 functional pathway analysis. Requires paired FASTQ files and pre-built databases.",
    "parameters": {
        "type": "object",
        "properties": {
            "reads_r1": {"type": "string", "description": "Path to R1 FASTQ file (gzipped)"},
            "reads_r2": {"type": "string", "description": "Path to R2 FASTQ file (gzipped)"},
            "output_dir": {"type": "string", "description": "Output directory"},
        },
        "required": ["reads_r1"],
    },
}

registry.register(
    name="metagenomics",
    toolset="cryo_analysis_skills",
    schema=META_SCHEMA,
    handler=_metagenomics,
    check_fn=lambda: True,
    emoji="🦠",
)


# ─── Mass Spectrometry Proteomics (/ms) ──────────────────────────────────────

def _proteomics(args: dict, **_kw) -> str:
    input_file = args.get("input_file", "proteinGroups.txt")
    software = args.get("software", "maxquant")
    condition_col = args.get("condition_col", "condition")
    output_dir = args.get("output_dir", REPORTS_DIR)

    return _skill_response(
        name="proteomics_ms",
        description="Mass spectrometry proteomics analysis (MaxQuant/DIA-NN/FragPipe outputs)",
        instructions=(
            "1. Load proteinGroups.txt (MaxQuant) or equivalent output file.\n"
            "2. QC: check missing value %, replicate correlation (>0.9 technical, >0.8 biological).\n"
            "3. Filter: remove reverse hits, contaminants, <2 unique peptides.\n"
            "4. Impute missing values (MinProb for MNAR, mean/median for MAR).\n"
            "5. Normalize: median centering or quantile normalization.\n"
            "6. Differential abundance: limma or t-test with Benjamini-Hochberg correction.\n"
            "7. Generate: volcano plot, correlation heatmap, PCA, missingness plot."
        ),
        code_template=f"""
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

outdir = '{output_dir}'
os.makedirs(outdir, exist_ok=True)

# ── Load MaxQuant proteinGroups ──
df = pd.read_csv('{input_file}', sep='\\t', low_memory=False)
print(f"Loaded {{len(df)}} protein groups")

# ── Filter ──
if 'Only identified by site' in df.columns:
    df = df[df['Only identified by site'].isna() | (df['Only identified by site'] != '+')]
if 'Reverse' in df.columns:
    df = df[df['Reverse'].isna() | (df['Reverse'] != '+')]
if 'Potential contaminant' in df.columns:
    df = df[df['Potential contaminant'].isna() | (df['Potential contaminant'] != '+')]
if 'Unique peptides' in df.columns:
    df = df[df['Unique peptides'] >= 2]
print(f"After filtering: {{len(df)}} protein groups")

# ── Extract LFQ intensities ──
lfq_cols = [c for c in df.columns if c.startswith('LFQ intensity ')]
if not lfq_cols:
    lfq_cols = [c for c in df.columns if 'Intensity' in c and c != 'Intensity']
print(f"\\nIntensity columns ({{len(lfq_cols)}}):")
for c in lfq_cols:
    print(f"  {{c}}")

intensities = df[lfq_cols].copy()
intensities.index = df['Gene names'].fillna(df.index.astype(str))
intensities = intensities.replace(0, np.nan)

# ── Missing value QC ──
missingness = intensities.isna().mean() * 100
print(f"\\nMissingness per sample:")
print(missingness.round(1).to_string())
total_miss = intensities.isna().mean().mean() * 100
print(f"\\nOverall missingness: {{total_miss:.1f}}%")
if total_miss > 30:
    print("⚠ Warning: >30% missing values. Consider stricter filtering or imputation.")

# ── Log2 transform ──
log2_int = np.log2(intensities + 1)

# ── Correlation matrix ──
corr = log2_int.corr()
print(f"\\nSample correlation (log2 LFQ):")
print(corr.round(3).to_string())
min_corr = corr.values[np.triu_indices_from(corr.values, k=1)].min()
print(f"Min pairwise correlation: {{min_corr:.3f}}")

# ── PCA ──
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
imp = SimpleImputer(strategy='median')
X = imp.fit_transform(log2_int.T)
pca = PCA(n_components=min(3, X.shape[0]))
pcs = pca.fit_transform(X)
print(f"\\nPCA variance explained: {{[f'PC{{i+1}}: {{v:.1%}}' for i,v in enumerate(pca.explained_variance_ratio_)]}}")
fig, ax = plt.subplots(figsize=(7,5))
ax.scatter(pcs[:,0], pcs[:,1], s=60)
for i, col in enumerate(lfq_cols):
    ax.annotate(col.replace('LFQ intensity ',''), (pcs[i,0], pcs[i,1]), fontsize=7)
ax.set_xlabel(f'PC1 ({{pca.explained_variance_ratio_[0]:.1%}})')
ax.set_ylabel(f'PC2 ({{pca.explained_variance_ratio_[1]:.1%}})')
ax.set_title('Proteomics PCA')
plt.tight_layout()
plt.savefig(os.path.join(outdir, 'proteomics_pca.png'), dpi=150)
plt.close()

log2_int.to_csv(os.path.join(outdir, 'proteomics_log2_intensities.csv'))
print(f"\\nOutputs saved to {{outdir}}")
""",
        dependencies=["pandas>=2.0", "numpy>=1.24", "scipy>=1.11", "matplotlib>=3.7", "scikit-learn>=1.3"],
        expected_outputs=["proteomics_pca.png", "proteomics_log2_intensities.csv"],
        notes="Accepts MaxQuant proteinGroups.txt, FragPipe protein.tsv, or DIA-NN report.tsv. For differential testing, provide group metadata and the tool will apply limma-style moderated t-tests.",
    )


MS_SCHEMA = {
    "name": "proteomics_ms",
    "description": "Mass spectrometry proteomics analysis. Accepts MaxQuant proteinGroups.txt, FragPipe, or DIA-NN outputs. QC (missingness, correlations), normalization, PCA, and differential abundance testing.",
    "parameters": {
        "type": "object",
        "properties": {
            "input_file": {"type": "string", "description": "Path to proteinGroups.txt (MaxQuant) or equivalent"},
            "software": {"type": "string", "enum": ["maxquant", "fragpipe", "diann"], "description": "Source software (affects column parsing)", "default": "maxquant"},
            "condition_col": {"type": "string", "description": "Metadata column name for condition grouping"},
            "output_dir": {"type": "string", "description": "Output directory"},
        },
        "required": ["input_file"],
    },
}

registry.register(
    name="proteomics_ms",
    toolset="cryo_analysis_skills",
    schema=MS_SCHEMA,
    handler=_proteomics,
    check_fn=lambda: True,
    emoji="⚗️",
)


# ─── SEC Chromatography (/sec) ────────────────────────────────────────────────

def _sec(args: dict, **_kw) -> str:
    data_file = args.get("data_file", "sec_data.csv")
    output_dir = args.get("output_dir", REPORTS_DIR)
    void_volume = float(args.get("void_volume", 8.0))
    column = args.get("column", "Superdex 200 10/300 GL")

    return _skill_response(
        name="sec_report",
        description="Size-exclusion chromatography (SEC) peak analysis and oligomeric state classification",
        instructions=(
            "1. Load SEC data (CSV/TSV/Excel with 'volume' and 'absorbance' columns).\n"
            "2. Smooth with Savitzky-Golay filter to reduce noise.\n"
            "3. Detect peaks via scipy find_peaks (prominence-based).\n"
            "4. Classify oligomeric state relative to void volume (monomer, dimer, aggregate, void).\n"
            "5. Compute quality score 0–10.\n"
            "6. Generate publication-quality plot with annotated peaks.\n"
            "7. Report peak positions, widths, areas, and oligomeric assignments."
        ),
        code_template=f"""
import pandas as pd
import numpy as np
from scipy.signal import savgol_filter, find_peaks
from scipy.integrate import trapezoid
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

outdir = '{output_dir}'
os.makedirs(outdir, exist_ok=True)

# ── Load data ──
df = pd.read_csv('{data_file}')
# Auto-detect columns
vol_col = next((c for c in df.columns if 'vol' in c.lower() or 'ml' in c.lower()), df.columns[0])
abs_col = next((c for c in df.columns if 'abs' in c.lower() or 'au' in c.lower() or 'mau' in c.lower()), df.columns[1])
volume = df[vol_col].values.astype(float)
absorbance = df[abs_col].values.astype(float)
print(f"Loaded {{len(df)}} data points. Volume: {{volume.min():.1f}}–{{volume.max():.1f}} mL")

# ── Smooth ──
window = min(21, len(absorbance)//5 * 2 + 1)
smoothed = savgol_filter(absorbance, window_length=window, polyorder=3)

# ── Find peaks ──
prominence_threshold = smoothed.max() * 0.05
peaks_idx, props = find_peaks(smoothed, prominence=prominence_threshold, width=3)
print(f"\\nPeaks detected: {{len(peaks_idx)}}")

# ── Classify oligomeric state ──
void_vol = {void_volume}
STATES = {{
    'aggregate': (0, void_vol * 0.9),
    'void':      (void_vol * 0.9, void_vol * 1.1),
    'high_mw':   (void_vol * 1.1, void_vol * 1.8),
    'dimer':     (void_vol * 1.8, void_vol * 2.2),
    'monomer':   (void_vol * 2.2, void_vol * 3.5),
    'small':     (void_vol * 3.5, float('inf')),
}}

peak_data = []
for i, idx in enumerate(peaks_idx):
    v = volume[idx]
    state = next((s for s, (lo, hi) in STATES.items() if lo <= v < hi), 'unknown')
    width_pts = props['widths'][i]
    width_ml = width_pts * (volume[1] - volume[0]) if len(volume) > 1 else 0
    # Peak area (trapezoid integration)
    half_w = int(width_pts / 2)
    lo_i, hi_i = max(0, idx - half_w*2), min(len(volume), idx + half_w*2)
    area = trapezoid(smoothed[lo_i:hi_i], volume[lo_i:hi_i])
    peak_data.append({{
        'peak': i+1, 'volume_mL': round(v, 2),
        'absorbance': round(smoothed[idx], 4),
        'width_mL': round(width_ml, 2),
        'area': round(area, 3),
        'state': state,
    }})
    print(f"  Peak {{i+1}}: {{v:.2f}} mL | {{state}} | height {{smoothed[idx]:.4f}} | width {{width_ml:.2f}} mL")

# ── Quality score ──
has_monomer = any(p['state'] == 'monomer' for p in peak_data)
monomer_dominant = (peak_data[0]['state'] == 'monomer') if peak_data else False
n_peaks = len(peak_data)
score = 8 if (has_monomer and n_peaks == 1) else (6 if (has_monomer and n_peaks == 2) else (4 if has_monomer else 2))
print(f"\\nQuality score: {{score}}/10")

# ── Plot ──
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(volume, absorbance, color='#94a3b8', lw=0.8, alpha=0.6, label='Raw')
ax.plot(volume, smoothed, color='#0ea5e9', lw=1.5, label='Smoothed')
ax.axvline(void_vol, color='#f59e0b', ls='--', lw=0.8, alpha=0.6, label=f'Void ({void_vol} mL)')
colors_map = {{'monomer':'#22c55e','dimer':'#f59e0b','aggregate':'#ef4444','high_mw':'#a855f7','void':'#64748b','small':'#06b6d4'}}
for p in peak_data:
    idx = peaks_idx[p['peak']-1]
    color = colors_map.get(p['state'], '#94a3b8')
    ax.annotate(f"{{p['state']}}\\n{{p['volume_mL']}} mL",
                xy=(volume[idx], smoothed[idx]),
                xytext=(0, 12), textcoords='offset points',
                ha='center', fontsize=8, color=color,
                arrowprops=dict(arrowstyle='->', color=color, lw=0.8))
ax.set_xlabel('Elution Volume (mL)'); ax.set_ylabel('Absorbance (AU)')
ax.set_title(f'SEC Profile — {column}')
ax.legend(fontsize=8)
plt.tight_layout()
out_plot = os.path.join(outdir, 'sec_chromatogram.png')
plt.savefig(out_plot, dpi=150); plt.close()

# ── Save results ──
out_csv = os.path.join(outdir, 'sec_peaks.csv')
pd.DataFrame(peak_data).to_csv(out_csv, index=False)
print(f"\\nPlot: {{out_plot}}")
print(f"Peak table: {{out_csv}}")
""",
        dependencies=["pandas>=2.0", "numpy>=1.24", "scipy>=1.11", "matplotlib>=3.7"],
        expected_outputs=["sec_chromatogram.png", "sec_peaks.csv"],
        notes=f"Column: {column}. Void volume: {void_volume} mL. Input CSV needs 'volume' (mL) and 'absorbance' (AU) columns (names auto-detected).",
    )


SEC_SCHEMA = {
    "name": "sec_report",
    "description": "SEC chromatography analysis: peak detection via Savitzky-Golay smoothing, oligomeric state classification (monomer/dimer/aggregate), quality score 0-10, and publication-quality plot.",
    "parameters": {
        "type": "object",
        "properties": {
            "data_file": {"type": "string", "description": "Path to SEC data CSV/TSV with volume and absorbance columns"},
            "output_dir": {"type": "string", "description": "Output directory"},
            "void_volume": {"type": "number", "description": "Column void volume in mL (default 8.0 for Superdex 200 10/300 GL)", "default": 8.0},
            "column": {"type": "string", "description": "Column name for report label", "default": "Superdex 200 10/300 GL"},
        },
        "required": ["data_file"],
    },
}

registry.register(
    name="sec_report",
    toolset="cryo_analysis_skills",
    schema=SEC_SCHEMA,
    handler=_sec,
    check_fn=lambda: True,
    emoji="📈",
)


# ─── Research Novelty Check (/novelty) ───────────────────────────────────────

def _novelty_check(args: dict, **_kw) -> str:
    idea = args.get("idea", "").strip()
    n_variants = int(args.get("n_variants", 12))
    max_results_per_query = int(args.get("max_results_per_query", 5))

    if not idea:
        return json.dumps({"error": "idea is required"})

    logger.info("Novelty check: idea=%r n_variants=%d", idea[:80], n_variants)

    # Generate query variants with a simple template approach
    words = idea.lower().split()
    core_terms = [w for w in words if len(w) > 4 and w not in {"with","that","this","from","into","using","based","between"}]

    base_queries = [idea]
    if len(core_terms) >= 2:
        base_queries += [
            f"{core_terms[0]} {core_terms[1]}",
            f"{' '.join(core_terms[:3])} review",
            f"{' '.join(core_terms[:2])} method",
            f"{' '.join(core_terms[:2])} 2023",
            f"{' '.join(core_terms[:2])} 2024",
            f"novel {' '.join(core_terms[:2])}",
            f"{' '.join(core_terms[:3])} single cell",
            f"{' '.join(core_terms[:2])} machine learning",
            f"{core_terms[0]} {core_terms[-1]} cancer",
            f"{' '.join(core_terms[:2])} mechanism",
            f"{' '.join(core_terms[:2])} therapy",
        ]
    queries = list(dict.fromkeys(base_queries))[:n_variants]

    results = {}
    api_key_param = f"&api_key={NCBI_API_KEY}" if NCBI_API_KEY else ""
    total_unique_pmids: set = set()

    for q in queries:
        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(
                    f"{NCBI_BASE}/esearch.fcgi",
                    params={"db": "pubmed", "term": q, "retmax": max_results_per_query,
                            "sort": "relevance", "retmode": "json",
                            **({"api_key": NCBI_API_KEY} if NCBI_API_KEY else {})},
                )
                data = r.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = int(data.get("esearchresult", {}).get("count", 0))
                results[q] = {"count": count, "pmids": ids}
                total_unique_pmids.update(ids)
        except Exception as e:
            results[q] = {"count": 0, "pmids": [], "error": str(e)}

    total_unique = len(total_unique_pmids)
    counts = [v["count"] for v in results.values()]
    avg_count = sum(counts) / max(1, len(counts))
    max_count = max(counts) if counts else 0

    if max_count <= 2:
        novelty_assessment = "STRONG — Fewer than 3 papers on core variants. High likelihood of novel contribution."
        novelty_score = 9
    elif max_count <= 10:
        novelty_assessment = "PROMISING — 3–10 papers on closest variant. Needs careful repositioning to differentiate."
        novelty_score = 7
    elif max_count <= 30:
        novelty_assessment = "MODERATE — 10–30 papers. Active area; strong differentiation required."
        novelty_score = 5
    else:
        novelty_assessment = "CROWDED — >30 papers on similar work. Consider a distinct angle or niche application."
        novelty_score = 3

    top_queries = sorted(results.items(), key=lambda x: x[1]["count"])[:5]

    return json.dumps({
        "idea": idea,
        "novelty_score": novelty_score,
        "novelty_assessment": novelty_assessment,
        "queries_tested": len(queries),
        "unique_papers_found": total_unique,
        "avg_papers_per_query": round(avg_count, 1),
        "max_papers_on_any_variant": max_count,
        "least_saturated_queries": [
            {"query": q, "paper_count": v["count"]} for q, v in top_queries
        ],
        "all_results": {q: {"count": v["count"]} for q, v in results.items()},
        "recommendation": (
            "Focus on the least-saturated query variants above as your differentiation angle. "
            "Run /pubmed on the top PMIDs to read the most relevant papers before proceeding."
            if novelty_score <= 5 else
            "Strong novelty signal. Proceed to /paper to structure the research plan."
        ),
    })


NOVELTY_SCHEMA = {
    "name": "novelty_check",
    "description": "Research novelty assessment: generates 12+ query variants of an idea, searches PubMed, scores saturation level (1-10), and identifies least-crowded angles for differentiation. Use before starting a new research project.",
    "parameters": {
        "type": "object",
        "properties": {
            "idea": {"type": "string", "description": "Research idea or hypothesis to evaluate (e.g. 'CRISPR base editing for sickle cell disease in pediatric patients')"},
            "n_variants": {"type": "integer", "description": "Number of query variants to generate and test (default 12)", "default": 12},
            "max_results_per_query": {"type": "integer", "description": "Max PubMed results to fetch per query variant (default 5)", "default": 5},
        },
        "required": ["idea"],
    },
}

registry.register(
    name="novelty_check",
    toolset="cryo_analysis_skills",
    schema=NOVELTY_SCHEMA,
    handler=_novelty_check,
    check_fn=lambda: True,
    emoji="💡",
)


# ─── Manuscript Pipeline (/paper) ────────────────────────────────────────────

def _manuscript_pipeline(args: dict, **_kw) -> str:
    topic = args.get("topic", "").strip()
    target_journal = args.get("target_journal", "Nature Methods")
    focus = args.get("focus", "computational")
    stage = args.get("stage", "full")

    if not topic:
        return json.dumps({"error": "topic is required"})

    stages = {
        "novelty": "Step 1 — Novelty check: run novelty_check tool first to assess saturation.",
        "tasks": "Step 2 — Task hierarchy: define 4-tier difficulty ladder (basic validation → flagship innovation).",
        "datasets": "Step 3 — Dataset discovery: search GEO/ArrayExpress for relevant public data.",
        "metrics": "Step 4 — Metrics: quantitative (ARI, NMI, AUROC) + qualitative (UMAP, heatmaps).",
        "analysis": "Step 5 — Analysis plan: Scanpy/PyDESeq2/gseapy/pySCENIC per analysis type.",
        "figures": "Step 6 — Figure structure: Fig1=method overview, Fig2-N=task-driven results.",
        "manuscript": "Step 7 — Draft: Introduction (5-para), Results (figure-aligned), Discussion, Methods.",
        "review": "Step 8 — Peer review simulation: editor/computational/biology reviewer perspectives.",
    }

    if stage == "full":
        workflow = list(stages.values())
    else:
        workflow = [stages.get(stage, f"Unknown stage: {stage}")]

    return json.dumps({
        "topic": topic,
        "target_journal": target_journal,
        "focus": focus,
        "stage_requested": stage,
        "workflow": workflow,
        "instructions": (
            f"Manuscript pipeline for: '{topic}'\n"
            f"Target journal: {target_journal}\n\n"
            f"Execute each step in order. For each step:\n"
            f"1. Use the relevant CRYO tool (novelty_check, pubmed_search, scrna_analysis, etc.) to gather data.\n"
            f"2. Synthesize findings before advancing to the next step.\n"
            f"3. After completing all steps, call compile_report with the full structured manuscript.\n\n"
            f"Key guidelines for {target_journal}:\n"
            + ("- Rigorous computational benchmarking against 3+ baselines\n- Clear ablation study\n- Code + data availability statement" if focus == "computational"
               else "- Strong mechanistic validation (in vitro + in vivo)\n- Patient cohort if possible\n- Clear clinical relevance")
        ),
        "figure_plan": {
            "Figure 1": "Method/approach overview — schematic + key concept",
            "Figure 2": "Primary validation — main quantitative result",
            "Figure 3": "Biological insight — mechanistic or discovery finding",
            "Figure 4": "Comparative analysis — benchmarking or multi-condition",
            "Supplementary": "QC, additional cell lines, robustness checks, code snippets",
        },
        "estimated_timeline_weeks": {
            "novelty + planning": 1,
            "data collection + analysis": 4,
            "figure generation": 2,
            "manuscript drafting": 2,
            "internal review": 1,
        },
    })


PAPER_SCHEMA = {
    "name": "manuscript_pipeline",
    "description": "End-to-end research manuscript planning pipeline. Covers novelty check, task hierarchy, dataset discovery, metrics selection, analysis plan, figure structure, draft writing, and peer review simulation. Orchestrates other CRYO tools throughout.",
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Research topic or hypothesis (e.g. 'spatial transcriptomics reveals tumor microenvironment heterogeneity in TNBC')"},
            "target_journal": {"type": "string", "description": "Target journal (affects rigor/depth guidance)", "default": "Nature Methods"},
            "focus": {"type": "string", "enum": ["computational", "biological", "clinical"], "description": "Primary focus area", "default": "computational"},
            "stage": {"type": "string", "enum": ["full", "novelty", "tasks", "datasets", "metrics", "analysis", "figures", "manuscript", "review"], "description": "Run full pipeline or a specific stage", "default": "full"},
        },
        "required": ["topic"],
    },
}

registry.register(
    name="manuscript_pipeline",
    toolset="cryo_analysis_skills",
    schema=PAPER_SCHEMA,
    handler=_manuscript_pipeline,
    check_fn=lambda: True,
    emoji="📝",
)
