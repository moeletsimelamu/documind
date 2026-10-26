import random

import pytest

from documind.ingestion.chunking import (
    CHUNK_MAX_CHARS,
    CHUNK_TARGET_CHARS,
    chunk_lines,
    normalize_text,
)


def non_whitespace(text: str) -> str:
    return "".join(text.split())


def test_normalize_unifies_line_endings_and_removes_control_characters() -> None:
    raw = "first\r\nsecond\rthird\x00 \x07bell\tand tab  \n"

    assert normalize_text(raw) == "first\nsecond\nthird bell and tab\n"


def test_normalize_applies_nfkc() -> None:
    # "ﬁ" ligature and a non-breaking space, both common in PDF text layers.
    assert normalize_text("\ufb01nance\u00a0report") == "finance report"


def test_normalize_keeps_line_count_for_text_files() -> None:
    raw = "one\n\n\nfour  \n   five\nsix-\nseven"

    normalized = normalize_text(raw)

    assert normalized.count("\n") == raw.count("\n")
    assert "six-\nseven" in normalized  # hyphens are only joined for PDFs (layout.py)


def test_normalize_removes_soft_hyphens() -> None:
    assert normalize_text("docu­mentation") == "documentation"


def test_short_text_is_one_chunk_with_its_line_range() -> None:
    chunks = chunk_lines("\n\nTitle\nfirst line\n\n", joiner="\n")

    assert len(chunks) == 1
    assert chunks[0].text == "Title\nfirst line"
    assert (chunks[0].first_line, chunks[0].last_line) == (3, 4)


def test_paragraphs_are_kept_together_when_they_fit() -> None:
    paragraph_a = "\n".join(["alpha " * 15] * 8)  # about 720 characters
    paragraph_b = "\n".join(["beta " * 15] * 8)
    text = f"{paragraph_a}\n\n{paragraph_b}"

    chunks = chunk_lines(text, joiner="\n")

    assert len(chunks) == 2
    assert "beta" not in chunks[0].text
    assert "alpha" not in chunks[1].text
    assert (chunks[0].first_line, chunks[0].last_line) == (1, 8)
    assert (chunks[1].first_line, chunks[1].last_line) == (10, 17)


def test_pdf_joiner_turns_visual_line_breaks_into_spaces() -> None:
    chunks = chunk_lines("The contract term is\nthree years.\n\nPayment is monthly.", joiner=" ")

    assert chunks[0].text == "The contract term is three years.\n\nPayment is monthly."


def test_very_long_line_is_split_at_sentences_and_keeps_its_line_number() -> None:
    sentence = "This sentence about revenue recognition is exactly long enough. "
    line = (sentence * 60).strip()  # one line, about 3,800 characters

    chunks = chunk_lines(f"intro\n{line}", joiner="\n")

    assert len(chunks) >= 3
    assert all(len(c.text) <= CHUNK_MAX_CHARS for c in chunks)
    assert chunks[-1].first_line == chunks[-1].last_line == 2
    assert non_whitespace("".join(c.text for c in chunks)) == non_whitespace(f"intro{line}")


def test_text_without_spaces_is_split_hard() -> None:
    blob = "x" * (CHUNK_TARGET_CHARS * 3 + 10)

    chunks = chunk_lines(blob, joiner="\n")

    assert [len(c.text) for c in chunks] == [CHUNK_TARGET_CHARS] * 3 + [10]


def test_empty_text_has_no_chunks() -> None:
    assert chunk_lines(" \n\n \n", joiner="\n") == []


@pytest.mark.parametrize("seed", range(25))
def test_chunks_cover_every_character_in_order(seed: int) -> None:
    """Property check over random documents: nothing is dropped, sizes stay bounded."""
    rng = random.Random(seed)
    words = ["budget", "the", "audit", "of", "Q3", "risk", "supplier", "and", "net", "margin."]
    lines = []
    for _ in range(rng.randint(1, 400)):
        roll = rng.random()
        if roll < 0.15:
            lines.append("")
        elif roll < 0.18:
            lines.append("y" * rng.randint(1, 4000))  # unbroken token
        else:
            lines.append(" ".join(rng.choice(words) for _ in range(rng.randint(1, 120))))
    text = normalize_text("\n".join(lines))

    for joiner in ("\n", " "):
        chunks = chunk_lines(text, joiner=joiner)

        assert non_whitespace("".join(c.text for c in chunks)) == non_whitespace(text)
        assert all(0 < len(c.text) <= CHUNK_MAX_CHARS for c in chunks)
        assert all(c.first_line <= c.last_line for c in chunks)
        assert [c.first_line for c in chunks] == sorted(c.first_line for c in chunks)
        # Line ranges point at the text they claim to contain.
        source_lines = text.split("\n")
        for chunk in chunks:
            claimed = "".join(source_lines[chunk.first_line - 1 : chunk.last_line])
            assert non_whitespace(chunk.text) in non_whitespace(claimed)


def test_chunks_are_reasonably_sized_for_ordinary_prose() -> None:
    text = "\n".join(
        ("The committee reviewed the proposal and asked for more detail. " * 3).strip()
        if i % 6
        else ""
        for i in range(300)
    )

    chunks = chunk_lines(text, joiner=" ")

    sizes = [len(c.text) for c in chunks]
    assert max(sizes) <= CHUNK_MAX_CHARS
    # Apart from the final chunk, none should be tiny.
    assert min(sizes[:-1]) >= CHUNK_TARGET_CHARS // 2
