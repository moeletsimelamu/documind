import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
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
import { Chunk, DocumentSummary } from '../../core/api.models';
import { ApiService } from '../../core/api.service';
import { formatBytes, formatDate, locationLabel, plural } from '../../core/format';
import { LibraryStore, POLL_INTERVAL_MS } from '../../core/library.store';
import { ToastService } from '../../core/toast.service';
import { ConfirmDialog } from '../../shared/confirm-dialog';
import { Icon } from '../../shared/icon';
import { StatusBadge } from '../../shared/status-badge';

export const READER_PAGE_SIZE = 60;
/** How many passages to show before the one a citation points at. */
const CONTEXT_BEFORE = 5;

@Component({
  selector: 'dm-document-page',
  imports: [RouterLink, StatusBadge, ConfirmDialog, Icon],
  templateUrl: './document-page.html',
  styleUrl: './document-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DocumentPage {
  private readonly api = inject(ApiService);
  private readonly library = inject(LibraryStore);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly injector = inject(Injector);
  private readonly dialog = viewChild.required(ConfirmDialog);
  private pollTimer: ReturnType<typeof setTimeout> | null = null;

  /** Route parameter. */
  readonly id = input.required<string>();
  /** Query parameter: the passage to open, e.g. from a search result or citation. */
  readonly chunk = input<string | undefined>();

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

  protected readonly targetId = computed(() => {
    const value = Number(this.chunk());
    return Number.isInteger(value) && value > 0 ? value : null;
  });
  protected readonly hasEarlier = computed(() => this.firstOffset() > 0);
  protected readonly hasLater = computed(
    () => this.firstOffset() + this.chunks().length < this.total(),
  );

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
    start$
      .pipe(
        switchMap((start) =>
          this.api.getChunks(id, start, READER_PAGE_SIZE).pipe(map((page) => ({ start, page }))),
        ),
      )
      .subscribe({
        next: ({ start, page }) => {
          this.firstOffset.set(start);
          this.chunks.set(page.items);
          this.total.set(page.total);
          this.loadingText.set(false);
          if (target) {
            afterNextRender(() => this.focusPassage(target), { injector: this.injector });
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

  private focusPassage(chunkId: number): void {
    const element = document.getElementById(`chunk-${chunkId}`);
    if (element) {
      element.scrollIntoView({ block: 'center' });
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
