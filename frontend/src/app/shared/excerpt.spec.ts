import { TestBed } from '@angular/core/testing';

import { Excerpt, segmentText } from './excerpt';

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
});
