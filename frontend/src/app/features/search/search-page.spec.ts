import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { makeHit } from '../../../testing/fixtures';
import { SearchResponse } from '../../core/api.models';
import { SearchPage } from './search-page';

function response(overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    query: 'supplier',
    searched_for: ['supplier'],
    total_passages: 1,
    total_documents: 1,
    results: [makeHit()],
    ...overrides,
  };
}

describe('SearchPage', () => {
  let fixture: ComponentFixture<SearchPage>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [SearchPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SearchPage);
    page = fixture.nativeElement as HTMLElement;
  });

  async function open(q?: string, doc?: string): Promise<void> {
    fixture.componentRef.setInput('q', q);
    fixture.componentRef.setInput('doc', doc);
    await fixture.whenStable();
  }

  const text = () => page.textContent?.replace(/\s+/g, ' ') ?? '';

  it('explains what search does before anything is searched', async () => {
    await open();

    expect(text()).toContain('Search inside your documents');
    http.expectNone((r) => r.url === '/api/search');
  });

  it('searches for the query in the URL and shows located, highlighted passages', async () => {
    await open('supplier delays');

    const request = http.expectOne((r) => r.url === '/api/search');
    expect(request.request.params.get('q')).toBe('supplier delays');
    request.flush(
      response({ searched_for: ['supplier', 'delays'], total_passages: 3, total_documents: 2 }),
    );
    await fixture.whenStable();

    expect(text()).toContain('3 passages in 2 documents');
    expect(Array.from(page.querySelectorAll('.searched q')).map((q) => q.textContent)).toEqual([
      'supplier',
      'delays',
    ]);
    expect(page.querySelector('mark')?.textContent).toBe('Supplier');
    expect(text()).toContain('p. 2');
    const openLink = page.querySelector<HTMLAnchorElement>('a.open')!;
    expect(openLink.getAttribute('href')).toBe('/documents/doc-1?chunk=11&q=supplier'); // the reader finds the words again
  });

  it('limits the search to one document when one is chosen', async () => {
    await open('budget', 'doc-7');

    const request = http.expectOne((r) => r.url === '/api/search');
    expect(request.request.params.get('document_id')).toBe('doc-7');
  });

  it('says clearly when nothing matched', async () => {
    await open('zebra');
    http
      .expectOne((r) => r.url === '/api/search')
      .flush(response({ total_passages: 0, total_documents: 0, results: [] }));
    await fixture.whenStable();

    expect(text()).toContain('No passages contain these words');
    expect(text()).toContain('does not match synonyms');
  });

  it('shows the server message when the search is rejected', async () => {
    await open('???');
    http
      .expectOne((r) => r.url === '/api/search')
      .flush(
        {
          error: {
            code: 'empty_query',
            message: 'Enter at least one word to search for.',
            request_id: 'r',
          },
        },
        { status: 422, statusText: 'Unprocessable' },
      );
    await fixture.whenStable();

    expect(page.querySelector('[role="alert"]')?.textContent).toContain('Enter at least one word');
  });

  it('submitting puts the query in the URL', async () => {
    await open();
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const input = page.querySelector<HTMLInputElement>('#search-query')!;
    input.value = '  notice period ';
    input.dispatchEvent(new Event('input'));

    page.querySelector('form')!.dispatchEvent(new Event('submit'));

    expect(navigate).toHaveBeenCalledWith(['/search'], {
      queryParams: { q: 'notice period', doc: null },
    });
  });

  it('submitting the same query again runs the search again (e.g. after an error)', async () => {
    await open('budget');
    http.expectOne((r) => r.url === '/api/search').flush(null, { status: 0, statusText: 'x' });
    await fixture.whenStable();

    page.querySelector('form')!.dispatchEvent(new Event('submit'));

    http.expectOne((r) => r.url === '/api/search').flush(response());
    await fixture.whenStable();
    expect(text()).toContain('1 passage in 1 document');
  });
});
