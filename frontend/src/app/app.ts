import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { ConfigService } from './core/config.service';
import { ConnectionService } from './core/connection.service';
import { LibraryStore } from './core/library.store';
import { ToastService } from './core/toast.service';
import { Icon } from './shared/icon';

@Component({
  selector: 'dm-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  private readonly router = inject(Router);
  private readonly config = inject(ConfigService);
  private readonly library = inject(LibraryStore);
  protected readonly connection = inject(ConnectionService);
  protected readonly toasts = inject(ToastService);

  constructor() {
    this.config.load();
    this.library.load();

    // When the server comes back after an outage, refresh what may have changed meanwhile.
    let wasOnline = true;
    effect(() => {
      const online = this.connection.online();
      if (online && !wasOnline) {
        untracked(() => {
          this.config.load();
          this.library.load();
        });
      }
      wasOnline = online;
    });

    // After in-app navigation, move focus to the new page so screen readers announce it.
    let first = true;
    const subscription = this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(() => {
        if (first) {
          first = false;
          return;
        }
        setTimeout(() => document.getElementById('main')?.focus({ preventScroll: true }));
      });
    inject(DestroyRef).onDestroy(() => subscription.unsubscribe());
  }

  protected search(event: Event, input: HTMLInputElement): void {
    event.preventDefault();
    const q = input.value.trim();
    if (q) {
      void this.router.navigate(['/search'], { queryParams: { q } });
      input.value = '';
    }
  }

  protected retryConnection(): void {
    this.connection.check();
  }
}
