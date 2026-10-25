import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'dm-not-found-page',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <div class="empty">
        <h1>Page not found</h1>
        <p>There is nothing at this address. It may have been a link to a deleted document.</p>
        <a class="btn btn-primary" routerLink="/library">Go to the library</a>
      </div>
    </div>
  `,
})
export class NotFoundPage {}
