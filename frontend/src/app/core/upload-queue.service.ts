import { HttpEventType } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';

import { toApiError } from './api-error';
import { ApiService } from './api.service';
import { ConfigService } from './config.service';
import { formatBytes } from './format';
import { LibraryStore } from './library.store';

export type UploadState = 'queued' | 'uploading' | 'processing' | 'ready' | 'failed' | 'rejected';

export interface UploadItem {
  key: number;
  name: string;
  size: number;
  state: UploadState;
  /** 0–100 while uploading. */
  progress: number;
  documentId: string | null;
  message: string | null;
  /** For duplicates: the document already in the library. */
  existingId: string | null;
}

const MAX_PARALLEL_UPLOADS = 2;
const FINISHED: ReadonlySet<UploadState> = new Set(['ready', 'failed', 'rejected']);

/**
 * Uploads files one request each, two at a time, with byte progress. Once the server accepts a
 * file, its state follows the document in the library store (processing → ready / failed).
 */
@Injectable({ providedIn: 'root' })
export class UploadQueueService {
  private readonly api = inject(ApiService);
  private readonly config = inject(ConfigService);
  private readonly library = inject(LibraryStore);
  private readonly files = new Map<number, File>();
  private nextKey = 1;

  private readonly rawItems = signal<UploadItem[]>([]);

  /** Items with server-side processing state merged in from the library. */
  readonly items = computed<UploadItem[]>(() => {
    const documents = this.library.byId();
    return this.rawItems().map((item) => {
      if (item.documentId === null || item.state === 'rejected') {
        return item;
      }
      const document = documents.get(item.documentId);
      if (!document) {
        return item;
      }
      return {
        ...item,
        state: document.status,
        message: document.status === 'failed' ? document.failure_message : null,
      };
    });
  });

  readonly active = computed(() => this.items().some((i) => !FINISHED.has(i.state)));
  readonly hasFinished = computed(() => this.items().some((i) => FINISHED.has(i.state)));

  add(files: Iterable<File>): void {
    const { allowed_file_types, max_upload_bytes } = this.config.config();
    const added: UploadItem[] = [];
    for (const file of files) {
      const key = this.nextKey++;
      const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
      let message: string | null = null;
      if (!file.name.includes('.') || !(allowed_file_types as string[]).includes(extension)) {
        message = 'Only PDF and TXT files can be uploaded.';
      } else if (file.size === 0) {
        message = 'The file is empty.';
      } else if (file.size > max_upload_bytes) {
        message = `The file is larger than the ${formatBytes(max_upload_bytes)} limit.`;
      }
      if (message === null) {
        this.files.set(key, file);
      }
      added.push({
        key,
        name: file.name,
        size: file.size,
        state: message === null ? 'queued' : 'rejected',
        progress: 0,
        documentId: null,
        message,
        existingId: null,
      });
    }
    this.rawItems.update((items) => [...items, ...added]);
    this.pump();
  }

  dismiss(key: number): void {
    this.files.delete(key);
    this.rawItems.update((items) => items.filter((i) => i.key !== key));
  }

  clearFinished(): void {
    const finished = new Set(
      this.items()
        .filter((i) => FINISHED.has(i.state))
        .map((i) => i.key),
    );
    this.rawItems.update((items) => items.filter((i) => !finished.has(i.key)));
  }

  private update(key: number, changes: Partial<UploadItem>): void {
    this.rawItems.update((items) => items.map((i) => (i.key === key ? { ...i, ...changes } : i)));
  }

  private pump(): void {
    const items = this.rawItems();
    let running = items.filter((i) => i.state === 'uploading').length;
    // Items are kept in the order the files were chosen, so uploads start in that order too.
    for (const item of items) {
      if (running >= MAX_PARALLEL_UPLOADS) {
        break;
      }
      if (item.state === 'queued') {
        running++;
        this.start(item.key);
      }
    }
  }

  private start(key: number): void {
    const file = this.files.get(key);
    if (!file) {
      return;
    }
    this.update(key, { state: 'uploading', progress: 0 });
    this.api.uploadDocument(file).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.update(key, { progress: Math.round((100 * event.loaded) / event.total) });
        } else if (event.type === HttpEventType.Response && event.body) {
          this.files.delete(key);
          this.update(key, { state: 'processing', progress: 100, documentId: event.body.id });
          this.library.upsert(event.body);
          this.pump();
        }
      },
      error: (error: unknown) => {
        const apiError = toApiError(error);
        const details = apiError.details as { document_id?: string } | undefined;
        this.files.delete(key);
        this.update(key, {
          state: 'rejected',
          message: apiError.message,
          existingId:
            apiError.code === 'duplicate_document' ? (details?.document_id ?? null) : null,
        });
        this.pump();
      },
    });
  }
}
