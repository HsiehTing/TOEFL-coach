from datetime import date
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "standards/ets-2026/manifest.yaml"


def test_manifest_identifies_the_2026_test_and_official_sources() -> None:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["test_version"] == "TOEFL iBT 2026"
    assert data["effective_from"] == date(2026, 1, 21)
    assert data["last_verified"] == date(2026, 7, 31)
    assert set(data["rubrics"]) == {
        "ets-writing-email-2025-applicable-2026",
        "ets-writing-discussion-2025-applicable-2026",
        "ets-speaking-blueprint-2026-diagnostic",
    }
    assert all(
        url.startswith(("https://www.ets.org/", "https://www.es.ets.org/"))
        for url in data["sources"].values()
    )


def test_score_policy_forbids_task_to_section_conversion() -> None:
    policy = (ROOT / "standards/ets-2026/score-policy.md").read_text(encoding="utf-8")
    assert "單題結果不得宣稱為完整 section band" in policy
    assert "0–5" in policy
    assert "1–6" in policy


def test_coach_taxonomies_match_machine_readable_codes() -> None:
    taxonomy = yaml.safe_load(
        (ROOT / "standards/ets-2026/taxonomy.yaml").read_text(encoding="utf-8")
    )
    for modality, reference in {
        "writing": ROOT / ".agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md",
        "speaking": ROOT / ".agents/skills/toefl-speaking-coach/references/speaking-error-taxonomy.md",
    }.items():
        documented = set(re.findall(r"`([A-Z][A-Z0-9-]+)`", reference.read_text(encoding="utf-8")))
        authoritative = {
            code for code, entry in taxonomy["codes"].items()
            if entry["modality"] in {modality, "all"}
        }
        assert documented == authoritative
