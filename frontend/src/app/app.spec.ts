import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';
import { ConnectionService, connectionInterceptor } from './core/connection.service';

describe('App shell', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    // Only intervals (the reconnect poll) are faked; whenStable() needs real timeouts.
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(withInterceptors([connectionInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => vi.useRealTimers());

  it('loads configuration and the library, and offers navigation', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();

    http.expectOne('/api/config');
    http.expectOne('/api/documents');
    const links = Array.from(fixture.nativeElement.querySelectorAll('nav a')).map((a) =>
      (a as HTMLElement).textContent?.trim(),
    );
    expect(links).toEqual(['Library', 'Search', 'Ask']);
    expect(fixture.nativeElement.querySelector('.skip-link')?.getAttribute('href')).toBe('#main');
  });

  it('shows an outage banner while the server is unreachable and reloads when it is back', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    http.expectOne('/api/config').flush(null, { status: 0, statusText: 'x' });
    http.expectOne('/api/documents').flush(null, { status: 0, statusText: 'x' });
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('.outage')?.textContent).toContain(
      "Can't reach the DocuMind server",
    );

    vi.advanceTimersByTime(5000);
    http.expectOne('/api/health').flush({ status: 'ok' });
    await fixture.whenStable();

    expect(TestBed.inject(ConnectionService).online()).toBe(true);
    expect(fixture.nativeElement.querySelector('.outage')).toBeNull();
    http.expectOne('/api/config');
    http.expectOne('/api/documents');
  });
});
