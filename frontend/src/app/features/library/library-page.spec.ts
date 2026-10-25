import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { makeDocument } from '../../../testing/fixtures';
import { DocumentSummary } from '../../core/api.models';
import { LibraryStore } from '../../core/library.store';
import { ToastService } from '../../core/toast.service';
import { LibraryPage } from './library-page';

describe('LibraryPage', () => {
  let fixture: ComponentFixture<LibraryPage>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [LibraryPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(LibraryPage);
    page = fixture.nativeElement as HTMLElement;
  });

  async function load(documents: DocumentSummary[]): Promise<void> {
    TestBed.inject(LibraryStore).load();
    http.expectOne('/api/documents').flush(documents);
    await fixture.whenStable();
  }

  const rows = () => Array.from(page.querySelectorAll('tbody tr'));
  const text = () => page.textContent?.replace(/\s+/g, ' ') ?? '';

  async function type(selector: string, value: string): Promise<void> {
    const input = page.querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    input.value = value;
    input.dispatchEvent(new Event(input instanceof HTMLSelectElement ? 'change' : 'input'));
    await fixture.whenStable();
  }

  it('shows a loading placeholder, then an empty state', async () => {
    TestBed.inject(LibraryStore).load();
    await fixture.whenStable();
    expect(page.querySelector('[aria-busy="true"]')).not.toBeNull();

    http.expectOne('/api/documents').flush([]);
    await fixture.whenStable();

    expect(text()).toContain('Your library is empty');
    expect(page.querySelector('table')).toBeNull();
  });

  it('lists documents with their state and problems', async () => {
    await load([
      makeDocument({ id: 'a', name: 'ok.pdf', empty_page_count: 2 }),
      makeDocument({
        id: 'b',
        name: 'scan.pdf',
        status: 'failed',
        failure_code: 'no_extractable_text',
        failure_message: 'This PDF appears to contain scanned images.',
        page_count: null,
      }),
    ]);

    expect(rows()).toHaveLength(2);
    expect(rows()[0].textContent).toContain('2 pages had no text');
    expect(rows()[0].textContent).toContain('Ready');
    expect(rows()[1].textContent).toContain('This PDF appears to contain scanned images.');
    expect(rows()[1].textContent).toContain('No text found');
    expect(text()).toContain('2 documents');
    expect(rows()[0].querySelector('a')?.getAttribute('href')).toBe('/documents/a');
  });

  it('filters by name and status, and explains when nothing matches', async () => {
    await load([
      makeDocument({ id: 'a', name: 'Budget 2026.pdf' }),
      makeDocument({ id: 'b', name: 'minutes.txt', status: 'failed' }),
    ]);

    await type('#name-filter', 'BUDGET');
    expect(rows().map((r) => r.querySelector('a')?.textContent)).toEqual(['Budget 2026.pdf']);
    expect(text()).toContain('Showing 1 of 2');

    await type('#status-filter', 'failed');
    expect(rows()).toHaveLength(0);
    expect(text()).toContain('No documents match');

    page.querySelector<HTMLButtonElement>('.empty button')!.click();
    await fixture.whenStable();
    expect(rows()).toHaveLength(2);
  });

  it('deletes a document after confirmation', async () => {
    const toasts = TestBed.inject(ToastService);
    await load([
      makeDocument({ id: 'a', name: 'old.pdf' }),
      makeDocument({ id: 'b', name: 'keep.pdf' }),
    ]);

    page.querySelector<HTMLButtonElement>('[aria-label="Delete old.pdf"]')!.click();
    await fixture.whenStable();
    const dialog = page.querySelector('dialog')!;
    expect(dialog.hasAttribute('open')).toBe(true);
    expect(dialog.textContent).toContain('old.pdf');
    http.expectNone('/api/documents/a'); // nothing deleted before confirming

    dialog.querySelector<HTMLButtonElement>('.btn-danger')!.click();
    const request = http.expectOne('/api/documents/a');
    expect(request.request.method).toBe('DELETE');
    request.flush(null, { status: 204, statusText: 'No Content' });
    await fixture.whenStable();

    expect(dialog.hasAttribute('open')).toBe(false);
    expect(rows().map((r) => r.querySelector('a')?.textContent)).toEqual(['keep.pdf']);
    expect(toasts.toasts().map((t) => t.message)).toEqual(['Deleted “old.pdf”']);
  });

  it('keeps the dialog open with the reason when deletion fails', async () => {
    await load([makeDocument({ id: 'a', name: 'old.pdf' })]);
    page.querySelector<HTMLButtonElement>('[aria-label="Delete old.pdf"]')!.click();
    await fixture.whenStable();

    page.querySelector<HTMLButtonElement>('dialog .btn-danger')!.click();
    http.expectOne('/api/documents/a').flush(
      {
        error: {
          code: 'internal_error',
          message: 'Something went wrong on the server.',
          request_id: 'r',
        },
      },
      { status: 500, statusText: 'Server Error' },
    );
    await fixture.whenStable();

    expect(page.querySelector('dialog')!.hasAttribute('open')).toBe(true);
    expect(page.querySelector('dialog [role="alert"]')?.textContent).toContain(
      'Something went wrong',
    );
    expect(rows()).toHaveLength(1);
  });

  it('cancelling the dialog deletes nothing', async () => {
    await load([makeDocument({ id: 'a', name: 'old.pdf' })]);
    page.querySelector<HTMLButtonElement>('[aria-label="Delete old.pdf"]')!.click();
    await fixture.whenStable();

    page.querySelector<HTMLButtonElement>('dialog .btn:not(.btn-danger)')!.click();
    await fixture.whenStable();

    expect(page.querySelector('dialog')!.hasAttribute('open')).toBe(false);
    http.expectNone('/api/documents/a');
    expect(rows()).toHaveLength(1);
  });

  it('offers a retry when the library cannot be loaded', async () => {
    TestBed.inject(LibraryStore).load();
    http.expectOne('/api/documents').flush(null, { status: 0, statusText: 'Unknown Error' });
    await fixture.whenStable();

    expect(page.querySelector('[role="alert"]')?.textContent).toContain(
      "Can't reach the DocuMind server",
    );
    page.querySelector<HTMLButtonElement>('[role="alert"] button')!.click();
    http.expectOne('/api/documents').flush([makeDocument()]);
    await fixture.whenStable();

    expect(rows()).toHaveLength(1);
  });
});
