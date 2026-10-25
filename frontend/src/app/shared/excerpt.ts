import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { Span } from '../core/api.models';

interface Segment {
  text: string;
  marked: boolean;
}

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

/**
 * Document text with matched words highlighted. The text is rendered with interpolation only, so
 * anything in a document that looks like HTML stays text.
 */
@Component({
  selector: 'dm-excerpt',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'source-text' },
  styles: `
    :host {
      display: block;
    }
  `,
  // Kept on one line: the host uses white-space: pre-wrap, so template whitespace would show.
  // prettier-ignore
  template: `@if (startsMidText()) {<span aria-hidden="true">… </span>}@for (segment of segments(); track $index) {@if (segment.marked) {<mark>{{ segment.text }}</mark>} @else {<span>{{ segment.text }}</span>}}@if (endsMidText()) {<span aria-hidden="true"> …</span>}`,
})
export class Excerpt {
  readonly text = input.required<string>();
  readonly highlights = input<readonly Span[]>([]);
  readonly startsMidText = input(false);
  readonly endsMidText = input(false);

  protected readonly segments = computed(() => segmentText(this.text(), this.highlights()));
}
