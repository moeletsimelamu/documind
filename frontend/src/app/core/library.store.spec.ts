import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { makeDocument } from '../../testing/fixtures';
import { LibraryStore, POLL_INTERVAL_MS } from './library.store';

describe('LibraryStore', () => {
  let store: LibraryStore;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    store = TestBed.inject(LibraryStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('loads the library from the server', () => {
    store.load();
    expect(store.loading()).toBe(true);

    http.expectOne('/api/documents').flush([makeDocument()]);

    expect(store.loaded()).toBe(true);
    expect(store.loading()).toBe(false);
    expect(store.documents().map((d) => d.name)).toEqual(['report.pdf']);
  });

  it('keeps the error when loading fails', () => {
    store.load();
    http.expectOne('/api/documents').flush(null, { status: 0, statusText: 'Unknown Error' });

    expect(store.loaded()).toBe(false);
    expect(store.error()?.code).toBe('network');
  });

  it('polls processing documents until they finish', () => {
    store.load();
    http
      .expectOne('/api/documents')
      .flush([
        makeDocument({ id: 'a', status: 'processing' }),
        makeDocument({ id: 'b', status: 'ready' }),
      ]);
    expect(store.processingCount()).toBe(1);

    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    http.expectOne('/api/documents/a').flush(makeDocument({ id: 'a', status: 'processing' }));

    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    http
      .expectOne('/api/documents/a')
      .flush(makeDocument({ id: 'a', status: 'failed', failure_code: 'malformed' }));

    expect(store.byId().get('a')?.status).toBe('failed');
    expect(store.processingCount()).toBe(0);
    vi.advanceTimersByTime(POLL_INTERVAL_MS * 3);
    http.expectNone('/api/documents/a'); // polling stopped
  });

  it('drops a processing document that was deleted elsewhere', () => {
    store.upsert(makeDocument({ id: 'gone', status: 'processing' }));

    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    http
      .expectOne('/api/documents/gone')
      .flush(
        { error: { code: 'not_found', message: 'x', request_id: 'r' } },
        { status: 404, statusText: 'Not Found' },
      );

    expect(store.documents()).toEqual([]);
  });

  it('adds new documents first and replaces existing ones', () => {
    store.upsert(makeDocument({ id: 'old', name: 'old.txt' }));
    store.upsert(makeDocument({ id: 'new', name: 'new.txt' }));
    store.upsert(makeDocument({ id: 'old', name: 'renamed.txt' }));

    expect(store.documents().map((d) => d.name)).toEqual(['new.txt', 'renamed.txt']);
  });

  it('removes a document after the server deletes it', () => {
    store.upsert(makeDocument({ id: 'x' }));
    let done = false;

    store.delete('x').subscribe(() => (done = true));
    const request = http.expectOne('/api/documents/x');
    expect(request.request.method).toBe('DELETE');
    expect(store.documents().length).toBe(1); // not removed before the server confirms
    request.flush(null, { status: 204, statusText: 'No Content' });

    expect(done).toBe(true);
    expect(store.documents()).toEqual([]);
  });
});
