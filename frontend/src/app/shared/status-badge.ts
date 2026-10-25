import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { DocumentStatus } from '../core/api.models';

/** Processing state as a word plus a glyph, so colour is never the only signal. */
@Component({
  selector: 'dm-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="badge" [class]="'badge badge-' + view().kind">
      @if (view().kind === 'processing') {
        <span class="spinner" aria-hidden="true"></span>
      } @else {
        <span aria-hidden="true">{{ view().glyph }}</span>
      }
      {{ view().label }}
    </span>
  `,
})
export class StatusBadge {
  readonly status = input.required<DocumentStatus | 'uploading' | 'queued' | 'rejected'>();
  readonly failureCode = input<string | null>(null);

  protected readonly view = computed(() => {
    switch (this.status()) {
      case 'queued':
        return { kind: 'processing', glyph: '', label: 'Waiting' };
      case 'uploading':
        return { kind: 'processing', glyph: '', label: 'Uploading' };
      case 'processing':
        return { kind: 'processing', glyph: '', label: 'Processing' };
      case 'ready':
        return { kind: 'ready', glyph: '✓', label: 'Ready' };
      case 'rejected':
        return { kind: 'failed', glyph: '!', label: 'Not uploaded' };
      case 'failed':
        return this.failureCode() === 'no_extractable_text'
          ? { kind: 'no-text', glyph: '▢', label: 'No text found' }
          : { kind: 'failed', glyph: '!', label: 'Failed' };
    }
  });
}
