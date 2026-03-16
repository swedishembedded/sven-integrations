---
name: integrations/libreoffice
description: |
  Use when asked to create documents, spreadsheets, or presentations. Trigger phrases:
  "create document", "write report", "create spreadsheet", "create presentation",
  "edit Word file", "edit Excel file", "convert to PDF", "add slide", "add table",
  "format document", "create invoice", "create resume".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-libreoffice]
---

# sven-integrations-libreoffice

Stateful CLI for LibreOffice Writer, Calc, and Impress. Creates ODF documents
natively (no LibreOffice binary required) with optional conversion to PDF/DOCX
via LibreOffice headless.

## Quick start

```bash
# Writer document
sven-integrations-libreoffice --json document new -o /tmp/doc.json --type writer
sven-integrations-libreoffice --json writer add-heading "Introduction" --level 1 -p /tmp/doc.json
sven-integrations-libreoffice --json writer add-paragraph "Body text here." -p /tmp/doc.json
sven-integrations-libreoffice --json export render output.odt -p /tmp/doc.json

# Spreadsheet
sven-integrations-libreoffice --json document new -o /tmp/sheet.json --type calc
sven-integrations-libreoffice --json calc set-cell A1 "Revenue" -p /tmp/sheet.json
sven-integrations-libreoffice --json calc set-cell B1 "=SUM(B2:B10)" -p /tmp/sheet.json
sven-integrations-libreoffice --json export render output.ods -p /tmp/sheet.json
```

## Command groups

### document
`new` (writer/calc/impress), `open`, `save`, `info`, `profiles`

### writer
`add-paragraph`, `add-heading`, `add-list`, `add-table`, `add-page-break`,
`remove`, `list`, `get`, `set-text`

### calc
`add-sheet`, `remove-sheet`, `rename-sheet`, `set-cell`, `get-cell`,
`clear-cell`, `list-sheets`, `get-data`

### impress
`add-slide`, `remove-slide`, `set-slide-content`, `add-element`,
`remove-element`, `move-slide`, `duplicate-slide`, `list`, `get`

### style
`create`, `list`, `get`, `apply`

### export
`presets`, `render` (odt/ods/odp/pdf/docx/xlsx/pptx/html/txt/csv)

### session
`undo`, `redo`, `history`

## For agents
- `export render output.pdf` requires LibreOffice installed for PDF conversion
- `export render output.odt` works without LibreOffice (pure Python ODF)
- Cell references: `A1`, `B2`, etc. (case-insensitive, normalized to uppercase)
