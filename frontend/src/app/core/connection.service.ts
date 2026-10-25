import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { isUnreachable } from './api-error';
import { ApiService } from './api.service';

const RETRY_INTERVAL_MS = 5000;

/**
 * Tracks whether the API is reachable. A network failure on any request marks it offline; while
 * offline the health endpoint is polled until the server answers again.
 */
@Injectable({ providedIn: 'root' })
export class ConnectionService {
  private readonly api = inject(ApiService);
  private timer: ReturnType<typeof setInterval> | null = null;

  readonly online = signal(true);
  readonly checking = signal(false);

  constructor() {
    inject(DestroyRef).onDestroy(() => this.stopPolling());
  }

  markOffline(): void {
    if (!this.online()) {
      return;
    }
    this.online.set(false);
    this.timer = setInterval(() => this.check(), RETRY_INTERVAL_MS);
  }

  check(): void {
    if (this.checking()) {
      return;
    }
    this.checking.set(true);
    this.api.health().subscribe({
      next: () => {
        this.checking.set(false);
        this.online.set(true);
        this.stopPolling();
      },
      error: () => this.checking.set(false),
    });
  }

  private stopPolling(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

/** Marks the connection offline when a request cannot reach the server at all. */
export const connectionInterceptor: HttpInterceptorFn = (request, next) => {
  const connection = inject(ConnectionService);
  return next(request).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        isUnreachable(error) &&
        !request.url.endsWith('/api/health')
      ) {
        connection.markOffline();
      }
      return throwError(() => error);
    }),
  );
};
