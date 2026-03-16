---
name: integrations/mermaid
description: |
  Use when asked to create diagrams as code using Mermaid syntax — flowcharts,
  sequence diagrams, class diagrams, Gantt charts, ER diagrams, state diagrams.
  Trigger phrases: "create Mermaid diagram", "flowchart", "sequence diagram",
  "class diagram", "Gantt chart", "diagram as code", "render Mermaid".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-mermaid]
---

# sven-integrations-mermaid

CLI for Mermaid diagram rendering. Renders diagrams via mermaid.ink API and
generates shareable Mermaid Live links.

## Quick start

```bash
sven-integrations-mermaid --json project new -o /tmp/diagram.json
sven-integrations-mermaid --json diagram set 'flowchart LR\n  A-->B\n  B-->C' -p /tmp/diagram.json
sven-integrations-mermaid --json export render output.png -p /tmp/diagram.json
sven-integrations-mermaid --json export share -p /tmp/diagram.json
```

## Command groups

### project
`new`, `open`, `save`, `info`, `list-samples`

### diagram
`set`, `show`

### export
`render` (downloads PNG via mermaid.ink), `share` (generates Live URL)

### session
`undo`, `redo`, `history`

## Mermaid diagram types

```
flowchart LR        # Flowchart (left-right)
sequenceDiagram     # Sequence diagram
classDiagram        # Class diagram
erDiagram           # Entity-relationship
gantt               # Gantt chart
stateDiagram-v2     # State machine
pie                 # Pie chart
gitGraph            # Git branch diagram
```

## For agents
- `diagram set` accepts the full Mermaid code string
- `export render` requires internet access (uses mermaid.ink)
- `export share` outputs a URL to Mermaid Live for the diagram
- No local Mermaid binary needed; all rendering is cloud-based
