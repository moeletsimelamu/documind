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
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Observable, map, of, switchMap } from 'rxjs';

import { ApiError, toApiError } from '../../core/api-error';
import { Chunk, ChunkPage, DocumentMatches, DocumentSummary, Span } from '../../core/api.models';
import { ApiService } from '../../core/api.service';
import { formatBytes, formatDate, locationLabel, plural } from '../../core/format';
import { LibraryStore, POLL_INTERVAL_MS } from '../../core/library.store';
import { PageBox, PdfPageRenderer, RenderedPage } from '../../core/pdf-page-renderer.service';
import { ToastService } from '../../core/toast.service';
import { ConfirmDialog } from '../../shared/confirm-dialog';
import { Icon } from '../../shared/icon';
import { MarkedText } from '../../shared/marked-text';
import { StatusBadge } from '../../shared/status-badge';

export const READER_PAGE_SIZE = 60;
/** How many passages to show before the one a citation, match or page jump points at. */
const CONTEXT_BEFORE = 5;

@Component({
  selector: 'dm-document-page',
  imports: [RouterLink, StatusBadge, ConfirmDialog, Icon, MarkedText],
  templateUrl: './document-page.html',
  styleUrl: './document-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DocumentPage {
  private readonly api = inject(ApiService);
  private readonly library = inject(LibraryStore);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly renderer = inject(PdfPageRenderer);
  private readonly injector = inject(Injector);
  private readonly dialog = viewChild.required(ConfirmDialog);
  private readonly pageCanvas = viewChild<ElementRef<HTMLCanvasElement>>('pageCanvas');
  private readonly pageFrame = viewChild<ElementRef<HTMLElement>>('pageFrame');
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private renderRun = 0;
  /** The original page was just opened: scroll it into view once it has been drawn. */
  private revealPending = false;

  /** Route parameter. */
  readonly id = input.required<string>();
  /** Query parameter: the passage to open, e.g. from a search result or citation. */
  readonly chunk = input<string | undefined>();
  /** Query parameter: words to find in the document, e.g. the search that led here. */
  readonly q = input<string | undefined>();

  protected readonly document = signal<DocumentSummary | null>(null);
  protected readonly loadError = signal<ApiError | null>(null);
  protected readonly chunks = signal<Chunk[]>([]);
  protected readonly total = signal(0);
  protected readonly firstOffset = signal(0);
  protected readonly loadingText = signal(false);
  protected readonly textError = signal<ApiError | null>(null);
  protected readonly loadingMore = signal<'earlier' | 'later' | null>(null);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);

  // Go to page
  protected readonly pageDraft = signal('');
  protected readonly pageError = signal<string | null>(null);

  // Find in document
  protected readonly findDraft = signal('');
  protected readonly finding = signal(false);
  protected readonly findError = signal<string | null>(null);
  protected readonly matches = signal<DocumentMatches | null>(null);
  protected readonly matchIndex = signal(-1);
  /** The passage the reader last moved to (a match or a page), shown as current. */
  protected readonly currentId = signal<number | null>(null);

  // Original page
  protected readonly originalOpen = signal(false);
  protected readonly viewedPage = signal(1);
  protected readonly rendering = signal(false);
  protected readonly renderError = signal<string | null>(null);
  protected readonly passageBoxes = signal<PageBox[]>([]);
  protected readonly frameHeight = signal<number | null>(null);

  protected readonly targetId = computed(() => {
    const value = Number(this.chunk());
    return Number.isInteger(value) && value > 0 ? value : null;
  });
  protected readonly hasEarlier = computed(() => this.firstOffset() > 0);
  protected readonly hasLater = computed(
    () => this.firstOffset() + this.chunks().length < this.total(),
  );
  protected readonly isPdf = computed(() => {
    const doc = this.document();
    return doc?.file_type === 'pdf' && (doc.page_count ?? 0) > 0;
  });
  protected readonly pageCount = computed(() => this.document()?.page_count ?? 0);
  protected readonly highlightsById = computed(() => {
    const byId = new Map<number, Span[]>();
    for (const match of this.matches()?.matches ?? []) {
      byId.set(match.chunk_id, match.highlights);
    }
    return byId;
  });
  protected readonly matchLabel = computed(() => {
    const result = this.matches();
    if (!result) {
      return '';
    }
    if (!result.total) {
      return 'No matches';
    }
    const shown = result.truncated ? `${result.matches.length}+` : String(result.total);
    const any = result.all_words ? '' : ' (any of the words)';
    return `${this.matchIndex() + 1} of ${shown}${any}`;
  });
  /** The passage to outline on the original page: the current one, else the one opened. */
  private readonly outlinedPassage = computed(() => {
    const page = this.viewedPage();
    const chunks = this.chunks();
    for (const id of [this.currentId(), this.targetId()]) {
      const found = chunks.find((c) => c.id === id);
      if (found && found.page === page) {
        return found.text;
      }
    }
    return null;
  });

  protected readonly formatBytes = formatBytes;
  protected readonly formatDate = formatDate;
  protected readonly locationLabel = locationLabel;
  protected readonly plural = plural;

  constructor() {
    effect(() => {
      const id = this.id();
      const target = this.targetId();
      untracked(() => this.load(id, target));
    });
    // Draw the original page whenever it is shown, changes, or a different passage is outlined.
    effect(() => {
      const open = this.originalOpen();
      const page = this.viewedPage();
      const passage = this.outlinedPassage();
      const doc = this.document();
      if (open && doc) {
        untracked(() =>
          afterNextRender(() => void this.drawPage(doc.id, page, passage), {
            injector: this.injector,
          }),
        );
      }
    });
    inject(DestroyRef).onDestroy(() => this.stopPolling());
  }

  protected showsPageDivider(index: number): boolean {
    const chunks = this.chunks();
    const page = chunks[index].page;
    return page !== null && (index === 0 || chunks[index - 1].page !== page);
  }

  protected load(id: string, target: number | null): void {
    this.stopPolling();
    this.loadError.set(null);
    this.api.getDocument(id).subscribe({
      next: (document) => {
        this.document.set(document);
        if (document.status === 'ready') {
          this.loadText(id, target);
        } else if (document.status === 'processing') {
          this.pollTimer = setTimeout(() => this.load(id, target), POLL_INTERVAL_MS);
        }
      },
      error: (error: unknown) => {
        this.document.set(null);
        this.loadError.set(toApiError(error));
      },
    });
  }

  private loadText(id: string, target: number | null): void {
    this.loadingText.set(true);
    this.textError.set(null);
    const start$: Observable<number> = target
      ? this.api
          .getChunk(target)
          .pipe(
            map((chunk) =>
              chunk.document_id === id ? Math.max(0, chunk.ordinal - CONTEXT_BEFORE) : 0,
            ),
          )
      : of(0);
    start$.pipe(switchMap((start) => this.api.getChunks(id, start, READER_PAGE_SIZE))).subscribe({
      next: (page) => {
        this.showWindow(page);
        this.loadingText.set(false);
        const opened = page.items.find((c) => c.id === target);
        if (opened?.page) {
          this.viewedPage.set(opened.page);
        }
        if (target) {
          afterNextRender(() => this.focusPassage(target, 'center'), {
            injector: this.injector,
          });
        }
        const query = this.q()?.trim();
        if (query) {
          this.findDraft.set(query);
          this.runFind(query, target);
        }
      },
      error: (error: unknown) => {
        this.loadingText.set(false);
        const apiError = toApiError(error);
        // A citation to a passage that no longer exists: show the document from the start.
        if (target && apiError.status === 404) {
          this.loadText(id, null);
          this.textError.set({ ...apiError, message: 'That passage no longer exists.' });
        } else {
          this.textError.set(apiError);
        }
      },
    });
  }

  private showWindow(page: ChunkPage): void {
    this.firstOffset.set(page.offset);
    this.chunks.set(page.items);
    this.total.set(page.total);
  }

  protected showEarlier(): void {
    const first = this.firstOffset();
    const start = Math.max(0, first - READER_PAGE_SIZE);
    this.loadingMore.set('earlier');
    this.api.getChunks(this.id(), start, first - start).subscribe({
      next: (page) => {
        this.chunks.update((chunks) => [...page.items, ...chunks]);
        this.firstOffset.set(start);
        this.loadingMore.set(null);
      },
      error: (error: unknown) => {
        this.loadingMore.set(null);
        this.textError.set(toApiError(error));
      },
    });
  }

  protected showLater(): void {
    this.loadingMore.set('later');
    const offset = this.firstOffset() + this.chunks().length;
    this.api.getChunks(this.id(), offset, READER_PAGE_SIZE).subscribe({
      next: (page) => {
        this.chunks.update((chunks) => [...chunks, ...page.items]);
        this.total.set(page.total);
        this.loadingMore.set(null);
      },
      error: (error: unknown) => {
        this.loadingMore.set(null);
        this.textError.set(toApiError(error));
      },
    });
  }

  // --- Go to page -----------------------------------------------------------------------------

  protected goToPage(event: Event): void {
    event.preventDefault();
    const count = this.pageCount();
    const page = Number(this.pageDraft());
    if (!Number.isInteger(page) || page < 1 || page > count) {
      this.pageError.set(`Enter a page from 1 to ${count}.`);
      return;
    }
    this.pageError.set(null);
    this.api.getChunksFromPage(this.id(), page, READER_PAGE_SIZE).subscribe({
      next: (result) => {
        this.showWindow(result);
        const first = result.items[0];
        this.viewedPage.set(page);
        if (first) {
          this.currentId.set(first.id);
          if (first.page !== page) {
            this.pageError.set(`Page ${page} has no text; showing page ${first.page}.`);
          }
          afterNextRender(() => this.focusPassage(first.id, 'start'), { injector: this.injector });
        }
      },
      error: (error: unknown) => this.pageError.set(toApiError(error).message),
    });
  }

  // --- Find in document ------------------------------------------------------------------------

  protected find(event: Event): void {
    event.preventDefault();
    const query = this.findDraft().trim();
    if (!query) {
      this.clearFind();
      return;
    }
    this.runFind(query, this.currentId() ?? this.targetId());
  }

  /** Runs a search in this document and moves to the first match at or after ``from``. */
  private runFind(query: string, from: number | null): void {
    this.finding.set(true);
    this.findError.set(null);
    this.api.findInDocument(this.id(), query).subscribe({
      next: (result) => {
        this.finding.set(false);
        this.matches.set(result);
        if (!result.matches.length) {
          this.matchIndex.set(-1);
          return;
        }
        const position = this.chunks().find((c) => c.id === from)?.ordinal ?? -1;
        const start = result.matches.findIndex((m) => m.ordinal >= position);
        this.goToMatch(Math.max(0, start));
      },
      error: (error: unknown) => {
        this.finding.set(false);
        this.matches.set(null);
        this.findError.set(toApiError(error).message);
      },
    });
  }

  protected step(direction: 1 | -1): void {
    const count = this.matches()?.matches.length ?? 0;
    if (count) {
      this.goToMatch((this.matchIndex() + direction + count) % count);
    }
  }

  protected clearFind(): void {
    this.findDraft.set('');
    this.matches.set(null);
    this.matchIndex.set(-1);
    this.findError.set(null);
  }

  private goToMatch(index: number): void {
    const match = this.matches()?.matches[index];
    if (!match) {
      return;
    }
    this.matchIndex.set(index);
    this.currentId.set(match.chunk_id);
    if (match.page) {
      this.viewedPage.set(match.page);
    }
    this.reveal(match.ordinal, match.chunk_id);
  }

  /** Scrolls to a passage, first loading the part of the document around it if needed. */
  private reveal(ordinal: number, chunkId: number): void {
    const first = this.firstOffset();
    if (ordinal >= first && ordinal < first + this.chunks().length) {
      afterNextRender(() => this.focusPassage(chunkId, 'center'), { injector: this.injector });
      return;
    }
    const start = Math.max(0, ordinal - CONTEXT_BEFORE);
    this.api.getChunks(this.id(), start, READER_PAGE_SIZE).subscribe({
      next: (page) => {
        this.showWindow(page);
        afterNextRender(() => this.focusPassage(chunkId, 'center'), { injector: this.injector });
      },
      error: (error: unknown) => this.textError.set(toApiError(error)),
    });
  }

  // --- Original page ---------------------------------------------------------------------------

  protected toggleOriginal(): void {
    this.originalOpen.update((open) => !open);
    this.revealPending = this.originalOpen();
  }

  protected viewOriginal(page: number): void {
    this.viewedPage.set(page);
    this.originalOpen.set(true);
    this.revealPending = true;
  }

  protected turnPage(direction: 1 | -1): void {
    const next = this.viewedPage() + direction;
    if (next >= 1 && next <= this.pageCount()) {
      this.viewedPage.set(next);
    }
  }

  private async drawPage(id: string, page: number, passage: string | null): Promise<void> {
    const canvas = this.pageCanvas()?.nativeElement;
    const frame = this.pageFrame()?.nativeElement;
    if (!canvas || !frame) {
      return;
    }
    const run = ++this.renderRun;
    this.rendering.set(true);
    this.renderError.set(null);
    let result: RenderedPage;
    try {
      result = await this.renderer.render(
        this.api.fileUrl(id),
        page,
        canvas,
        frame.clientWidth,
        passage,
      );
    } catch {
      if (run === this.renderRun) {
        this.rendering.set(false);
        this.passageBoxes.set([]);
        this.renderError.set(
          'This page could not be shown. Download the original to view it in a PDF reader.',
        );
      }
      return;
    }
    if (run !== this.renderRun) {
      return; // a later page was asked for meanwhile
    }
    this.rendering.set(false);
    this.frameHeight.set(result.height);
    this.passageBoxes.set(result.passageBoxes);
    const panel = frame.closest<HTMLElement>('.original');
    if (!panel) {
      return;
    }
    // Wide screens: the panel scrolls on its own; bring the outlined passage into view in it.
    const firstBox = result.passageBoxes[0];
    if (firstBox) {
      panel.scrollTop = Math.max(0, frame.offsetTop + firstBox.top - 80);
    }
    // Narrow screens: the page sits above the text. When it was just opened, show it — after
    // drawing, since the canvas changes height — but never when only the match or page changed.
    if (this.revealPending) {
      this.revealPending = false;
      afterNextRender(
        () => {
          if (getComputedStyle(panel).position !== 'sticky') {
            panel.scrollIntoView({ block: 'start' });
          }
        },
        { injector: this.injector },
      );
    }
  }

  // --- Deletion ---------------------------------------------------------------------------------

  protected askToDelete(): void {
    this.deleteError.set(null);
    this.dialog().open();
  }

  protected confirmDelete(): void {
    const document = this.document();
    if (!document || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.library.delete(document.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.dialog().close();
        this.toasts.show(`Deleted “${document.name}”`);
        void this.router.navigate(['/library']);
      },
      error: (error: unknown) => {
        this.deleting.set(false);
        this.deleteError.set(toApiError(error).message);
      },
    });
  }

  protected fileUrl(id: string): string {
    return this.api.fileUrl(id);
  }

  private focusPassage(chunkId: number, block: ScrollLogicalPosition): void {
    const element = document.getElementById(`chunk-${chunkId}`);
    if (element) {
      element.scrollIntoView({ block });
      element.focus({ preventScroll: true });
    }
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }
}
