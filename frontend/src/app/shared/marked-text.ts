import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { Span } from '../core/api.models';
import { segmentText } from './excerpt';

/**
 * A whole passage with the words found by "find in document" marked. Rendered with interpolation
 * only, so document text that looks like HTML stays text.
 */
@Component({
  selector: 'dm-marked-text',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'source-text' },
  styles: `
    :host {
      display: block;
    }
  `,
  // Kept on one line: the host uses white-space: pre-wrap, so template whitespace would show.
  // prettier-ignore
  template: `@for (segment of segments(); track $index) {@if (segment.marked) {<mark>{{ segment.text }}</mark>} @else {<span>{{ segment.text }}</span>}}`,
})
export class MarkedText {
  readonly text = input.required<string>();
  readonly highlights = input<readonly Span[]>([]);

  protected readonly segments = computed(() => segmentText(this.text(), this.highlights()));
}
