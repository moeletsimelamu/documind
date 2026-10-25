import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  message: string;
}

const TOAST_MS = 4000;

/** Brief confirmations after an action. Errors that need action are shown inline instead. */
@Injectable({ providedIn: 'root' })
export class ToastService {
  private nextId = 1;
  readonly toasts = signal<Toast[]>([]);

  show(message: string): void {
    const toast = { id: this.nextId++, message };
    this.toasts.update((list) => [...list, toast]);
    setTimeout(() => this.dismiss(toast.id), TOAST_MS);
  }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
  }
}
