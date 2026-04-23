# CRYO Workspace — Multi-Canvas Research UI

## Concept

A visual research workspace where each conversation is a **node** on an infinite canvas. Users branch from any response to create new nodes, building a **research flowchart** over time.

## What It Looks Like

### Starting State (empty workspace)
```
┌──────────────────────────────────────────────────────────┐
│  CRYO Workspace                              [+ New Node]│
│                                                          │
│                                                          │
│                    ┌─────────────┐                       │
│                    │  + Start    │                       │
│                    │  Research   │                       │
│                    └─────────────┘                       │
│                                                          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### After first query: "/protein TP53"
```
┌──────────────────────────────────────────────────────────┐
│  CRYO Workspace                              [+ New Node]│
│                                                          │
│  ┌──────────────────────────────┐                        │
│  │ 🧬 /protein TP53             │                        │
│  │                              │                        │
│  │ TP53 is a tumor suppressor   │                        │
│  │ protein encoded by the TP53  │                        │
│  │ gene. Function: DNA damage   │                        │
│  │ response, cell cycle arrest  │                        │
│  │ ...                          │                        │
│  │                              │                        │
│  │ [+Branch] [📋Copy] [🔗Link] │                        │
│  │ ┌──────────────────────────┐ │                        │
│  │ │ Ask follow-up...    [▶] │ │                        │
│  │ └──────────────────────────┘ │                        │
│  └──────────────────────────────┘                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### After branching: user hovers on "DNA damage response" → clicks [+Branch]
```
┌──────────────────────────────────────────────────────────────────────┐
│  CRYO Workspace                                        [+ New Node] │
│                                                                      │
│  ┌────────────────────────┐                                          │
│  │ 🧬 /protein TP53       │                                          │
│  │                        │         ┌────────────────────────┐       │
│  │ TP53 is a tumor        │────────▶│ 🔬 DNA damage response │       │
│  │ suppressor protein...  │         │                        │       │
│  │                        │         │ What drugs target the  │       │
│  │ • DNA damage response ◀──branch  │ DNA damage response    │       │
│  │ • Cell cycle arrest    │         │ pathway?               │       │
│  │ • Apoptosis            │         │                        │       │
│  │                        │         │ PARP inhibitors like   │       │
│  │ [Ask follow-up...]     │         │ Olaparib exploit...    │       │
│  └────────────────────────┘         │                        │       │
│                                      │ [Ask follow-up...]     │       │
│                                      └────────────────────────┘       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Full research session — the flowchart emerges
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CRYO Workspace                                              [+ New Node]   │
│                                                                              │
│                        ┌─────────────┐                                       │
│                        │ 🧬 TP53      │                                       │
│                        │ protein info │                                       │
│                        └──────┬──────┘                                       │
│                    ┌──────────┼──────────┐                                   │
│                    ▼          ▼          ▼                                   │
│            ┌───────────┐ ┌────────┐ ┌──────────┐                            │
│            │ 🔬 DNA     │ │ 💊 Drug│ │ 🧪 Variant│                            │
│            │ damage     │ │ targets│ │ rs28934  │                            │
│            │ pathway    │ │ for p53│ │ 578      │                            │
│            └─────┬─────┘ └───┬────┘ └──────────┘                            │
│                  │           │                                               │
│                  ▼           ▼                                               │
│          ┌───────────┐ ┌─────────────┐                                      │
│          │ 📋 PARP    │ │ 📊 Report:  │                                      │
│          │ inhibitors │ │ TP53 in     │                                      │
│          │ comparison │ │ cancer      │                                      │
│          └───────────┘ └─────────────┘                                      │
│                                                                              │
│  ─── Zoom: [−] 75% [+] ── Pan: drag background ── Minimap: [□] ───        │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Node Anatomy

Each node is a mini-chat canvas:
```
┌──────────────────────────────────────┐
│ 🧬 Title (auto from first query)  ×  │  ← Header: icon + title + close
│──────────────────────────────────────│
│                                      │
│ [User message]                       │  ← Chat messages
│                                      │
│ [Assistant response with             │
│  markdown, tables, etc.]             │
│                                      │
│ [User follow-up]                     │
│                                      │
│ [Assistant response]                 │
│  ↑ hover shows [+Branch] button      │  ← Branch point
│                                      │
│──────────────────────────────────────│
│ [Ask follow-up...              ▶]   │  ← Input field
│──────────────────────────────────────│
│ 💬 4 messages  ·  2 tools used       │  ← Footer stats
└──────────────────────────────────────┘
```

## Interactions

### Creating Nodes
- **[+ New Node]** button → empty node appears at center
- **[+Branch]** on hover over any assistant response → new node spawned to the right, connected with an arrow, pre-filled with that response as context

### Node Actions
- **Drag** header to reposition
- **Resize** from edges/corners
- **Minimize** → collapses to just the title bar
- **Maximize** → expands to fill workspace
- **Close** → removes from workspace (conversation stays in DB)
- **Double-click title** → rename

### Canvas Controls
- **Pan** → drag empty space or middle-mouse
- **Zoom** → scroll wheel or pinch, or [−][+] buttons
- **Minimap** → small overview in corner showing all nodes
- **Auto-layout** button → arranges nodes in a clean tree layout
- **Fit all** → zoom to fit all nodes in view

### Connections
- Solid arrow from parent node to child (branch)
- Arrow label shows the branching context (truncated response text)
- Click arrow to highlight the source message in parent node

## Data Model

```
workspace
  └── nodes[]
       ├── id: uuid
       ├── conversation_id: uuid (maps to PG conversations table)
       ├── parent_node_id: uuid | null
       ├── branch_from_message_id: uuid | null
       ├── position: {x, y}
       ├── size: {w, h}
       ├── minimized: boolean
       └── title: string

workspace stored in localStorage (positions/layout)
conversations stored in PostgreSQL (messages/content)
```

## Example Research Session

1. User creates first node: `/protein EGFR`
   → Gets protein info with domains, mutations, pathways

2. User hovers on "EGFR is commonly mutated in NSCLC" → clicks [+Branch]
   → New node spawns: "Tell me more about EGFR mutations in NSCLC"
   → Gets detailed mutation landscape (L858R, exon 19 del, T790M)

3. User hovers on "Osimertinib targets T790M" → clicks [+Branch]
   → New node: `/drug osimertinib`
   → Gets ChEMBL data, clinical trials, mechanism

4. User creates standalone node [+]: `/report EGFR targeted therapy landscape`
   → Gets full research report with all the context from exploring

5. Final workspace looks like a research tree:
   ```
   EGFR protein → NSCLC mutations → Osimertinib drug info
                                   → Resistance mechanisms
                → Colorectal cancer → Cetuximab vs Panitumumab
   EGFR report (standalone)
   ```

## Tech Stack

- **React Flow** or custom canvas with CSS transforms for pan/zoom
- Each node = a `<ChatCanvas>` component with its own conversation state
- Connections rendered with SVG paths between nodes
- Positions saved to localStorage, conversations to PostgreSQL
- Branch context passed via conversation_history to Hermes

## Comparison

| Feature | Current Chat UI | Workspace UI |
|---------|----------------|-------------|
| Conversations | One at a time, sidebar list | Multiple visible simultaneously |
| Context | Linear, single thread | Branching tree, visual connections |
| Research flow | Sequential | Parallel exploration |
| Overview | None (scroll through history) | Bird's-eye view of all research |
| Branching | Start new chat, lose context | Branch from any response, keep context |
