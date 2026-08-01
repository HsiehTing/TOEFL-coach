from pathlib import Path

from toefl_tracker.audit import audit_workspace
from toefl_tracker.reports import rebuild_modality


def test_full_practice_cadence_and_integrity(populated_workspace: Path) -> None:
    writing_reports = {path.name for path in rebuild_modality(populated_workspace, "writing")}
    speaking_reports = {path.name for path in rebuild_modality(populated_workspace, "speaking")}
    assert "writing-common-0003.md" in writing_reports
    assert "writing-academic-discussion-0003.md" in writing_reports
    assert "speaking-common-0006.md" in speaking_reports
    assert "speaking-listen-and-repeat-0003.md" in speaking_reports
    assert "speaking-take-an-interview-0003.md" in speaking_reports
    profile = (populated_workspace / "tracker/speaking/profile.md").read_text()
    assert "`SPK-FLUENCY`: relapsed" in profile
    assert audit_workspace(populated_workspace) == []
