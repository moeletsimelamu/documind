import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, forkJoin, map, of, tap } from 'rxjs';

import { ApiError, toApiError } from './api-error';
import { DocumentSummary } from './api.models';
import { ApiService } from './api.service';

export const POLL_INTERVAL_MS = 2000;

/** A re-fetched document, or null if it no longer exists. */
interface PollResult {
  id: string;
  document: DocumentSummary | null;
}

/**
 * The document library as the server reports it. While any document is processing, those
 * documents are re-fetched every two seconds until they are ready or failed.
 */
@Injectable({ providedIn: 'root' })
export class LibraryStore {
  private readonly api = inject(ApiService);
  private pollTimer: ReturnType<typeof setTimeout> | null = null;

  readonly documents = signal<DocumentSummary[]>([]);
  readonly loaded = signal(false);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);

  readonly byId = computed(() => new Map(this.documents().map((d) => [d.id, d])));
  readonly readyDocuments = computed(() => this.documents().filter((d) => d.status === 'ready'));
  readonly processingCount = computed(
    () => this.documents().filter((d) => d.status === 'processing').length,
  );

  load(): void {
    this.loading.set(true);
    this.api.listDocuments().subscribe({
      next: (documents) => {
        this.documents.set(documents);
        this.loaded.set(true);
        this.loading.set(false);
        this.error.set(null);
        this.schedulePoll();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(toApiError(error));
      },
    });
  }

  /** Add or replace a document (newest first), e.g. after an upload is accepted. */
  upsert(document: DocumentSummary): void {
    this.documents.update((list) => {
      const index = list.findIndex((d) => d.id === document.id);
      if (index === -1) {
        return [document, ...list];
      }
      const copy = [...list];
      copy[index] = document;
      return copy;
    });
    this.schedulePoll();
  }

  remove(id: string): void {
    this.documents.update((list) => list.filter((d) => d.id !== id));
  }

  delete(id: string): Observable<void> {
    return this.api.deleteDocument(id).pipe(tap(() => this.remove(id)));
  }

  private schedulePoll(): void {
    if (this.pollTimer !== null || this.processingCount() === 0) {
      return;
    }
    this.pollTimer = setTimeout(() => this.poll(), POLL_INTERVAL_MS);
  }

  private poll(): void {
    const processing = this.documents().filter((d) => d.status === 'processing');
    if (!processing.length) {
      this.pollTimer = null;
      return;
    }
    const requests = processing.map((d) =>
      this.api.getDocument(d.id).pipe(
        map((document): PollResult => ({ id: d.id, document })),
        // A 404 means it was deleted elsewhere; other errors are retried on the next poll.
        catchError((error: unknown) =>
          of<PollResult>({ id: d.id, document: toApiError(error).status === 404 ? null : d }),
        ),
      ),
    );
    forkJoin(requests).subscribe((results) => {
      this.pollTimer = null;
      for (const result of results) {
        if (result.document === null) {
          this.remove(result.id);
        } else {
          this.upsert(result.document);
        }
      }
      this.schedulePoll();
    });
  }
}
