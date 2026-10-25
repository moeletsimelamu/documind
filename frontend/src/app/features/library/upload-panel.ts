import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ConfigService } from '../../core/config.service';
import { formatBytes } from '../../core/format';
import { UploadQueueService } from '../../core/upload-queue.service';
import { Icon } from '../../shared/icon';
import { StatusBadge } from '../../shared/status-badge';

/** Drop zone + file button, and the queue of uploads with their real progress and outcome. */
@Component({
  selector: 'dm-upload-panel',
  imports: [Icon, StatusBadge, RouterLink],
  templateUrl: './upload-panel.html',
  styleUrl: './upload-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UploadPanel {
  protected readonly queue = inject(UploadQueueService);
  private readonly config = inject(ConfigService);
  protected readonly dragging = signal(false);
  protected readonly limit = computed(() => formatBytes(this.config.config().max_upload_bytes));
  protected readonly formatBytes = formatBytes;

  /** A text summary for screen readers, updated as uploads progress. */
  protected readonly announcement = computed(() => {
    const items = this.queue.items();
    const ready = items.filter((i) => i.state === 'ready').length;
    const working = items.filter((i) => ['queued', 'uploading', 'processing'].includes(i.state));
    const problems = items.filter((i) => i.state === 'failed' || i.state === 'rejected').length;
    if (!items.length) {
      return '';
    }
    return `${working.length} in progress, ${ready} ready, ${problems} with problems.`;
  });

  protected choose(input: HTMLInputElement): void {
    if (input.files?.length) {
      this.queue.add(Array.from(input.files));
    }
    input.value = ''; // allow choosing the same file again
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const files = event.dataTransfer?.files;
    if (files?.length) {
      this.queue.add(Array.from(files));
    }
  }
}
