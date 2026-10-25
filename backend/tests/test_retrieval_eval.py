"""Regression guard for retrieval quality on the evaluation set (see tests/eval/).

Baseline measured on 2026-10-25: keyword questions hit@1 95%, hit@5 100%; paraphrased questions
hit@5 56%. The floors below leave a little room so that a deliberate trade-off can be made, but
a real regression fails the build.
"""

from tests.eval.run_eval import evaluate


def test_retrieval_quality_does_not_regress() -> None:
    report = evaluate()

    assert report.hit_rate(5, "keyword") >= 0.95
    assert report.hit_rate(1, "keyword") >= 0.90
    assert report.hit_rate(5) >= 0.80
    # Keyword search cannot match vocabulary it has never seen; this documents, not hides, it.
    assert report.hit_rate(5, "paraphrase") < 1.0
