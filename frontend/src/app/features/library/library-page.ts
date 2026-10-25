import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../core/api-error';
import { DocumentStatus, DocumentSummary } from '../../core/api.models';
import { formatBytes, formatDate, plural } from '../../core/format';
import { LibraryStore } from '../../core/library.store';
import { ToastService } from '../../core/toast.service';
import { ConfirmDialog } from '../../shared/confirm-dialog';
import { Icon } from '../../shared/icon';
import { StatusBadge } from '../../shared/status-badge';
import { UploadPanel } from './upload-panel';

type StatusFilter = DocumentStatus | 'all';

@Component({
  selector: 'dm-library-page',
  imports: [RouterLink, UploadPanel, StatusBadge, ConfirmDialog, Icon],
  templateUrl: './library-page.html',
  styleUrl: './library-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LibraryPage {
  protected readonly library = inject(LibraryStore);
  private readonly toasts = inject(ToastService);
  private readonly dialog = viewChild.required(ConfirmDialog);

  protected readonly nameFilter = signal('');
  protected readonly statusFilter = signal<StatusFilter>('all');
  protected readonly pendingDelete = signal<DocumentSummary | null>(null);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);

  protected readonly formatBytes = formatBytes;
  protected readonly formatDate = formatDate;
  protected readonly plural = plural;

  protected readonly filtered = computed(() => {
    const name = this.nameFilter().trim().toLowerCase();
    const status = this.statusFilter();
    return this.library
      .documents()
      .filter(
        (d) => (status === 'all' || d.status === status) && d.name.toLowerCase().includes(name),
      );
  });

  protected readonly filtering = computed(
    () => this.nameFilter().trim() !== '' || this.statusFilter() !== 'all',
  );

  protected setStatus(value: string): void {
    this.statusFilter.set(value as StatusFilter);
  }

  protected clearFilters(): void {
    this.nameFilter.set('');
    this.statusFilter.set('all');
  }

  protected askToDelete(document: DocumentSummary): void {
    this.pendingDelete.set(document);
    this.deleteError.set(null);
    this.dialog().open();
  }

  protected confirmDelete(): void {
    const document = this.pendingDelete();
    if (!document || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.library.delete(document.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.dialog().close();
        this.pendingDelete.set(null);
        this.toasts.show(`Deleted “${document.name}”`);
      },
      error: (error: unknown) => {
        this.deleting.set(false);
        const apiError = toApiError(error);
        if (apiError.status === 404) {
          // Already gone (deleted elsewhere): reflect that rather than showing an error.
          this.library.remove(document.id);
          this.dialog().close();
          this.toasts.show(`“${document.name}” was already deleted`);
        } else {
          this.deleteError.set(apiError.message);
        }
      },
    });
  }
}
