import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AskResponse, SearchHit } from '../../core/api.models';
import { AskEntry, AskSessionService } from '../../core/ask-session.service';
import { ConfigService } from '../../core/config.service';
import { locationLabel, plural } from '../../core/format';
import { LibraryStore } from '../../core/library.store';
import { bestSentence } from '../../shared/excerpt';
import { Icon } from '../../shared/icon';
import { PassageCard } from '../../shared/passage-card';
import { AnswerPart, citedWithoutMarker, splitCitations } from './citations';

/** Two columns (thread and sources) from this width; below it, sources follow each answer. */
const WIDE_QUERY = '(min-width: 1024px)';

@Component({
  selector: 'dm-ask-page',
  imports: [PassageCard, Icon, RouterLink, NgTemplateOutlet],
  templateUrl: './ask-page.html',
  styleUrl: './ask-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AskPage {
  protected readonly session = inject(AskSessionService);
  protected readonly config = inject(ConfigService);
  protected readonly library = inject(LibraryStore);
  private readonly injector = inject(Injector);

  private readonly questionField =
    viewChild.required<ElementRef<HTMLTextAreaElement>>('questionField');
  protected readonly draft = signal('');
  protected readonly scope = signal('');
  /** The source last opened from a citation, as "<entry id>:<marker>". */
  private readonly selectedSource = signal<string | null>(null);
  /** The entry whose sources the side panel shows; null means the latest. */
  private readonly chosenEntryId = signal<number | null>(null);
  protected readonly plural = plural;
  protected readonly locationLabel = locationLabel;

  /** Wide screens show the thread and a sources panel side by side. */
  protected readonly wide = signal(false);

  protected readonly maxChars = computed(() => this.config.config().max_question_chars);
  protected readonly tooLong = computed(() => this.draft().length > this.maxChars());
  protected readonly canAsk = computed(
    () => this.draft().trim().length > 0 && !this.tooLong() && !this.session.busy(),
  );

  protected readonly latest = computed(() => this.session.entries().at(-1) ?? null);
  protected readonly activeEntry = computed(() => {
    const id = this.chosenEntryId();
    return this.session.entries().find((e) => e.id === id) ?? this.latest();
  });

  /** What is happening while a question is being answered; a model can take a while to write. */
  protected readonly workingMessage = computed(() => {
    const config = this.config.config();
    return config.llm_enabled
      ? `Finding passages and asking ${config.llm_model ?? 'the AI model'} for an answer…`
      : 'Looking for relevant passages…';
  });

  /** For screen readers: announces when a response arrives. */
  protected readonly announcement = computed(() => {
    const latest = this.latest();
    if (!latest || latest.state === 'loading') {
      return latest ? this.workingMessage() : '';
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

  constructor() {
    const media = typeof window.matchMedia === 'function' ? window.matchMedia(WIDE_QUERY) : null;
    if (media) {
      this.wide.set(media.matches);
      const listener = (event: MediaQueryListEvent) => this.wide.set(event.matches);
      media.addEventListener('change', listener);
      inject(DestroyRef).onDestroy(() => media.removeEventListener('change', listener));
    }

    // When the latest question is answered, bring the answer into view above the question box.
    let waitingFor: number | null = null;
    effect(() => {
      const latest = this.latest();
      if (latest?.state === 'loading') {
        waitingFor = latest.id;
      } else if (latest && latest.id === waitingFor) {
        waitingFor = null;
        afterNextRender(() => this.revealLatest(), { injector: this.injector });
      }
    });
  }

  protected submit(event?: Event): void {
    event?.preventDefault();
    if (!this.canAsk()) {
      return;
    }
    const scopeId = this.scope() || null;
    const scopeName = scopeId ? (this.library.byId().get(scopeId)?.name ?? null) : null;
    this.session.ask(this.draft().trim(), scopeId, scopeName);
    this.chosenEntryId.set(null); // the panel follows the new question
    // Clear the element itself: if Enter arrives before the next render, a [value] binding would
    // see no change ('' → '') and leave the old text in the field.
    this.questionField().nativeElement.value = '';
    this.draft.set('');
    afterNextRender(() => this.revealLatest(), { injector: this.injector });
  }

  protected onKeydown(event: KeyboardEvent): void {
    // Enter asks; Shift+Enter starts a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      this.submit(event);
    }
  }

  protected clear(): void {
    this.session.clear();
    this.chosenEntryId.set(null);
    this.selectedSource.set(null);
  }

  protected answerParts(response: AskResponse): AnswerPart[] {
    return splitCitations(response.answer ?? '', response.cited);
  }

  protected unmarkedCitations(response: AskResponse): string[] {
    return citedWithoutMarker(response.answer ?? '', response.cited);
  }

  /** The sentence of a passage that best matches the question, for the "closest match" quote. */
  protected closestSentence(hit: SearchHit): string {
    const span = bestSentence(hit.excerpt, hit.highlights);
    return (span ? hit.excerpt.slice(span[0], span[1]) : hit.excerpt).trim();
  }

  protected markers(response: AskResponse): string[] {
    return response.passages.map((_, i) => `S${i + 1}`);
  }

  protected isActive(entry: AskEntry): boolean {
    return this.activeEntry()?.id === entry.id;
  }

  protected sourceElementId(entryId: number, marker: string): string {
    return `entry-${entryId}-source-${marker}`;
  }

  protected isSelected(entryId: number, marker: string): boolean {
    return this.selectedSource() === `${entryId}:${marker}`;
  }

  /** Shows the entry's sources (in the side panel when wide) without moving the thread. */
  protected showSources(entry: AskEntry): void {
    this.chosenEntryId.set(entry.id);
    this.selectedSource.set(null);
  }

  /** Selects a cited source, shows it and moves focus to it. */
  protected showSource(entryId: number, marker: string): void {
    this.chosenEntryId.set(entryId);
    this.selectedSource.set(`${entryId}:${marker}`);
    // The panel may first have to switch to this entry's sources.
    afterNextRender(() => this.bringIntoView(this.sourceElementId(entryId, marker)), {
      injector: this.injector,
    });
  }

  private bringIntoView(elementId: string): void {
    const element = document.getElementById(elementId);
    if (!element) {
      return;
    }
    const behavior: ScrollBehavior = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 'auto'
      : 'smooth';
    const panel = element.closest<HTMLElement>('.sources-panel.side');
    if (panel) {
      // The side panel scrolls on its own; scrolling the page would move the thread.
      const top = element.offsetTop - panel.offsetTop;
      const visible =
        top >= panel.scrollTop &&
        top + element.offsetHeight <= panel.scrollTop + panel.clientHeight;
      if (!visible) {
        panel.scrollTo({ top: Math.max(0, top - 8), behavior });
      }
    } else {
      element.scrollIntoView({ block: 'nearest', behavior });
    }
    element.focus({ preventScroll: true });
  }

  /**
   * Keeps the newest question in view above the question box, as a conversation does. An answer
   * too tall for the space left is shown from its start rather than its end.
   */
  private revealLatest(): void {
    const entries = document.querySelectorAll<HTMLElement>('.thread .entry');
    const entry = entries[entries.length - 1];
    if (!entry) {
      return;
    }
    const gap = 16;
    // The question box is pinned to the bottom on wide screens, so the visible room ends above it.
    const composer = document.querySelector<HTMLElement>('.wide .composer');
    const limit = (composer?.getBoundingClientRect().top ?? window.innerHeight) - gap;
    const box = entry.getBoundingClientRect();
    let by = 0;
    if (box.height > limit - gap || box.top < gap) {
      by = box.top - gap; // too tall to fit: show it from its start
    } else if (box.bottom > limit) {
      by = box.bottom - limit;
    }
    if (by !== 0) {
      const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      window.scrollBy({ top: by, behavior: reduced ? 'auto' : 'smooth' });
    }
  }
}
