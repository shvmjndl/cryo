# CRYO — From "Search AI" to "Synthesis AI"

## Vision
To empower an AI like CRYO to solve global biological challenges, the "right tech" integration must move beyond information retrieval (Reading) to experimental execution and biological synthesis (Writing). This document outlines the evolution into an Autonomous Biological Agent capable of designing and overseeing the creation of new biological entities by leveraging open-source projects.

## Phase 0: Workspace UI Stabilization (Immediate Focus)
Before integrating advanced "Write Tech," it is critical to stabilize the recently developed multi-canvas workspace UI. This phase addresses the immediate actionable items identified in `currentstate_20260422_225041.json`.

1.  **Commit and Push:** Ensure all current workspace UI changes are committed and pushed to the repository.
2.  **Comprehensive Workflow Testing:**
    *   Thoroughly test the full workspace flow: create new workspace → add multiple nodes → engage in conversations within nodes → utilize the branch feature → reload the application → verify that all node positions, conversations, and branches persist correctly via PostgreSQL.
    *   Test multiple workspace switching functionality to ensure nodes and edges load correctly per workspace.
3.  **UI/UX Refinements:**
    *   **Slash Command Dropdown Visibility:** Verify and fix any clipping issues in workspace nodes (e.g., by ensuring appropriate `overflow: visible` and `z-index` properties for the dropdown).
    *   **Report Generation:** Test report generation from workspace nodes and verify that file download cards appear correctly in the UI.
    *   **Node Resizing Discoverability:** Implement visual cues (e.g., cursor changes on edges, subtle highlights) to make the `NodeResizer` handles more obvious to the user.
    *   **Workspace Management:** Add a 3-dot menu or similar UI element on workspace items in the left panel to allow users to delete workspaces.
4.  **Production Hardening:** Implement error boundaries, comprehensive loading states, and appropriate empty states across the application to enhance robustness and user experience.

## Resource Requirements for Phase 1 "Write Tech" Integrations

### 1. `/lab_connect` (Self-Driving Lab Integration)
*   **Paid Services:** Yes, potentially. While the software (Opentrons Python API, PyLabRobot) is open-source, physical lab automation hardware (e.g., an Opentrons robot) must be purchased. Alternatively, interfacing with a "Cloud Lab" service would involve subscription or per-experiment fees.
*   **GPU:** Not typically required; these operations are primarily CPU-bound.

### 2. `/design_protein` (Generative Structural Design)
*   **Paid Services:** Highly likely. Running deep learning models like RFdiffusion and ProteinMPNN efficiently necessitates powerful GPUs. If local GPUs are unavailable, cloud-based GPU instances (e.g., AWS, GCP, Azure) would be required, incurring costs. Even free services (e.g., ColabFold) often have usage limits or paid tiers for sustained/high-performance use.
*   **GPU:** **Essential.** Without dedicated GPU resources, computation times for protein design would be prohibitively long.

### 3. `/digital_twin` (In Silico Patient Simulation)
*   **Paid Services:** Generally no, for the open-source tools (COBRApy, Tellurium). These are CPU-bound. However, for very large-scale simulations or extensive multi-omics data management, cloud computing resources (VMs with increased RAM/CPU) may be chosen, leading to standard cloud infrastructure costs.
*   **GPU:** Not typically required; these simulations are generally CPU-intensive.

### 4. `/crispr_write` (Validated Sequence Engineering)
*   **Paid Services:** Generally no, for the open-source tools (Biopython, gRNA design algorithms). These are CPU-bound. Similar to `/digital_twin`, very large-scale genome analysis might incur cloud compute costs if local resources are insufficient.
*   **GPU:** Not typically required; these bioinformatics tasks are generally CPU-intensive.

## Phase 1: "Write Tech" Integration with Open Source

### 1. `/lab_connect` (Self-Driving Lab Integration)
*   **Problem:** Antimicrobial Resistance (AMR) – Current capability identifies novel antibiotic scaffolds in literature.
*   **"Write" Tech Integration (Potential):** Automated Chemical Synthesis and Experimental Execution. Directly interface with robotic labs to synthesize and test predicted molecules.
*   **Open Source Focus:**
    *   **Opentrons:** Leverage the Opentrons Python API for controlling robotic liquid handlers and other lab instruments.
    *   **PyLabRobot:** Explore for broader instrument control and protocol automation if Opentrons is not sufficient for specific tasks.
*   **Implementation Plan:**
    1.  Develop a new Hermes Python tool (`cryo_lab_connect.py`) that wraps the chosen open-source lab automation APIs.
    2.  Implement a command, e.g., `/lab_connect synthesize <molecule_SMILES> <quantity_mg> <binding_assay_target>`, which translates into a sequence of Opentrons/PyLabRobot commands.
    3.  Integrate a simulator mode for in-silico protocol validation.
