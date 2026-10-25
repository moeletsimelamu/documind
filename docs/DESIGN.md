# DocuMind — Design

Status: **implemented in Phase 5.** Sections 1–8 are the specification; section 9 records where
the built interface differs from it and why, after review in a browser.

## 1. Who it is for and what they do

**Primary user:** a student, researcher, analyst or consultant with a working set of 5–200 PDFs and
text files (papers, reports, contracts, meeting notes) who needs to find specific facts and be able
to show where each fact came from.

**Primary workflows, in order of frequency**

1. *Look something up:* type words → scan matching passages → open the one that looks right in
   its document to read the context.
2. *Ask a question:* type a question → read a short answer → check each cited passage → open the
   document if needed.
3. *Build the library:* drop several files → watch each one get processed → fix failures (wrong
   type, scanned PDF, too large).
4. *Tidy up:* filter the library → delete documents that are no longer needed.

The product promise is **verifiability**: every answer and result leads back to the exact text it
came from in one click.

## 2. Visual direction — "reading desk"

DocuMind should feel like a well-made reference tool: quiet chrome, dense but calm lists, and
**document text that looks like print**. The interface is sans-serif; anything quoted from a user's
document is set in a serif. That one rule carries most of the distinction between *what the
documents say* and *what the application or the AI says*.

Deliberately avoided: gradients, glass effects, glows, chat bubbles, sparkle/"magic" icons, metric
cards, large rounded containers nested inside each other, illustrations in empty states, and
decorative animation.

Distinct from OpsHub (the previous project): OpsHub uses warm "paper" neutrals, a teal accent, IBM
Plex and a sidebar. DocuMind uses cool neutrals, an ink-navy top bar, a blue accent with an amber
"highlighter", and the Source Sans 3 / Source Serif 4 pairing.

## 3. Colour

All text pairs below were measured (WCAG 2.x relative-luminance formula) on 2026-10-25.

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--ink` | `#162036` | Body text; top bar background | 16.2:1 on white |
| `--ink-muted` | `#4A5568` | Secondary text, metadata | 7.5:1 on white, 7.0:1 on desk |
| `--ink-subtle` | `#5E6878` | Hints, timestamps | 5.6:1 on white, 5.2:1 on desk |
| `--desk` | `#F5F7FA` | App background | — |
| `--surface` | `#FFFFFF` | Lists, panels, inputs, reader page | — |
| `--line` | `#D9DEE5` | Dividers | — |
| `--line-strong` | `#7D8796` | Input and control borders | 3.6:1 (≥ 3:1 for UI components) |
| `--accent` | `#2547C4` | Links, primary button, focus ring, generated-answer rule | 7.6:1 on white; white on it 7.6:1 |
| `--accent-hover` | `#1B379C` | Hover / pressed | — |
| `--accent-soft` | `#E8EDFC` | Selected row, active nav, info banner | accent text 6.5:1 |
| `--highlight` | `#FFE680` | Matched search terms, the cited passage being inspected | ink 13.0:1 |
| `--source-rule` | `#B7791F` | 3px left rule on quoted source text (decorative, paired with labels) | 3.6:1 |
| `--danger` / `--danger-soft` | `#B3261E` / `#FCEBEA` | Errors, delete, Failed | 6.5:1 / 5.7:1 |
| `--warning` / `--warning-soft` | `#8A5A00` / `#FDF3DC` | No text found, provider unavailable | 5.9:1 / 5.4:1 |
| `--success` / `--success-soft` | `#1F6F43` / `#E6F3EC` | Ready, uploaded | 6.2:1 / 5.4:1 |
| Top bar text / muted / focus | `#FFFFFF` / `#AEB8C8` / `#8FB0FF` on `--ink` | Navigation | 16.2 / 8.1 / 7.6:1 |

Colour is never the only signal: every status has a word and a glyph.

## 4. Typography

Self-hosted with `@fontsource` packages (no requests to font CDNs).

- **Source Sans 3** — interface: navigation, labels, buttons, tables, generated answers.
- **Source Serif 4** — document text: excerpts, search results, cited passages, the reader.
- **Tabular numerals** for sizes, page numbers and counts.

