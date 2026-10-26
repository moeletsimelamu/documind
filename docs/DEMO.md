# DocuMind — five-minute demonstration

A script for showing DocuMind to someone. It uses fictional documents and runs with AI answers off
(nothing to configure, nothing paid). Times are approximate.

**Before you start:** run DocuMind (README, "Running as one process", or the container in
DEPLOYMENT.md) with an empty library, and have the five demo files to hand. Generate them from
the evaluation set, into a folder outside the repository (`../../demo-docs` here), with the
backend's virtual environment active:

```bash
cd backend
python -c "import pathlib,sys; sys.path.insert(0,'.'); from tests.eval.dataset import DOCUMENTS; from tests.pdf_factory import make_pdf; o=pathlib.Path(sys.argv[1]); o.mkdir(exist_ok=True); [ (o/d.name).write_bytes(make_pdf(d.pages) if d.pages else d.text.encode()) for d in DOCUMENTS ]; (o/'scanned-delivery-note.pdf').write_bytes(make_pdf([None,None]))" ../../demo-docs
```

This writes four fictional documents (two text files, two PDFs) and a two-page PDF with no text
layer, standing in for a scan.

## 1. The problem (30 s)

"Facts are spread across PDFs and notes. Searching them by hand is slow, and when a tool gives an
answer you need to know where it came from. DocuMind finds the passage and always shows its
source."

## 2. Build the library (1 min)

1. Open **Library**: the empty state explains what to do.
2. Drag all five files in at once. Point out real upload progress, then *Processing*, then
   *Ready* — each PDF is parsed in a separate, time-limited process.
3. `scanned-delivery-note.pdf` ends as **No text found** with the reason: DocuMind says what it
   cannot read instead of pretending.
4. Drop `northwind-staff-handbook.txt` again: **"Already in your library"**, with a link.

## 3. Search (1 min)

1. Top-bar search: `supplier delivery delays`. Matches are highlighted, including other word forms
   ("delayed", "deliveries"); each result shows document and page.
2. Note the hint: it matches words, not meaning — said plainly in the interface.
3. **Open in document** on the Kestrel Boxes result: the reader opens on page 2 with that passage
   highlighted and focused.

## 4. Ask (1.5 min)

1. **Ask**: "How many days of paid vacation do full-time staff get?" The answer is the most relevant
   passages, numbered S1, S2…, each with its source.
2. Ask "Who won the rugby final?": **"Not enough in your documents to answer this"** — no
   invented answer.
3. If an AI model is configured: the same question returns a short generated answer with citation
   chips; clicking one highlights its source beside the answer. Citations to passages that were not
   retrieved are removed on the server.

## 5. Clean up and close (1 min)

1. Delete `q3-operations-report.pdf`: the dialog names exactly what will be removed; afterwards
   searching `Kestrel` finds nothing — the index entries went with it.
2. Close with what is *not* claimed: single user (no accounts), keyword search rather than
   semantic search (with its measured limits in ARCHITECTURE.md §7), and a self-review rather than
   an independent audit (docs/REVIEW.md).
