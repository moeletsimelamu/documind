import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { Span } from '../core/api.models';

interface Segment {
  text: string;
  marked: boolean;
}

/** An excerpt split around its best-matching sentence. Exported for tests. */
export interface ExcerptParts {
  before: Segment[];
  best: Segment[];
  after: Segment[];
  /** No sentence stands out (one sentence, or no matches): matched words are highlighted instead. */
  wordMarks: boolean;
}

/** A sentence ends at . ! ? (and any closing quote or bracket) before a space, or at a line break. */
const SENTENCE_END = /([.!?]['"’”)\]]*)\s+|\n+/g;

/** A best sentence longer than this share of the excerpt is not worth singling out. */
const MAX_BEST_SHARE = 0.7;

/** Splits text at highlight offsets. Exported for tests. */
export function segmentText(text: string, highlights: readonly Span[]): Segment[] {
  const segments: Segment[] = [];
  let position = 0;
  const ordered = [...highlights].sort((a, b) => a[0] - b[0]);
  for (const [start, end] of ordered) {
    if (start < position || end > text.length || start >= end) {
      continue; // overlapping or out-of-range spans are ignored rather than trusted
    }
    if (start > position) {
      segments.push({ text: text.slice(position, start), marked: false });
    }
    segments.push({ text: text.slice(start, end), marked: true });
    position = end;
  }
  if (position < text.length) {
    segments.push({ text: text.slice(position), marked: false });
  }
  return segments;
}

/** [start, end) of each sentence, without surrounding whitespace. Exported for tests. */
export function sentenceSpans(text: string): Span[] {
  const spans: Span[] = [];
  const add = (start: number, end: number) => {
    while (start < end && /\s/.test(text[start])) start++;
    while (end > start && /\s/.test(text[end - 1])) end--;
    if (end > start) spans.push([start, end]);
  };
  let start = 0;
  for (const match of text.matchAll(SENTENCE_END)) {
    const index = match.index ?? 0;
    add(start, index + (match[1]?.length ?? 0));
    start = index + match[0].length;
  }
  add(start, text.length);
  return spans;
}

/**
 * The sentence containing the most different matched words (then the most matches, then the
 * earliest), or null when nothing matched. Exported for tests.
 */
export function bestSentence(text: string, highlights: readonly Span[]): Span | null {
  let best: Span | null = null;
  let bestDistinct = 0;
  let bestCount = 0;
  for (const [start, end] of sentenceSpans(text)) {
    const inside = highlights.filter(([s, e]) => s >= start && e <= end && s < e);
    const distinct = new Set(inside.map(([s, e]) => text.slice(s, e).toLowerCase())).size;
    if (distinct > bestDistinct || (distinct === bestDistinct && inside.length > bestCount)) {
      best = [start, end];
      bestDistinct = distinct;
      bestCount = inside.length;
    }
  }
  return best;
}

/** Lower-case words of three or more letters, and numbers ("15"). */
function words(text: string): Set<string> {
  const tokens = text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  return new Set(tokens.filter((t) => t.length >= 3 || /^\p{N}+$/u.test(t)));
}

/** Fewest words a sentence must share with the reference text to count as supporting it. */
const MIN_SHARED_WORDS = 3;

/**
 * The sentence most covered by ``reference`` (e.g. a generated answer that cites this passage):
 * the largest share of its words that also appear in the reference, with at least
 * MIN_SHARED_WORDS in common. Measured as a share, not a count, so that a long sentence does not
 * win merely by containing more words. Null when no sentence qualifies. Exported for tests.
 */
export function supportingSentence(text: string, reference: string): Span | null {
  const wanted = words(reference);
  let best: Span | null = null;
  let bestShare = 0;
  for (const [start, end] of sentenceSpans(text)) {
    const own = words(text.slice(start, end));
    const shared = [...own].filter((w) => wanted.has(w)).length;
    const share = own.size ? shared / own.size : 0;
    if (shared >= MIN_SHARED_WORDS && share > bestShare) {
      best = [start, end];
      bestShare = share;
    }
  }
  return best;
}

/** Highlights within [from, to), shifted to start at ``from``. */
function clip(highlights: readonly Span[], from: number, to: number): Span[] {
  return highlights
    .filter(([s, e]) => s >= from && e <= to)
    .map(([s, e]): Span => [s - from, e - from]);
}

/**
 * Splits an excerpt around the sentence to emphasise: the one supporting ``reference`` when given
 * and found, otherwise the best match for the query. Exported for tests.
 */
export function excerptParts(
  text: string,
  highlights: readonly Span[],
  reference: string | null = null,
): ExcerptParts {
  const sentence =
    (reference ? supportingSentence(text, reference) : null) ?? bestSentence(text, highlights);
  const length = text.trim().length;
  if (!sentence || sentence[1] - sentence[0] > MAX_BEST_SHARE * length) {
    return { before: segmentText(text, highlights), best: [], after: [], wordMarks: true };
  }
  const [start, end] = sentence;
  return {
    before: segmentText(text.slice(0, start), clip(highlights, 0, start)),
    best: segmentText(text.slice(start, end), clip(highlights, start, end)),
    after: segmentText(text.slice(end), clip(highlights, end, text.length)),
    wordMarks: false,
  };
}

/**
 * Document text with the sentence that best matches the query highlighted, and the matched words
 * underlined. A short excerpt with no stand-out sentence highlights the matched words instead.
 * The text is rendered with interpolation only, so anything in a document that looks like HTML
 * stays text.
 */
@Component({
  selector: 'dm-excerpt',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'source-text' },
  styles: `
    :host {
      display: block;
    }
    .term {
      text-decoration: underline;
      text-decoration-color: var(--source-rule);
      text-decoration-thickness: 2px;
      text-underline-offset: 0.2em;
    }
    .best {
      padding: 0.1em 0;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }
  `,
  // Kept on one line: the host uses white-space: pre-wrap, so template whitespace would show.
  // prettier-ignore
  template: `@if (startsMidText()) {<span aria-hidden="true">… </span>}@for (segment of parts().before; track $index) {@if (segment.marked && parts().wordMarks) {<mark>{{ segment.text }}</mark>} @else {<span [class.term]="segment.marked">{{ segment.text }}</span>}}@if (parts().best.length) {<mark class="best">@for (segment of parts().best; track $index) {<span [class.term]="segment.marked">{{ segment.text }}</span>}</mark>}@for (segment of parts().after; track $index) {<span [class.term]="segment.marked">{{ segment.text }}</span>}@if (endsMidText()) {<span aria-hidden="true"> …</span>}`,
})
export class Excerpt {
  readonly text = input.required<string>();
  readonly highlights = input<readonly Span[]>([]);
  readonly startsMidText = input(false);
  readonly endsMidText = input(false);
  /** Text this passage supports, e.g. the answer that cites it: its closest sentence is shown. */
  readonly reference = input<string | null>(null);

  protected readonly parts = computed(() =>
    excerptParts(this.text(), this.highlights(), this.reference()),
  );
}