| Token | Size / line height | Use |
|---|---|---|
| `--text-xs` | 12 / 16px | Badges, metadata |
| `--text-sm` | 14 / 20px | Tables, labels, buttons |
| `--text-md` | 16 / 24px | Body, generated answers, inputs |
| `--text-read` | 17 / 28px (serif) | Reader and excerpts; measure capped at 68ch |
| `--text-lg` | 20 / 28px | Section headings |
| `--text-xl` | 26 / 32px | Page titles |

Weights: 400, 600 (headings, labels). No weights above 600.

## 5. Space, shape, elevation, motion

- 4px base scale: 4, 8, 12, 16, 24, 32, 48.
- Radius: 3px (inputs, badges), 6px (buttons, panels, dialogs). Lists are not wrapped in cards.
- Separation by 1px lines and whitespace; a shadow only on floating layers (dialogs, menus, toasts).
- Motion only for state changes the user caused (overlay open, row removed), 150ms, disabled under
  `prefers-reduced-motion`. Spinners appear only while a request or processing job is actually
  running.
- Focus: 2px `--accent` outline with 2px offset on every interactive element (`#8FB0FF` on the top bar).

## 6. Layout and navigation

```
┌───────────────────────────────────────────────────────────────┐
│ DocuMind   Library   Search   Ask              [ Search… ⏎ ]   │  ink top bar, 56px
├───────────────────────────────────────────────────────────────┤
│                         page content                           │  desk background
```

- Routes: `/library` (default), `/documents/:id`, `/search?q=`, `/ask`. The search field in the top
  bar navigates to `/search?q=…`. Unknown routes show a plain not-found page.
- Breakpoints: **≥ 1024px** desktop (two-column Ask and reader); **640–1023px** tablet (one column,
  sources below the answer); **< 640px** mobile (nav becomes a row of three tabs under the wordmark;
  tables become stacked rows; no horizontal scrolling).

### Library

- Title row: "Library" + "14 documents".
- **Upload strip:** a slim dashed-border drop target with "Choose files" button: "PDF or TXT, up to
  20 MB each. Text-based PDFs only — scanned pages can't be read." Accepts several files; each is
  uploaded in its own request (two at a time).
- **Upload queue** directly below while active: one row per file with real byte progress, then
  "Processing…", then the outcome. Rejected files show the server's reason inline ("Not a PDF",
  "Larger than 20 MB", "Already in your library — open").
- **Filter bar:** name filter + status filter (All / Ready / Processing / Failed).
- **Table:** Name (link to reader) · Type · Pages · Size · Added · Status · actions menu (Open,
  Download original, Delete). Failed rows show the failure explanation under the name.
- **Empty state:** "Your library is empty. Upload PDFs or text files to search them and ask
  questions about them." + the upload button. Filtered-empty: "No documents match 'x'." + Clear
  filter.
- Polling: while any document is `processing`, the list refreshes it every 2 seconds; polling
  stops when none are processing.

### Document reader

- Header: name, "PDF · 42 pages · 1.8 MB · added 25 Oct 2026", status, Download original, Delete
  (confirmation dialog naming the file and what will be removed).
- Note above the text: "Extracted text — layout, images and tables from the original are not shown."
- Desktop: a narrow page index on the left ("p. 1 … p. 42") for jumping; the text in serif on a
  white page, with small-caps "PAGE 3" dividers.
- **Opened from a citation or result** (`?chunk=123`): that passage is scrolled into view, given the
  highlighter background and amber rule, and receives focus so screen readers announce it.

### Search

- Query field (pre-filled from the URL), document filter, result count: "23 passages in 5 documents".
- Each result: document name · "p. 7" (or "lines 120–140") as a link → excerpt in serif with matched
  words highlighted → "Open in document".
- Copy is honest about the method: helper text "Matches words and word forms, not meaning."
- Empty: "No passages contain these words. Try fewer words or a different term."

### Ask

- Desktop: left column is the question/answer thread; right column (sticky) is **Sources** for the
  selected answer. Tablet/mobile: sources follow each answer.
- The thread is not a chat: each entry is the question as a heading, then the response block.
  Entries live only in the browser tab for this session; this is stated in the empty state.
- Response blocks by mode — the visual language is fixed across the app:

