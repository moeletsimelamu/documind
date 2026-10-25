import { Injectable, computed, inject, signal } from '@angular/core';

import { ApiError, toApiError } from './api-error';
import { AskResponse } from './api.models';
import { ApiService } from './api.service';

export interface AskEntry {
  id: number;
  question: string;
  scopeId: string | null;
  scopeName: string | null;
  state: 'loading' | 'done' | 'error';
  response: AskResponse | null;
  error: ApiError | null;
}

/**
 * The questions asked in this browser tab and their responses. Kept in memory only: nothing is
 * stored on the server or in the browser, and the thread is gone when the tab closes.
 */
@Injectable({ providedIn: 'root' })
export class AskSessionService {
  private readonly api = inject(ApiService);
  private nextId = 1;

  /** Newest first. */
  readonly entries = signal<AskEntry[]>([]);
  readonly busy = computed(() => this.entries().some((e) => e.state === 'loading'));

  ask(question: string, scopeId: string | null, scopeName: string | null): void {
    if (this.busy()) {
      return; // one question at a time; also prevents double submission
    }
    const entry: AskEntry = {
      id: this.nextId++,
      question,
      scopeId,
      scopeName,
      state: 'loading',
      response: null,
      error: null,
    };
    this.entries.update((entries) => [entry, ...entries]);
    this.send(entry);
  }

  retry(id: number): void {
    const entry = this.entries().find((e) => e.id === id);
    if (!entry || this.busy()) {
      return;
    }
    this.update(id, { state: 'loading', error: null });
    this.send(entry);
  }

  clear(): void {
    if (!this.busy()) {
      this.entries.set([]);
    }
  }

  private send(entry: AskEntry): void {
    this.api.ask(entry.question, entry.scopeId ? [entry.scopeId] : null).subscribe({
      next: (response) => this.update(entry.id, { state: 'done', response }),
      error: (error: unknown) =>
        this.update(entry.id, { state: 'error', error: toApiError(error) }),
    });
  }

  private update(id: number, changes: Partial<AskEntry>): void {
    this.entries.update((entries) => entries.map((e) => (e.id === id ? { ...e, ...changes } : e)));
  }
}
