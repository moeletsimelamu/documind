import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  input,
  output,
  viewChild,
} from '@angular/core';

/**
 * A modal confirmation built on the native <dialog> element: the rest of the page is inert while
 * it is open, Esc cancels, and focus returns to whatever opened it.
 */
@Component({
  selector: 'dm-confirm-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    dialog {
      width: min(440px, calc(100vw - 32px));
      padding: var(--space-5);
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-float);
      color: var(--ink);
    }
    dialog::backdrop {
      background: rgb(22 32 54 / 45%);
    }
    h2 {
      margin-bottom: var(--space-3);
    }
    .body {
      display: grid;
      gap: var(--space-3);
      color: var(--ink-muted);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: var(--space-2);
      margin-top: var(--space-5);
    }
  `,
  template: `
    <dialog #dialog [attr.aria-labelledby]="headingId" (cancel)="onCancel($event)">
      <h2 [id]="headingId">{{ heading() }}</h2>
      <div class="body"><ng-content /></div>
      @if (error()) {
        <p class="banner banner-error" role="alert">{{ error() }}</p>
      }
      <div class="actions">
        <button type="button" class="btn" (click)="cancel()" [disabled]="busy()">Cancel</button>
        <button type="button" class="btn btn-danger" (click)="confirmed.emit()" [disabled]="busy()">
          @if (busy()) {
            <span class="spinner" aria-hidden="true"></span>
          }
          {{ confirmLabel() }}
        </button>
      </div>
    </dialog>
  `,
})
export class ConfirmDialog {
  private static nextId = 1;
  protected readonly headingId = `dialog-heading-${ConfirmDialog.nextId++}`;
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  private returnFocusTo: HTMLElement | null = null;

  readonly heading = input.required<string>();
  readonly confirmLabel = input('Delete');
  readonly busy = input(false);
  readonly error = input<string | null>(null);
  readonly confirmed = output<void>();
  readonly cancelled = output<void>();

  open(): void {
    this.returnFocusTo = document.activeElement as HTMLElement | null;
    this.dialog().nativeElement.showModal();
  }

  close(): void {
    this.dialog().nativeElement.close();
    const trigger = this.returnFocusTo;
    this.returnFocusTo = null;
    // Decide after the next render: a delete usually removes the trigger along with its row, and
    // then focus goes to the page content rather than being left on <body>.
    setTimeout(() => {
      const target = trigger?.isConnected ? trigger : document.getElementById('main');
      target?.focus();
    });
  }

  cancel(): void {
    this.close();
    this.cancelled.emit();
  }

  protected onCancel(event: Event): void {
    event.preventDefault(); // Esc: close through the same path so focus is restored
    if (!this.busy()) {
      this.cancel();
    }
  }
}