| Mode | Label | Treatment |
|---|---|---|
| `generated` | "Answer · generated by {model} from 3 sources" | Sans text, 3px **accent** left rule, inline markers `[S1]` as buttons |
| `retrieval_only` | "AI answers are off — most relevant passages" | No answer block; passages only |
| `insufficient_evidence` | "Not enough in your documents to answer this" | Neutral notice; closest passages (if any) labelled "closest matches" |
| provider error | "The AI provider didn't respond — showing passages instead" | Warning banner + passages |

- **Sources** are always serif with the **amber** left rule, labelled `S1`, document name and page.
  Activating a marker `[S2]` selects and highlights that source in the panel without moving the
  reading position in the answer; "Open in document" goes to the reader at that passage.
- Composer: multi-line field (Enter submits, Shift+Enter new line), optional document scope,
  submit button disabled with a spinner while a request is in flight (prevents duplicate submits).

## 7. Components

| Component | Rules |
|---|---|
| Button | Primary (one per view), secondary (bordered), quiet (text), danger. 36px high, 44px on touch. Keeps width while busy. |
| Status badge | Word + glyph: `◌ Processing` (accent), `✓ Ready` (success), `! Failed` (danger), `▢ No text found` (warning). |
| Banner | Inline info / warning / error with an action where one exists (e.g. "Retry"). |
| Toast | Short confirmation ("Deleted report.pdf"), polite live region, 4s; never for errors that need action. |
| Dialog | Native `<dialog>` with `showModal()`: background inert, Esc closes, focus returns to the trigger (or to the page if the trigger was removed). Used for delete confirmation. |
| Excerpt | Serif text, amber rule, source label line; highlight spans rendered as text nodes. |
| Skeleton | Line-shaped placeholders while first loading; announced "Loading…". |
| API unavailable | Full-width banner "Can't reach the DocuMind server. Retrying…" with manual retry; existing content stays visible. |

Icons: a small set of inline SVGs (upload, search, file, trash, external, chevron, alert, check),
16px, `currentColor`, `aria-hidden` when next to text. No icon library dependency.

## 8. Accessibility targets

- WCAG 2.2 AA contrast (table above), visible focus everywhere, logical tab order, skip link.
- Every control has an accessible name; status changes in the upload queue and Ask responses are
  announced through polite live regions.
- Drop zone is also a normal file button; nothing requires drag and drop.
- Usable at 320px width and at 200% zoom without horizontal scrolling.
- Checked in Phase 9 with keyboard-only walkthroughs and automated checks; results go in REVIEW.md.

## 9. As built (Phase 5)

Checked in the in-app browser at 1280×800 and 375×812 against the real API. Differences from the
specification above:

| Area | Specification | Built | Why |
|---|---|---|---|
| Dialog | Angular CDK dialog | Native `<dialog>` | The platform element provides modality, inert background and Esc; no extra dependency. |
| Reader | Page index column for jumping | Page dividers in the text; passages load 60 at a time with "Show earlier text" / "Show more text" | The API pages passages by position, not by page; an index would need a new endpoint. Citations still open at the exact passage. |
| Ask layout | Thread with a sticky Sources column | Composer at the top, newest question first; in retrieval-only mode the passages *are* the response and are shown inline as numbered sources S1…Sn | Without generated text there is nothing for a side panel to annotate. The side panel is revisited with generated answers in Phase 6. |
| Library filters | (not specified) | Name and status filters work on the loaded list, instantly | A single user's library is small; the server-side filters remain available in the API. |
| Upload queue | (not specified) | Shown in the order files were chosen, two uploads at a time, real byte progress, then the server's processing state | — |
| Skeleton | Animated placeholders | Static grey bars | Avoids motion with no information value. |
| Fonts | Source Sans 3 / Source Serif 4 | Latin subsets only: Sans 400/600, Serif 400/400 italic/600, self-hosted | Smaller downloads; no third-party font requests. |

Status words in use: *Waiting*, *Uploading*, *Processing* (with a spinner), *Ready* ✓, *Failed* !,
*No text found* ▢ (scanned PDFs), *Not uploaded* ! (rejected before or at upload).

Outage handling: if the API cannot be reached, a banner says so, existing content stays on screen,
the health endpoint is polled every 5 s, and configuration and the library reload when it answers.
