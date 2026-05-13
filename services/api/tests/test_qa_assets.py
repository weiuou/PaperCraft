import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SUITE_PATH = ROOT / "docs" / "qa" / "regression-sample-suite.json"


def test_regression_sample_suite_matches_mvp_contract() -> None:
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    samples = suite["samples"]

    assert suite["schema"] == "papercraft.regression-suite.v1"
    assert len(samples) == 21
    assert len({sample["id"] for sample in samples}) == len(samples)
    assert _count(samples, "pet") == 5
    assert _count(samples, "bust") == 5
    assert _count(samples, "simple_object") == 5
    assert _count(samples, "complex_background") == 3
    assert _count(samples, "upload_validation") == 3

    positive_samples = [sample for sample in samples if sample["expected_outcome"] == "success"]
    assert len(positive_samples) == 15
    for sample in positive_samples:
        assert sample["category"] in {"pet", "bust", "simple_object"}
        assert 1 <= sample["source_image_count"] <= 3
        assert sample["paper_size"] in {"a4", "a3"}
        assert sample["max_pages"] > 0
        assert sample["expected_stages"][-1] == "completed"

    failure_samples = [sample for sample in samples if sample["expected_outcome"] != "success"]
    assert len(failure_samples) == 6
    for sample in failure_samples:
        assert sample["expected_error_code"]
        assert sample["expected_failure_stage"]
        assert sample["recovery_guidance"]


def test_beta_release_docs_exist() -> None:
    for relative_path in (
        "docs/qa/regression-runbook.md",
        "docs/qa/manual-assembly-qa.md",
        "docs/qa/beta-release-checklist.md",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "Last updated: 2026-05-13" in content


def _count(samples: list[dict[str, object]], group: str) -> int:
    return sum(1 for sample in samples if sample["group"] == group)
