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

import { AskResponse } from '../../core/api.models';
import { AskSessionService } from '../../core/ask-session.service';
import { ConfigService } from '../../core/config.service';
import { plural } from '../../core/format';
import { LibraryStore } from '../../core/library.store';
import { Icon } from '../../shared/icon';
import { PassageCard } from '../../shared/passage-card';
import { AnswerPart, splitCitations } from './citations';

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
  /** The source last opened from a citation marker, as "<entry id>:<marker>". */
  private readonly selectedSource = signal<string | null>(null);
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
    switch (response.mode) {
      case 'insufficient_evidence':
        return 'Not enough in your documents to answer this.';
      case 'generated':
        return `Answer ready, citing ${plural(response.cited.length, 'source')}.`;
      default:
        return `${response.generation_error ? 'No AI answer. ' : ''}Response ready with ${plural(response.passages.length, 'source')}.`;
    }
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

  protected answerParts(response: AskResponse): AnswerPart[] {
    return splitCitations(response.answer ?? '', response.cited);
  }

  protected sourceElementId(entryId: number, marker: string): string {
    return `entry-${entryId}-source-${marker}`;
  }

  protected isSelected(entryId: number, marker: string): boolean {
    return this.selectedSource() === `${entryId}:${marker}`;
  }

  /** Highlights a cited source and brings it into view without moving the answer. */
  protected showSource(entryId: number, marker: string): void {
    this.selectedSource.set(`${entryId}:${marker}`);
    const element = document.getElementById(this.sourceElementId(entryId, marker));
    if (!element) {
      return;
    }
    const behavior: ScrollBehavior = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 'auto'
      : 'smooth';
    const panel = element.closest<HTMLElement>('.sources-panel');
    if (panel && panel.scrollHeight > panel.clientHeight) {
      // Wide layout: the sources panel scrolls on its own beside the answer. scrollIntoView
      // would scroll the page too and push the answer out of view, so instead: if the panel runs
      // off the bottom of the window, bring the answer-and-sources row to the top (the answer
      // stays on screen), then scroll only the panel.
      const row = element.closest<HTMLElement>('.answer-layout');
      if (row && panel.getBoundingClientRect().bottom > window.innerHeight) {
        window.scrollBy({ top: row.getBoundingClientRect().top - 16, behavior });
      }
      const top = element.offsetTop;
      const visible =
        top >= panel.scrollTop &&
        top + element.offsetHeight <= panel.scrollTop + panel.clientHeight;
      if (!visible) {
        panel.scrollTo({ top: Math.max(0, top - 8), behavior });
      }
    } else {
      // Narrow layout: sources follow the answer, so the page itself has to scroll to them.
      element.scrollIntoView({ block: 'nearest', behavior });
    }
    element.focus({ preventScroll: true });
  }
}
