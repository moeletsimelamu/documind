import { citedWithoutMarker, splitCitations } from './citations';

describe('citedWithoutMarker', () => {
  it('lists confirmed sources that the text does not mark, in cited order', () => {
    expect(citedWithoutMarker('Corpus: BooksCorpus and Wikipedia.', ['S4', 'S5'])).toEqual([
      'S4',
      'S5',
    ]);
    expect(citedWithoutMarker('Budget R4.5 million [S2].', ['S2', 'S3'])).toEqual(['S3']);
    expect(citedWithoutMarker('Budget R4.5 million [S2].', ['S2'])).toEqual([]);
  });
});

describe('splitCitations', () => {
  it('turns confirmed markers into separate parts', () => {
    expect(splitCitations('R4.5 million [S1]. Launch in February [S2].', ['S1', 'S2'])).toEqual([
      { text: 'R4.5 million ', marker: null },
      { text: '[S1]', marker: 'S1' },
      { text: '. Launch in February ', marker: null },
      { text: '[S2]', marker: 'S2' },
      { text: '.', marker: null },
    ]);
  });

  it('leaves markers the server did not confirm as plain text', () => {
    expect(splitCitations('Approved [S1][S4].', ['S1'])).toEqual([
      { text: 'Approved ', marker: null },
      { text: '[S1]', marker: 'S1' },
      { text: '[S4].', marker: null },
    ]);
  });

  it('handles an answer with no markers', () => {
    expect(splitCitations('Plain text.', [])).toEqual([{ text: 'Plain text.', marker: null }]);
  });
});
