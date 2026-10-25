import { formatBytes, formatDate, locationLabel, plural } from './format';

describe('format helpers', () => {
  it('formats byte sizes', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2 KB');
    expect(formatBytes(5.5 * 1024 * 1024)).toBe('5.5 MB');
    expect(formatBytes(20 * 1024 * 1024)).toBe('20 MB');
  });

  it('describes where a passage comes from', () => {
    expect(locationLabel({ page: 3, line_start: null, line_end: null })).toBe('p. 3');
    expect(locationLabel({ page: null, line_start: 4, line_end: 9 })).toBe('lines 4–9');
    expect(locationLabel({ page: null, line_start: 7, line_end: 7 })).toBe('line 7');
    expect(locationLabel({ page: null, line_start: null, line_end: null })).toBe('');
  });

  it('pluralises counts', () => {
    expect(plural(1, 'document')).toBe('1 document');
    expect(plural(2, 'document')).toBe('2 documents');
    expect(plural(1200, 'passage')).toBe('1,200 passages');
  });

  it('shows the time for today and the date otherwise', () => {
    const now = new Date('2026-10-26T15:00:00');
    expect(formatDate('2026-10-26T09:30:00', now)).toMatch(/^Today, \d\d:\d\d$/);
    expect(formatDate('2026-10-20T09:30:00', now)).toBe('20 Oct 2026');
  });
});