*   **Impact:** Rapid discovery and empirical validation of non-traditional antibiotics and other bioactive molecules, moving from theoretical identification to tangible results.

### 2. `/design_protein` (Generative Structural Design)
*   **Problem:** Protein Engineering – Current capability predicts protein structures (e.g., AlphaFold).
*   **"Write" Tech Integration (Potential):** Generative Protein Design. Use deep learning models to "write" de novo enzymes or binders.
*   **Open Source Focus:**
    *   **RFdiffusion & ProteinMPNN:** Integrate community-maintained open-source implementations of these powerful generative models for protein backbone and sequence design.
    *   **AlphaFold/ColabFold:** Utilize for *in silico* structural validation of newly designed proteins.
*   **Implementation Plan:**
    1.  Set up a containerized (Docker) environment for computationally intensive protein design models (RFdiffusion, ProteinMPNN), ensuring necessary hardware acceleration (GPU) is configured.
    2.  Create a new Hermes Python tool (`cryo_design_protein.py`) exposing functions like `/design_protein enzyme <reaction_type> <active_site_definition>` or `/design_protein binder <target_protein_PDB_ID> <desired_affinity_nM>`.
    3.  The tool will orchestrate the generation of candidate protein structures and sequences, followed by optional structural validation using AlphaFold/ColabFold.
*   **Impact:** Solving environmental and industrial crises by creating novel enzymes for plastic degradation or carbon capture, and developing new therapeutic proteins.

### 3. `/digital_twin` (In Silico Patient Simulation)
*   **Problem:** Rare Genetic Diseases/Drug Toxicity – Current capability identifies causative mutations via VEP and ClinVar.
*   **"Write" Tech Integration (Potential):** Multi-omics Integration Platform using metabolic modeling to simulate drug toxicity on a virtual patient model.
*   **Open Source Focus:**
    *   **COBRApy:** A robust Python package for constraint-based reconstruction and analysis of genome-scale metabolic networks.
    *   **Tellurium/Antimony:** For dynamic modeling of biological systems, potentially complementing COBRApy.
*   **Implementation Plan:**
    1.  Develop a new Hermes Python tool (`cryo_digital_twin.py`) that leverages COBRApy for building and simulating personalized metabolic models.
    2.  Implement commands like `/digital_twin simulate_drug_response <drug_ID> <patient_omics_profile_path>` which will construct a patient-specific metabolic model, simulate drug interactions, and predict outcomes.
    3.  Integrate with open-source visualization libraries (e.g., Matplotlib, Plotly) for clear representation of simulation results.
*   **Impact:** Truly personalized curative therapies and predictive toxicology by simulating drug effects on individual patient models before clinical application, reducing risks and accelerating therapeutic development.

### 4. `/crispr_write` (Validated Sequence Engineering)
*   **Problem:** Rare Genetic Diseases – Current capability identifies causative mutations.
*   **"Write" Tech Integration (Potential):** AI-driven gRNA design with real-time off-target verification and synthesis ordering.
*   **Open Source Focus:**
    *   **Biopython:** For fundamental sequence manipulation and analysis.
    *   **Open-source gRNA design algorithms:** Integrate academic or community-developed algorithms for optimal gRNA design (e.g., scoring functions for on-target efficiency, secondary structure prediction).
    *   **Open-source off-target prediction tools:** Implement algorithms for *in silico* off-target assessment against reference genomes.
    *   **PrimeDesign:** Investigate and integrate open-source implementations for prime editing guide RNA (pegRNA) design.
*   **Implementation Plan:**
    1.  Create a new Hermes Python tool (`cryo_crispr_write.py`) to automate gRNA design for various CRISPR systems.
    2.  Implement commands like `/crispr_write design_gRNA <target_gene_ID> <mutation_details> <genome_assembly>` and subsequently for prime editing.
    3.  The tool will design optimal gRNA sequences, perform *in silico* off-target prediction, and provide comprehensive reports including on-target efficiency and off-target scores.
*   **Impact:** Precision genome engineering for therapeutic applications, enabling the development of highly specific gene therapies for genetic diseases with reduced off-target effects.

## General Architectural Considerations for Phase 1
*   **Containerization (Docker):** Encapsulate complex dependencies for each "Write Tech" tool within Docker containers to ensure isolated, reproducible, and scalable deployment.
*   **Hermes Tool Wrappers:** All "Write Tech" functionalities will be exposed as well-defined Hermes Python tools, allowing CRYO to orchestrate complex biological workflows through natural language commands.
*   **Asynchronous Operations:** Implement asynchronous processing for potentially long-running computations (e.g., protein design, simulations), providing users with real-time status updates.
*   **Data Standards:** Utilize open standards for biological data (e.g., PDB, FASTA, SBML) to ensure interoperability and ease of data exchange.
*   **User Feedback & Visualization:** Design tool outputs to be clear, concise, and actionable, potentially including links to generated reports, interactive 3D visualizations, or plots to facilitate interpretation.
