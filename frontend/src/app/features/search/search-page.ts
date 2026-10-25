import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { ApiError, toApiError } from '../../core/api-error';
import { SearchResponse } from '../../core/api.models';
import { ApiService } from '../../core/api.service';
import { ConfigService } from '../../core/config.service';
import { plural } from '../../core/format';
import { LibraryStore } from '../../core/library.store';
import { Icon } from '../../shared/icon';
import { PassageCard } from '../../shared/passage-card';

export const SEARCH_LIMIT = 20;

@Component({
  selector: 'dm-search-page',
  imports: [PassageCard, Icon],
  templateUrl: './search-page.html',
  styleUrl: './search-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  protected readonly library = inject(LibraryStore);
  protected readonly config = inject(ConfigService);
  private request: Subscription | null = null;

  /** Query parameters: the search text and an optional document to search within. */
  readonly q = input<string | undefined>();
  readonly doc = input<string | undefined>();

  protected readonly draft = signal('');
  protected readonly scope = signal('');
  protected readonly response = signal<SearchResponse | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly plural = plural;
  protected readonly limit = SEARCH_LIMIT;

  constructor() {
    effect(() => {
      const q = this.q()?.trim() ?? '';
      const doc = this.doc() ?? '';
      untracked(() => {
        this.draft.set(q);
        this.scope.set(doc);
        this.run(q, doc);
      });
    });
  }

  protected submit(event: Event): void {
    event.preventDefault();
    const q = this.draft().trim();
    if (!q) {
      return;
    }
    if (q === (this.q()?.trim() ?? '') && this.scope() === (this.doc() ?? '')) {
      // Same URL, so navigation would not re-run the search; run it again (e.g. after an error).
      this.run(q, this.scope());
      return;
    }
    void this.router.navigate(['/search'], {
      queryParams: { q, doc: this.scope() || null },
    });
  }

  protected documentName(id: string): string {
    return this.library.byId().get(id)?.name ?? 'the selected document';
  }

  private run(q: string, doc: string): void {
    this.request?.unsubscribe();
    if (!q) {
      this.response.set(null);
      this.error.set(null);
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.request = this.api.search(q, doc || null, SEARCH_LIMIT).subscribe({
      next: (response) => {
        this.response.set(response);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.response.set(null);
        this.error.set(toApiError(error));
        this.loading.set(false);
      },
    });
  }
}
