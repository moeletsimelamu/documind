import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AskSessionService } from '../../core/ask-session.service';
import { ConfigService } from '../../core/config.service';
import { plural } from '../../core/format';
import { LibraryStore } from '../../core/library.store';
import { Icon } from '../../shared/icon';
import { PassageCard } from '../../shared/passage-card';

@Component({
  selector: 'dm-ask-page',
  imports: [PassageCard, Icon, RouterLink],
  templateUrl: './ask-page.html',
  styleUrl: './ask-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AskPage {
  protected readonly session = inject(AskSessionService);
  protected readonly config = inject(ConfigService);
  protected readonly library = inject(LibraryStore);

  private readonly questionField =
    viewChild.required<ElementRef<HTMLTextAreaElement>>('questionField');
  protected readonly draft = signal('');
  protected readonly scope = signal('');
  protected readonly plural = plural;

  protected readonly maxChars = computed(() => this.config.config().max_question_chars);
  protected readonly tooLong = computed(() => this.draft().length > this.maxChars());
  protected readonly canAsk = computed(
    () => this.draft().trim().length > 0 && !this.tooLong() && !this.session.busy(),
  );

  /** For screen readers: announces when a response arrives. */
  protected readonly announcement = computed(() => {
    const latest = this.session.entries()[0];
    if (!latest || latest.state === 'loading') {
      return latest ? 'Looking for relevant passages…' : '';
    }
    if (latest.state === 'error') {
      return `The question could not be answered: ${latest.error?.message}`;
    }
    const response = latest.response!;
    return response.mode === 'insufficient_evidence'
      ? 'Not enough in your documents to answer this.'
      : `Response ready with ${plural(response.passages.length, 'source')}.`;
  });

  protected submit(event?: Event): void {
    event?.preventDefault();
    if (!this.canAsk()) {
      return;
    }
    const scopeId = this.scope() || null;
    const scopeName = scopeId ? (this.library.byId().get(scopeId)?.name ?? null) : null;
    this.session.ask(this.draft().trim(), scopeId, scopeName);
    // Clear the element itself: if Enter arrives before the next render, a [value] binding would
    // see no change ('' → '') and leave the old text in the field.
    this.questionField().nativeElement.value = '';
    this.draft.set('');
  }

  protected onKeydown(event: KeyboardEvent): void {
    // Enter asks; Shift+Enter starts a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      this.submit(event);
    }
  }
}
