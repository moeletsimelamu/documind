import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ConnectionService, connectionInterceptor } from './connection.service';

describe('ConnectionService', () => {
  let connection: ConnectionService;
  let client: HttpClient;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([connectionInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    connection = TestBed.inject(ConnectionService);
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => vi.useRealTimers());

  function failRequest(status: number, body: string | object | null): void {
    client.get('/api/documents').subscribe({ error: () => undefined });
    http.expectOne('/api/documents').flush(body, { status, statusText: 'x' });
  }

  it('goes offline when the server cannot be reached, then recovers by polling health', () => {
    failRequest(0, null);
    expect(connection.online()).toBe(false);

    vi.advanceTimersByTime(5000);
    http.expectOne('/api/health').flush(null, { status: 0, statusText: 'x' });
    expect(connection.online()).toBe(false);

    vi.advanceTimersByTime(5000);
    http.expectOne('/api/health').flush({ status: 'ok' });
    expect(connection.online()).toBe(true);

    vi.advanceTimersByTime(20000);
    http.expectNone('/api/health'); // polling stopped
  });

  it('goes offline when a proxy answers 5xx without the API error envelope', () => {
    failRequest(500, 'Error occurred while trying to proxy');

    expect(connection.online()).toBe(false);
  });

  it('stays online for errors the API itself returns', () => {
    failRequest(500, { error: { code: 'internal_error', message: 'x', request_id: 'r' } });
    failRequest(404, { error: { code: 'not_found', message: 'x', request_id: 'r' } });

    expect(connection.online()).toBe(true);
  });
});
