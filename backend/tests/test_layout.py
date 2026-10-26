from documind.ingestion.extraction import extract_bytes
from documind.ingestion.layout import clean_pdf_pages
from tests.pdf_factory import make_pdf

TOPICS = ["leave", "expenses", "equipment", "conduct", "training", "travel", "payroll", "benefits"]


def body(n: int) -> list[str]:
    """Four lines as pypdf returns them from a typeset page, different on every page."""
    topic = TOPICS[n % len(TOPICS)]
    return [
        f"Employees with a question about {topic} should first speak to their manager,",
        f"who will try to resolve any {topic} matter informally within five working days.",
        f"If a {topic} matter cannot be resolved informally, the employee may raise it",
        f"formally in writing with the {topic} team in People Operations.",
    ]


def page(number: int, lines: list[str] | None = None) -> str:
    header = ["Northwind Staff Handbook", "Version 4 - 2026"]
    return "\n".join([*header, *(lines or body(number)), f"Page {number} of 6"])


def test_running_headers_footers_and_page_numbers_are_removed() -> None:
    cleaned = clean_pdf_pages([page(n) for n in range(1, 7)])

    for text in cleaned:
        assert "Northwind Staff Handbook" not in text
        assert "Version 4" not in text
        assert "Page" not in text
        assert text.startswith("Employees with a question") and text.endswith("Operations.")


def test_a_line_on_only_a_few_pages_is_not_a_running_header() -> None:
    pages = [page(n) for n in range(1, 11)]
    for index in (2, 7):  # a heading that happens to start two of ten pages
        pages[index] = "Grievances\n" + pages[index]

    cleaned = clean_pdf_pages(pages)

    assert all("Grievances" in cleaned[index] for index in (2, 7))


def test_repeated_lines_in_the_body_of_a_page_are_kept() -> None:
    def lines(n: int) -> list[str]:
        middle = ["Contact People Operations on extension 4400."]  # on every page
        return body(n) + middle + body(n + 1) + body(n + 2)

    cleaned = clean_pdf_pages([page(n, lines(n)) for n in range(1, 7)])

    assert all("Contact People Operations on extension 4400." in text for text in cleaned)


def test_page_numbers_are_removed_when_they_rise_with_the_page() -> None:
    lines = [body(n) for n in range(6)]
    pages = [
        "i\n" + "\n".join(lines[0]),  # front matter
        "\n".join(lines[1]) + "\nii",
        "- 1 -\n" + "\n".join(lines[2]),  # printed numbers start at 1 on the third page
        "\n".join(lines[3]) + "\n2",
        "civic\n" + "\n".join(lines[4]) + "\n3",
        "\n".join(lines[5]) + "\nPage 4",
    ]

    cleaned = clean_pdf_pages(pages)

    assert [text.split("\n")[0] for text in cleaned] == [
        lines[0][0],
        lines[1][0],
        lines[2][0],
        lines[3][0],
        "civic",
        lines[5][0],
    ]
    assert all(text.endswith("Operations.") for text in cleaned)


def test_numbers_at_the_bottom_of_a_table_are_kept() -> None:
    table = ["Region totals for the quarter", "1200", "1350", "1410", "1525"]

    cleaned = clean_pdf_pages(["\n".join(body(n) + table[: 3 + n]) for n in range(3)])

    assert cleaned[2].endswith("1200\n1350\n1410\n1525")
    assert cleaned[0].endswith("1200\n1350")


def test_paragraphs_list_items_and_headings_are_separated() -> None:
    paragraph = [
        "Employees who have a problem at work should first raise it with their manager,",
        "who will try to resolve it informally.",
    ]
    lines = [
        "Raising a grievance",
        *paragraph,
        "The employee should explain:",
        "• what the grievance is about",
        "• what outcome they would like",
        "3.2 Grievance meetings",
        "The meeting should be held without unreasonable delay after the grievance",
        "is received, and the employee should be given time to prepare for it.",
    ]

    (text,) = clean_pdf_pages(["\n".join(lines)])
    paragraphs = text.split("\n\n")

    assert paragraphs[0] == "Raising a grievance"
    assert paragraphs[1] == "\n".join(paragraph)  # wrapped lines stay one paragraph
    assert paragraphs[2] == "The employee should explain:"
    assert paragraphs[3:5] == ["• what the grievance is about", "• what outcome they would like"]
    assert paragraphs[5] == "3.2 Grievance meetings"
    assert paragraphs[6].startswith("The meeting should")


def test_dash_bullets_start_items_but_ordinary_wrapped_lines_do_not() -> None:
    en_dash, em_dash = chr(0x2013), chr(0x2014)
    lines = [
        "Staff turnover in the warehouse fell to",
        "2 per cent, and the share of agency staff fell to",
        "é levels not seen since the warehouse opened in 2019:",
        f"{en_dash} first item",
        f"{em_dash} second item",
    ]

    (text,) = clean_pdf_pages(["\n".join(lines)])

    assert text.split("\n\n") == ["\n".join(lines[:3]), lines[3], lines[4]]


def test_dot_leaders_are_shortened() -> None:
    (text,) = clean_pdf_pages(["Contents\nIntroduction ............................ 5"])

    assert "Introduction … 5" in text
    assert "...." not in text


def test_words_split_across_lines_are_rejoined() -> None:
    (text,) = clean_pdf_pages(
        [
            "the inter-\nnational office uses a left-to-\nright layout and Anglo-\nSaxon names;\n"
            "task-specific models need task-\nspecific data"
        ]
    )

    assert "international office" in text
    assert "left-to-right layout" in text  # the word already had a hyphen
    assert "Anglo-\nSaxon" in text  # a capitalised second part: probably a compound or name
    assert "task-specific data" in text  # hyphenated elsewhere in the document


def test_pdf_extraction_applies_the_layout_clean_up() -> None:
    pdf = make_pdf([page(n) for n in range(1, 5)])

    document = extract_bytes(pdf, "pdf", max_pages=10, max_chars=100_000)

    assert document.page_count == 4
    assert all(p.text.startswith("Employees with a question") for p in document.pages)
    assert all("Handbook" not in p.text for p in document.pages)


def test_a_page_holding_only_the_running_header_counts_as_empty() -> None:
    pdf = make_pdf([page(1), page(2), "Northwind Staff Handbook\nVersion 4 - 2026", page(4)])

    document = extract_bytes(pdf, "pdf", max_pages=10, max_chars=100_000)

    assert document.pages[2].text == ""
    assert document.empty_page_count == 1
