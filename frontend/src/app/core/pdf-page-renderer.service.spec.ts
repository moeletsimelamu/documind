import { itemsInPassage } from './pdf-page-renderer.service';

// Text runs as pdf.js reports them for a page: lines, with hyphenation and page furniture.
const ITEMS = [
  { str: 'NIST SP 800-63B-4' }, // running header, removed from the stored passage
  { str: '3.1.1.2. Password Verifiers' },
  { str: 'The following requirements apply to passwords.' },
  { str: '1. Verifiers and CSPs SHALL require passwords that are used as a single-' },
  { str: 'factor authentication mechanism to be a minimum of 15 characters in length.' },
  { str: 'the' }, // short and common: outlined only next to a longer match
  { str: 'Appendix A' },
  { str: '25' }, // page number
];

const PASSAGE =
  '1. Verifiers and CSPs SHALL require passwords that are used as a single-factor ' +
  'authentication mechanism to be a minimum of 15 characters in length.';

describe('itemsInPassage', () => {
  it('finds the lines of a passage despite hyphenation and the clean-up of stored text', () => {
    expect(itemsInPassage(ITEMS, PASSAGE)).toEqual([3, 4, 5]);
  });

  it('does not outline short common words on their own', () => {
    expect(itemsInPassage([{ str: 'the' }, { str: 'and' }], 'the cat and the dog')).toEqual([]);
  });

  it('finds nothing for an empty passage', () => {
    expect(itemsInPassage(ITEMS, '  ')).toEqual([]);
  });
});
