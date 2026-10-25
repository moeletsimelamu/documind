import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { SearchHit } from '../core/api.models';
import { locationLabel } from '../core/format';
import { Excerpt } from './excerpt';
import { Icon } from './icon';

/**
 * A passage quoted from a document: where it comes from, the excerpt (serif, with the amber
 * source rule), and a link that opens the document at that passage.
 */
@Component({
  selector: 'dm-passage-card',
  imports: [RouterLink, Excerpt, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    :host {
      display: block;
      padding: var(--space-3) var(--space-4);
      border: 1px solid var(--line);
      border-left: 3px solid var(--source-rule);
      border-radius: 0 var(--radius-md) var(--radius-md) 0;
      background: var(--surface);
    }
    .source {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: var(--space-1) var(--space-2);
      margin-bottom: var(--space-2);
      font-size: var(--text-sm);
    }
    .label {
      padding: 0 var(--space-1);
      border-radius: var(--radius-sm);
      background: var(--warning-soft);
      color: var(--warning);
      font-size: var(--text-xs);
      font-weight: 600;
    }
    .doc {
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .where {
      color: var(--ink-subtle);
    }
    .open {
      display: inline-flex;
      align-items: center;
      gap: var(--space-1);
      margin-top: var(--space-2);
      font-size: var(--text-sm);
      font-weight: 600;
      text-decoration: none;
    }
    .open:hover {
      text-decoration: underline;
    }
  `,
  template: `
    <div class="source">
      @if (label()) {
        <span class="label">{{ label() }}</span>
      }
      <span class="doc">{{ hit().document_name }}</span>
      @if (where()) {
        <span class="where tabular">{{ where() }}</span>
      }
    </div>
    <dm-excerpt
      [text]="hit().excerpt"
      [highlights]="hit().highlights"
      [startsMidText]="hit().excerpt_starts_mid_text"
      [endsMidText]="hit().excerpt_ends_mid_text"
    />
    <a
      class="open"
      [routerLink]="['/documents', hit().document_id]"
      [queryParams]="{ chunk: hit().chunk_id }"
      [attr.aria-label]="
        'Open ' + hit().document_name + (where() ? ', ' + where() : '') + ' at this passage'
      "
    >
      Open in document <dm-icon name="arrow-right" />
    </a>
  `,
})
export class PassageCard {
  readonly hit = input.required<SearchHit>();
  /** e.g. "S1" when the passage is a numbered source. */
  readonly label = input<string | null>(null);

  protected readonly where = computed(() => locationLabel(this.hit()));
}
