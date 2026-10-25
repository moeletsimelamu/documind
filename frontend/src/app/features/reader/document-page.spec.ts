import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { makeDocument } from '../../../testing/fixtures';
import { Chunk } from '../../core/api.models';
import { DocumentPage, READER_PAGE_SIZE } from './document-page';

const chunk = (
  id: number,
  ordinal: number,
  page: number | null,
  text = `Passage ${id}`,
): Chunk => ({
  id,
  ordinal,
  page,
  line_start: page === null ? ordinal * 10 + 1 : null,
  line_end: page === null ? ordinal * 10 + 9 : null,
  text,
});

describe('DocumentPage', () => {
  let fixture: ComponentFixture<DocumentPage>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DocumentPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DocumentPage);
    page = fixture.nativeElement as HTMLElement;
  });

  async function open(id: string, chunkId?: number): Promise<void> {
    fixture.componentRef.setInput('id', id);
    fixture.componentRef.setInput('chunk', chunkId === undefined ? undefined : String(chunkId));
    await fixture.whenStable();
  }

  const text = () => page.textContent?.replace(/\s+/g, ' ') ?? '';

  it('shows the extracted text with page dividers', async () => {
    await open('doc-1');
    http
      .expectOne('/api/documents/doc-1')
      .flush(makeDocument({ name: 'report.pdf', page_count: 2 }));
    const chunks = http.expectOne((r) => r.url === '/api/documents/doc-1/chunks');
    expect(chunks.request.params.get('offset')).toBe('0');
    chunks.flush({
      document_id: 'doc-1',
      total: 3,
      offset: 0,
      limit: READER_PAGE_SIZE,
      items: [chunk(1, 0, 1), chunk(2, 1, 1), chunk(3, 2, 2)],
    });
    await fixture.whenStable();

    expect(page.querySelector('h1')?.textContent).toBe('report.pdf');
    expect(
      Array.from(page.querySelectorAll('.page-divider')).map((d) => d.textContent?.trim()),
    ).toEqual(['Page 1', 'Page 2']);
    expect(page.querySelectorAll('.passage')).toHaveLength(3);
    expect(page.querySelector<HTMLAnchorElement>('a[download]')?.getAttribute('href')).toBe(
      '/api/documents/doc-1/file',
    );
    expect(page.querySelector('.more')).toBeNull(); // everything is loaded
  });

  it('opens a cited passage with a little context before it, and marks it', async () => {
    await open('doc-1', 50);
    http.expectOne('/api/documents/doc-1').flush(makeDocument({ chunk_count: 100 }));
    http
      .expectOne('/api/chunks/50')
      .flush({ ...chunk(50, 40, 9), document_id: 'doc-1', document_name: 'report.pdf' });
    const request = http.expectOne((r) => r.url === '/api/documents/doc-1/chunks');
    expect(request.request.params.get('offset')).toBe('35');
    request.flush({
      document_id: 'doc-1',
      total: 100,
      offset: 35,
      limit: READER_PAGE_SIZE,
      items: Array.from({ length: 10 }, (_, i) => chunk(45 + i, 35 + i, 9)),
    });
    await fixture.whenStable();

    const target = page.querySelector('#chunk-50')!;
    expect(target.classList).toContain('target');
    expect(target.getAttribute('aria-label')).toBe('Passage you opened');
    // Text before and after the window can be loaded.
    expect(Array.from(page.querySelectorAll('.more')).map((b) => b.textContent?.trim())).toEqual([
      'Show earlier text',
      'Show more text',
    ]);
  });

  it('labels line ranges for text files', async () => {
    await open('doc-2');
    http
      .expectOne('/api/documents/doc-2')
      .flush(makeDocument({ id: 'doc-2', file_type: 'txt', page_count: null }));
    http
      .expectOne((r) => r.url === '/api/documents/doc-2/chunks')
      .flush({ document_id: 'doc-2', total: 1, offset: 0, limit: 60, items: [chunk(1, 0, null)] });
    await fixture.whenStable();

    expect(page.querySelector('.lines')?.textContent?.trim()).toBe('lines 1–9');
    expect(page.querySelector('.page-divider')).toBeNull();
  });

  it('explains why a failed document has no text', async () => {
    await open('doc-3');
    http.expectOne('/api/documents/doc-3').flush(
      makeDocument({
        status: 'failed',
        failure_code: 'encrypted',
        failure_message: 'This PDF is password-protected.',
      }),
    );
    await fixture.whenStable();

    expect(text()).toContain('This document could not be indexed.');
    expect(text()).toContain('This PDF is password-protected.');
    http.expectNone((r) => r.url.includes('/chunks'));
  });

  it('shows a not-found state for a deleted document', async () => {
    await open('gone');
    http
      .expectOne('/api/documents/gone')
      .flush(
        { error: { code: 'not_found', message: 'Document not found.', request_id: 'r' } },
        { status: 404, statusText: 'Not Found' },
      );
    await fixture.whenStable();

    expect(page.querySelector('h1')?.textContent).toBe('Document not found');
  });
});
