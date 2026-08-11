from pathlib import Path

import pytest

from toefl_tracker.calibration import validate_writing_calibration
from toefl_tracker.models import ValidationError


ROOT = Path(__file__).parents[1]


def test_fixed_writing_calibration_suite_covers_both_routes() -> None:
    results = validate_writing_calibration(ROOT)

    assert {row["task_type"] for row in results} == {"email", "academic_discussion"}
    assert len([row for row in results if row["task_type"] == "email"]) >= 2
    assert len([row for row in results if row["task_type"] == "academic_discussion"]) >= 2
    assert all(row["result_label"] == "simulated_task_score" for row in results)
    assert all(row["rubric_version"].startswith("ets-writing-") for row in results)


def test_calibration_detects_score_drift(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(ROOT / "tests/fixtures/calibration", tmp_path / "tests/fixtures/calibration")
    shutil.copytree(ROOT / "tests/fixtures/writing", tmp_path / "tests/fixtures/writing")
    cases = tmp_path / "tests/fixtures/calibration/writing/cases.yaml"
    cases.write_text(cases.read_text(encoding="utf-8").replace("minimum: 4", "minimum: 5"), encoding="utf-8")

    with pytest.raises(ValidationError, match="outside approved range"):
        validate_writing_calibration(tmp_path)


def test_calibration_detects_code_and_rubric_reason_drift(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(ROOT / "tests/fixtures/calibration", tmp_path / "tests/fixtures/calibration")
    shutil.copytree(ROOT / "tests/fixtures/writing", tmp_path / "tests/fixtures/writing")
    events = tmp_path / "tests/fixtures/calibration/writing/email-basic/events.jsonl"
    events.write_text(
        events.read_text(encoding="utf-8").replace('"GRAM-CLAUSE"', '"GRAM-ARTICLE"'),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="code classification drift"):
        validate_writing_calibration(tmp_path)

    events.write_text(
        events.read_text(encoding="utf-8").replace('"GRAM-ARTICLE"', '"GRAM-CLAUSE"'),
        encoding="utf-8",
    )
    feedback = tmp_path / "tests/fixtures/calibration/writing/email-basic/feedback.md"
    feedback.write_text(
        feedback.read_text(encoding="utf-8").replace("clear, polite", "well-organized"),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="rubric-reason drift"):
        validate_writing_calibration(tmp_path)
