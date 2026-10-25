/** Small, pure formatting helpers shared by several pages. */

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  const mb = bytes / (1024 * 1024);
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

const DATE_FORMAT = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});
const TIME_FORMAT = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' });

export function formatDate(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const sameDay = date.toDateString() === now.toDateString();
  return sameDay ? `Today, ${TIME_FORMAT.format(date)}` : DATE_FORMAT.format(date);
}

/** Where a passage comes from: "p. 3", "lines 12–40", "line 7". */
export function locationLabel(location: {
  page: number | null;
  line_start: number | null;
  line_end: number | null;
}): string {
  if (location.page !== null) {
    return `p. ${location.page}`;
  }
  if (location.line_start !== null && location.line_end !== null) {
    return location.line_start === location.line_end
      ? `line ${location.line_start}`
      : `lines ${location.line_start}–${location.line_end}`;
  }
  return '';
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count.toLocaleString('en-GB')} ${count === 1 ? singular : pluralForm}`;
}
