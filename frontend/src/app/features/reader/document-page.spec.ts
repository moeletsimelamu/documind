import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { makeDocument } from '../../../testing/fixtures';
import { Chunk, DocumentMatches } from '../../core/api.models';
import { PdfPageRenderer, RenderedPage } from '../../core/pdf-page-renderer.service';
import { DocumentPage, READER_PAGE_SIZE } from './document-page';

/** Stands in for pdf.js, which jsdom cannot run; real rendering is checked end to end. */
class FakeRenderer {
  calls: { url: string; page: number; passage: string | null }[] = [];
  result: RenderedPage | Error = {
    pageCount: 3,
    width: 400,
    height: 520,
    passageBoxes: [{ left: 40, top: 100, width: 300, height: 14 }],
  };

  render(
    url: string,
    page: number,
    _canvas: HTMLCanvasElement,
    _width: number,
    passage: string | null,
  ): Promise<RenderedPage> {
    this.calls.push({ url, page, passage });
    return this.result instanceof Error
      ? Promise.reject(this.result)
      : Promise.resolve(this.result);
  }
}

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
  let renderer: FakeRenderer;

  beforeEach(() => {
    renderer = new FakeRenderer();
    TestBed.configureTestingModule({
      imports: [DocumentPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: PdfPageRenderer, useValue: renderer },
      ],
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

  describe('navigation in a long PDF', () => {
    const LONG = makeDocument({ page_count: 120, chunk_count: 300 });
    const windowFrom = (offset: number, page = 1) => ({
      document_id: 'doc-1',
      total: 300,
      offset,
      limit: READER_PAGE_SIZE,
      items: Array.from({ length: 10 }, (_, i) =>
        chunk(1000 + offset + i, offset + i, page, `Passage ${offset + i} about suppliers`),
      ),
    });

    async function openLong(q?: string): Promise<void> {
      fixture.componentRef.setInput('q', q);
      await open('doc-1');
      http.expectOne('/api/documents/doc-1').flush(LONG);
      http.expectOne((r) => r.url === '/api/documents/doc-1/chunks').flush(windowFrom(0));
      await fixture.whenStable();
    }

    const field = (id: string) => page.querySelector<HTMLInputElement>(`#${id}`)!;
    async function submit(id: string, value: string): Promise<void> {
      field(id).value = value;
      field(id).dispatchEvent(new Event('input'));
      field(id).form!.dispatchEvent(new Event('submit', { cancelable: true }));
      await fixture.whenStable();
    }

    const matches = (...found: [number, number, number][]): DocumentMatches => ({
      document_id: 'doc-1',
      query: 'supplier',
      searched_for: ['supplier'],
      total: found.length,
      truncated: false,
      all_words: true,
      matches: found.map(([chunk_id, ordinal, pageNumber]) => ({
        chunk_id,
        ordinal,
        page: pageNumber,
        line_start: null,
        line_end: null,
        highlights: [[16, 25]],
      })),
    });

    it('jumps to a page and marks where it starts', async () => {
      await openLong();

      await submit('goto-page', '77');
      const request = http.expectOne((r) => r.url === '/api/documents/doc-1/chunks');
      expect(request.request.params.get('page')).toBe('77');
      request.flush(windowFrom(190, 77));
      await fixture.whenStable();

      expect(page.querySelector('.page-divider')?.textContent?.trim()).toBe('Page 77');
      expect(page.querySelector('#chunk-1190')?.classList).toContain('current');
      expect(text()).toContain('Show earlier text');
    });

    it('refuses a page outside the document without asking the server', async () => {
      await openLong();

      await submit('goto-page', '121');

      expect(text()).toContain('Enter a page from 1 to 120.');
      http.expectNone((r) => r.url.includes('/chunks'));
    });

    it('finds the words, marks them, and steps to a match outside the loaded text', async () => {
      await openLong();

      await submit('find-in-document', 'supplier');
      const find = http.expectOne((r) => r.url === '/api/documents/doc-1/matches');
      expect(find.request.params.get('q')).toBe('supplier');
      find.flush(matches([1003, 3, 1], [1250, 250, 100]));
      await fixture.whenStable();

      expect(page.querySelector('.match-count')?.textContent).toBe('1 of 2');
      expect(page.querySelector('#chunk-1003 mark')?.textContent).toBe('suppliers');
      expect(page.querySelector('#chunk-1003')?.classList).toContain('current');

      page.querySelector<HTMLButtonElement>('[aria-label="Next match"]')!.click();
      await fixture.whenStable();
      const load = http.expectOne((r) => r.url === '/api/documents/doc-1/chunks');
      expect(load.request.params.get('offset')).toBe('245'); // a little context before it
      load.flush(windowFrom(245, 100));
      await fixture.whenStable();

      expect(page.querySelector('.match-count')?.textContent).toBe('2 of 2');
      expect(page.querySelector('#chunk-1250')?.classList).toContain('current');

      page.querySelector<HTMLButtonElement>('[aria-label="Next match"]')!.click();
      await fixture.whenStable();
      http.expectOne((r) => r.url === '/api/documents/doc-1/chunks').flush(windowFrom(0));
      await fixture.whenStable();
      expect(page.querySelector('.match-count')?.textContent).toBe('1 of 2'); // wraps around
    });

    it('says so when nothing matches', async () => {
      await openLong();

      await submit('find-in-document', 'unicorn');
      http.expectOne((r) => r.url === '/api/documents/doc-1/matches').flush(matches());
      await fixture.whenStable();

      expect(page.querySelector('.match-count')?.textContent).toBe('No matches');
    });

    it('finds the words of the search that opened the document', async () => {
      await openLong('supplier');

      expect(field('find-in-document').value).toBe('supplier');
      http.expectOne((r) => r.url === '/api/documents/doc-1/matches').flush(matches([1004, 4, 1]));
      await fixture.whenStable();

      expect(page.querySelector('.match-count')?.textContent).toBe('1 of 1');
    });

    it('shows the original page with the current passage outlined', async () => {
      await openLong();
      await submit('find-in-document', 'supplier');
      http.expectOne((r) => r.url === '/api/documents/doc-1/matches').flush(matches([1003, 3, 1]));
      await fixture.whenStable();

      page.querySelector<HTMLButtonElement>('.original-toggle')!.click();
      await fixture.whenStable();
      await new Promise((resolve) => setTimeout(resolve)); // let the render promise settle
      await fixture.whenStable();

      expect(renderer.calls.at(-1)).toEqual({
        url: '/api/documents/doc-1/file',
        page: 1,
        passage: 'Passage 3 about suppliers',
      });
      expect(page.querySelector('.original-title')?.textContent?.trim()).toBe(
        'Original · page 1 of 120',
      );
      expect(page.querySelectorAll('.passage-box')).toHaveLength(1);
      expect(page.querySelector('canvas')?.getAttribute('aria-label')).toContain('as printed');

      page.querySelector<HTMLButtonElement>('[aria-label="Next page"]')!.click();
      await fixture.whenStable();
      expect(renderer.calls.at(-1)?.page).toBe(2);
    });

    it('explains when a page cannot be shown', async () => {
      renderer.result = new Error('broken');
      await openLong();

      page.querySelector<HTMLButtonElement>('.original-toggle')!.click();
      await fixture.whenStable();
      await new Promise((resolve) => setTimeout(resolve));
      await fixture.whenStable();

      expect(text()).toContain('This page could not be shown.');
    });

    it('offers the original page only for PDFs', async () => {
      await open('doc-2');
      http
        .expectOne('/api/documents/doc-2')
        .flush(makeDocument({ id: 'doc-2', file_type: 'txt', page_count: null }));
      http
        .expectOne((r) => r.url === '/api/documents/doc-2/chunks')
        .flush({
          document_id: 'doc-2',
          total: 1,
          offset: 0,
          limit: 60,
          items: [chunk(1, 0, null)],
        });
      await fixture.whenStable();

      expect(page.querySelector('.original-toggle')).toBeNull();
      expect(page.querySelector('#goto-page')).toBeNull();
      expect(page.querySelector('#find-in-document')).not.toBeNull();
    });
  });
});
