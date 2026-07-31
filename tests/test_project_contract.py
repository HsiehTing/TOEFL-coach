from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_private_audio_and_python_artifacts_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tracker/**/media/" in ignore
    assert "__pycache__/" in ignore
    assert ".pytest_cache/" in ignore


def test_supported_python_floor_is_311() -> None:
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in config
    assert '"PyYAML>=6.0,<7"' in config
