import { HttpEventType, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { makeDocument } from '../../testing/fixtures';
import { LibraryStore } from './library.store';
import { UploadQueueService } from './upload-queue.service';

const file = (name: string, size = 100) => new File([new Uint8Array(size)], name);

describe('UploadQueueService', () => {
  let queue: UploadQueueService;
  let library: LibraryStore;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    queue = TestBed.inject(UploadQueueService);
    library = TestBed.inject(LibraryStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => vi.useRealTimers());

  it('rejects unsupported, empty and oversized files without uploading them', () => {
    queue.add([
      file('a.docx'),
      file('noext'),
      file('empty.txt', 0),
      file('big.pdf', 21 * 1024 * 1024),
    ]);

    expect(queue.items().map((i) => [i.state, i.message])).toEqual([
      ['rejected', 'Only PDF and TXT files can be uploaded.'],
      ['rejected', 'Only PDF and TXT files can be uploaded.'],
      ['rejected', 'The file is empty.'],
      ['rejected', 'The file is larger than the 20 MB limit.'],
    ]);
    http.expectNone('/api/documents');
  });

  it('uploads at most two files at a time, in the order they were chosen', () => {
    queue.add([file('1.pdf'), file('2.pdf'), file('3.pdf')]);

    const requests = http.match('/api/documents');
    expect(requests.map((r) => (r.request.body as FormData).get('file'))).toHaveLength(2);
    expect(((requests[0].request.body as FormData).get('file') as File).name).toBe('1.pdf');
    expect(queue.items().map((i) => i.state)).toEqual(['uploading', 'uploading', 'queued']);

    requests[0].flush(makeDocument({ id: 'd1', status: 'processing' }));

    expect(queue.items().map((i) => i.state)).toEqual(['processing', 'uploading', 'uploading']);
    http.match('/api/documents').forEach((r) => r.flush(makeDocument({ status: 'processing' })));
  });

  it('reports byte progress, then follows the document through processing', () => {
    queue.add([file('report.pdf')]);
    const request = http.expectOne('/api/documents');

    request.event({ type: HttpEventType.UploadProgress, loaded: 50, total: 200 });
    expect(queue.items()[0]).toMatchObject({ state: 'uploading', progress: 25 });

    request.flush(makeDocument({ id: 'd1', status: 'processing' }));
    expect(queue.items()[0]).toMatchObject({ state: 'processing', documentId: 'd1' });

    library.upsert(makeDocument({ id: 'd1', status: 'ready' }));
    expect(queue.items()[0].state).toBe('ready');

    library.upsert(
      makeDocument({ id: 'd1', status: 'failed', failure_message: 'This PDF is damaged.' }),
    );
    expect(queue.items()[0]).toMatchObject({ state: 'failed', message: 'This PDF is damaged.' });
  });

  it('shows the server reason when an upload is refused, with a link for duplicates', () => {
    queue.add([file('copy.pdf')]);

    http.expectOne('/api/documents').flush(
      {
        error: {
          code: 'duplicate_document',
          message: 'This file is already in your library as “report.pdf”.',
          request_id: 'r',
          details: { document_id: 'original', status: 'ready' },
        },
      },
      { status: 409, statusText: 'Conflict' },
    );

    expect(queue.items()[0]).toMatchObject({
      state: 'rejected',
      message: 'This file is already in your library as “report.pdf”.',
      existingId: 'original',
    });
  });

  it('clears finished uploads but keeps those still in progress', () => {
    queue.add([file('bad.exe'), file('good.txt')]);
    expect(queue.hasFinished()).toBe(true);

    queue.clearFinished();

    expect(queue.items().map((i) => i.name)).toEqual(['good.txt']);
    http.expectOne('/api/documents').flush(makeDocument({ status: 'processing' }));
  });
});
