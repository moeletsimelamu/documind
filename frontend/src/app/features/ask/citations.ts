/** A run of answer text, or a citation marker such as "S2". */
export type AnswerPart = { text: string; marker: null } | { text: string; marker: string };

const MARKER = /\[(S\d+)\]/g;

/**
 * Splits a generated answer into text and citation markers. Only markers the server confirmed
 * (``cited``) become links to sources; anything else stays as plain text.
 */
export function splitCitations(answer: string, cited: readonly string[]): AnswerPart[] {
  const parts: AnswerPart[] = [];
  let position = 0;
  for (const match of answer.matchAll(MARKER)) {
    const index = match.index ?? 0;
    if (!cited.includes(match[1])) {
      continue;
    }
    if (index > position) {
      parts.push({ text: answer.slice(position, index), marker: null });
    }
    parts.push({ text: match[0], marker: match[1] });
    position = index + match[0].length;
  }
  if (position < answer.length) {
    parts.push({ text: answer.slice(position), marker: null });
  }
  return parts;
}

/**
 * Confirmed sources that the answer text never marks. Small models often list their sources in
 * ``cited`` without writing markers into the text; these are shown after the answer instead, so
 * every source the answer relies on can still be opened.
 */
export function citedWithoutMarker(answer: string, cited: readonly string[]): string[] {
  const marked = new Set(Array.from(answer.matchAll(MARKER), (match) => match[1]));
  return cited.filter((id) => !marked.has(id));
}
