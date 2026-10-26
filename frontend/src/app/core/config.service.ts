import { Injectable, inject, signal } from '@angular/core';

import { ClientConfig } from './api.models';
import { ApiService } from './api.service';

/** Limits used before the server is asked; the server enforces them again. */
const FALLBACK: ClientConfig = {
  llm_enabled: false,
  llm_model: null,
  allowed_file_types: ['pdf', 'txt'],
  max_upload_bytes: 20 * 1024 * 1024,
  max_pdf_pages: 500,
  max_query_chars: 300,
  max_question_chars: 1000,
};

/** The server's public configuration, loaded once (and again after an outage). */
@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly api = inject(ApiService);

  readonly config = signal<ClientConfig>(FALLBACK);
  readonly loaded = signal(false);

  load(): void {
    this.api.config().subscribe({
      next: (config) => {
        this.config.set(config);
        this.loaded.set(true);
      },
      error: () => this.loaded.set(false),
    });
  }
}
