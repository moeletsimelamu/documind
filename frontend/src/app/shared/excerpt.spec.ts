import { TestBed } from '@angular/core/testing';

import {
  Excerpt,
  bestSentence,
  excerptParts,
  segmentText,
  sentenceSpans,
  supportingSentence,
} from './excerpt';

// From NIST SP 800-63B-4, p. 25, as an excerpt: the query "minimum length for a password" matches
// more words in the second sentence, but the answer was drawn from the first.
const NIST =
  'single-factor authentication mechanism to be a minimum of 15 characters in length. ' +
  'Verifiers and CSPs MAY allow passwords that are only used as part of multi-factor ' +
  'authentication processes to be shorter but SHALL require them to be a minimum of eight ' +
  'characters in length.\n\n2. Verifiers and CSPs SHOULD permit a maximum password length';
const NIST_ANSWER =
  'Verifiers and CSPs SHALL require passwords that are used as a single-factor authentication ' +
  'mechanism to be a minimum of 15 characters in length.';

describe('supportingSentence', () => {
  it('finds the sentence an answer was drawn from, by share of its words', () => {
    const [start, end] = supportingSentence(NIST, NIST_ANSWER)!;

    expect(NIST.slice(start, end)).toBe(
      'single-factor authentication mechanism to be a minimum of 15 characters in length.',
    );
  });

  it('is null when no sentence shares enough words with the reference', () => {
    expect(supportingSentence(NIST, 'Kestrel Boxes missed deliveries.')).toBeNull();
  });

  it('takes precedence over the best query match, which is used otherwise', () => {
    const highlights = spansOf(NIST, 'minimum', 'length', 'passwords', 'password');
    const join = (segments: { text: string }[]) => segments.map((s) => s.text).join('');

    expect(join(excerptParts(NIST, highlights).best)).toContain('minimum of eight');
    expect(join(excerptParts(NIST, highlights, NIST_ANSWER).best)).toContain('minimum of 15');
  });
});

/** Highlight spans for every occurrence of each word, the way the API reports matches. */
function spansOf(text: string, ...words: string[]): [number, number][] {
  const spans: [number, number][] = [];
  for (const word of words) {
    for (const match of text.matchAll(new RegExp(`\\b${word}\\b`, 'gi'))) {
      spans.push([match.index ?? 0, (match.index ?? 0) + word.length]);
    }
  }
  return spans.sort((a, b) => a[0] - b[0]);
}

const HANDBOOK =
  'Overtime is paid at 1.5 times the normal rate.\n\n2. Leave\nFull-time staff receive 21 ' +
  'working days of paid vacation per year. Part-time staff receive a pro-rata share. Up to five ' +
  'unused vacation days can be carried over.';

describe('sentenceSpans', () => {
  it('splits at sentence ends and line breaks, trimming whitespace', () => {
    const text = 'One. "Two?" Three!\nFour (five.) six';
    expect(sentenceSpans(text).map(([s, e]) => text.slice(s, e))).toEqual([
      'One.',
      '"Two?"',
      'Three!',
      'Four (five.)',
      'six',
    ]);
  });
});

describe('bestSentence', () => {
  it('picks the sentence with the most different matched words', () => {
    const highlights = spansOf(HANDBOOK, 'paid', 'vacation', 'days', 'staff', 'time');
    const [start, end] = bestSentence(HANDBOOK, highlights)!;

    expect(HANDBOOK.slice(start, end)).toBe(
      'Full-time staff receive 21 working days of paid vacation per year.',
    );
  });

  it('is null when nothing matched', () => {
    expect(bestSentence(HANDBOOK, [])).toBeNull();
  });
});

describe('excerptParts', () => {
  it('splits around the best sentence and keeps every character', () => {
    const highlights = spansOf(HANDBOOK, 'paid', 'vacation', 'days');
    const parts = excerptParts(HANDBOOK, highlights);
    const join = (segments: { text: string }[]) => segments.map((s) => s.text).join('');

    expect(parts.wordMarks).toBe(false);
    expect(join(parts.best)).toBe(
      'Full-time staff receive 21 working days of paid vacation per year.',
    );
    expect(join(parts.before) + join(parts.best) + join(parts.after)).toBe(HANDBOOK);
    expect(parts.best.filter((s) => s.marked).map((s) => s.text)).toEqual([
      'days',
      'paid',
      'vacation',
    ]);
  });

  it('highlights words instead when one sentence makes up most of the excerpt', () => {
    const text = 'The budget of R4.5 million was approved by the committee.';
    const parts = excerptParts(text, spansOf(text, 'budget'));

    expect(parts.wordMarks).toBe(true);
    expect(parts.best).toEqual([]);
  });
});

describe('segmentText', () => {
  it('splits text at highlight offsets', () => {
    expect(
      segmentText('The budget was approved', [
        [4, 10],
        [15, 23],
      ]),
    ).toEqual([
      { text: 'The ', marked: false },
      { text: 'budget', marked: true },
      { text: ' was ', marked: false },
      { text: 'approved', marked: true },
    ]);
  });

  it('ignores overlapping, empty and out-of-range spans instead of trusting them', () => {
    expect(
      segmentText('abcdef', [
        [0, 3],
        [2, 4],
        [5, 5],
        [4, 99],
      ]),
    ).toEqual([
      { text: 'abc', marked: true },
      { text: 'def', marked: false },
    ]);
  });
});

describe('Excerpt', () => {
  it('renders the text exactly, adding no whitespace of its own', async () => {
    const fixture = TestBed.createComponent(Excerpt);
    const text = 'Line one\n  indented line two';
    fixture.componentRef.setInput('text', text);
    fixture.componentRef.setInput('highlights', [[0, 4]]);
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toBe(text);
  });

  it('marks highlighted words and renders document markup as plain text', async () => {
    const fixture = TestBed.createComponent(Excerpt);
    fixture.componentRef.setInput('text', '<b>bold</b> budget <script>alert(1)</script>');
    fixture.componentRef.setInput('highlights', [[12, 18]]);
    fixture.componentRef.setInput('endsMidText', true);
    await fixture.whenStable();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('mark')?.textContent).toBe('budget');
    expect(host.querySelector('b')).toBeNull();
    expect(host.querySelector('script')).toBeNull();
    expect(host.textContent).toContain('<script>alert(1)</script>');
    expect(host.textContent?.trim().endsWith('…')).toBe(true);
  });

  it('highlights the best sentence and underlines the matched words', async () => {
    const fixture = TestBed.createComponent(Excerpt);
    fixture.componentRef.setInput('text', HANDBOOK);
    fixture.componentRef.setInput('highlights', spansOf(HANDBOOK, 'paid', 'vacation', 'days'));
    await fixture.whenStable();

    const host = fixture.nativeElement as HTMLElement;
    const marks = host.querySelectorAll('mark');
    expect(marks).toHaveLength(1);
    expect(marks[0].classList).toContain('best');
    expect(marks[0].textContent).toContain('21 working days of paid vacation');
    expect(Array.from(host.querySelectorAll('.term')).map((t) => t.textContent)).toEqual([
      'paid',
      'days',
      'paid',
      'vacation',
      'vacation',
      'days',
    ]);
    expect(host.textContent).toBe(HANDBOOK);
  });
});
