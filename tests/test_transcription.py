import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from toefl_tracker.audio import AudioInspectionError
from toefl_tracker.quality import quality_decision
from toefl_tracker.transcription import preflight_audio_tools, transcribe_audio


class DependencyProbe:
    def __init__(self, tmp_path: Path) -> None:
        self.model = tmp_path / "outside-repository" / "ggml-small.en.bin"
        self.model.parent.mkdir()
        self.model.write_bytes(b"model fixture")
        self.executables = {
            "ffmpeg": "/usr/local/bin/ffmpeg",
            "ffprobe": "/usr/local/bin/ffprobe",
            "whisper-cli": "/usr/local/bin/whisper-cli",
        }
        self.environ = {"TOEFL_WHISPER_MODEL": str(self.model)}

    def which(self, executable: str) -> str | None:
        return self.executables.get(executable)

    def remove(self, name: str) -> None:
        if name == "model":
            self.model.unlink()
        else:
            self.executables.pop(name)


@pytest.fixture
def dependency_probe(tmp_path: Path) -> DependencyProbe:
    return DependencyProbe(tmp_path)


@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe", "whisper-cli", "model"])
def test_preflight_names_each_missing_dependency(missing: str, dependency_probe: DependencyProbe) -> None:
    dependency_probe.remove(missing)

    with pytest.raises(AudioInspectionError, match=missing):
        preflight_audio_tools(which=dependency_probe.which, environ=dependency_probe.environ)


def test_preflight_rejects_wrong_or_repository_model(
    tmp_path: Path, dependency_probe: DependencyProbe
) -> None:
    wrong_name = tmp_path / "outside-repository" / "other.bin"
    wrong_name.write_bytes(b"model fixture")
    dependency_probe.environ["TOEFL_WHISPER_MODEL"] = str(wrong_name)
    with pytest.raises(AudioInspectionError, match="ggml-small.en.bin"):
        preflight_audio_tools(which=dependency_probe.which, environ=dependency_probe.environ)

    repository_model = tmp_path / "models" / "ggml-small.en.bin"
    repository_model.parent.mkdir()
    repository_model.write_bytes(b"model fixture")
    dependency_probe.environ["TOEFL_WHISPER_MODEL"] = str(repository_model)
    with pytest.raises(AudioInspectionError, match="outside the repository"):
        preflight_audio_tools(
            model_path=repository_model,
            which=dependency_probe.which,
            environ=dependency_probe.environ,
            repository_root=tmp_path,
        )


def test_transcription_normalizes_to_wav_and_cleans_temporary_files(
    tmp_path: Path, dependency_probe: DependencyProbe
) -> None:
    audio = tmp_path / "input.m4a"
    audio.write_bytes(b"fixture")
    dependencies = preflight_audio_tools(which=dependency_probe.which, environ=dependency_probe.environ)
    temporary_files: list[Path] = []
    commands: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        commands.append(command)
        if command[0] == "/usr/local/bin/ffmpeg":
            temporary_files.append(Path(command[-1]))
            return CompletedProcess(command, 0, "", "")
        if command[0] == "/usr/local/bin/whisper-cli":
            output_prefix = Path(command[command.index("-of") + 1])
            output_json = output_prefix.with_suffix(".json")
            temporary_files.append(output_json)
            output_json.write_text(
                json.dumps({"transcription": [{"offsets": {"from": 0, "to": 3800}, "text": " Please describe a place. "}]}),
                encoding="utf-8",
            )
            return CompletedProcess(command, 0, "", "")
        raise AssertionError(f"unexpected executable: {command[0]}")

    rows = transcribe_audio(audio, dependencies, runner=runner)

    assert rows == [{"start": 0.0, "end": 3.8, "text": "Please describe a place."}]
    assert all(not path.exists() for path in temporary_files)
    assert [command[0] for command in commands] == ["/usr/local/bin/ffmpeg", "/usr/local/bin/whisper-cli"]
    assert commands[0][1:] == [
        "-nostdin", "-y", "-i", str(audio), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", commands[0][-1],
    ]
    assert commands[1][1:5] == ["-m", str(dependencies.model_path), "-f", commands[0][-1]]
    assert commands[1][-2:] == ["-of", str(Path(commands[0][-1]).parent / "output")]


def test_transcription_rejects_malformed_whisper_segments(
    tmp_path: Path, dependency_probe: DependencyProbe
) -> None:
    audio = tmp_path / "input.m4a"
    audio.write_bytes(b"fixture")
    dependencies = preflight_audio_tools(which=dependency_probe.which, environ=dependency_probe.environ)

    def runner(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if command[0] == "/usr/local/bin/ffmpeg":
            return CompletedProcess(command, 0, "", "")
        output_prefix = Path(command[command.index("-of") + 1])
        output_prefix.with_suffix(".json").write_text('{"transcription": [{"text": "missing offsets"}]}')
        return CompletedProcess(command, 0, "", "")

    with pytest.raises(AudioInspectionError, match="whisper JSON"):
        transcribe_audio(audio, dependencies, runner=runner)


def test_provenance_contains_identifiers_but_not_local_paths(
    dependency_probe: DependencyProbe,
) -> None:
    dependencies = preflight_audio_tools(which=dependency_probe.which, environ=dependency_probe.environ)

    provenance = dependencies.provenance

    assert provenance["model_identifier"] == "ggml-small.en.bin"
    assert set(provenance["executables"]) == {"ffmpeg", "ffprobe", "whisper-cli"}
    rendered = json.dumps(provenance)
    assert str(dependency_probe.model) not in rendered
    assert "/usr/local/bin" not in rendered


def test_preflight_keeps_reported_tool_version_when_version_command_exits_nonzero(
    dependency_probe: DependencyProbe,
) -> None:
    def version_runner(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        executable = Path(command[0]).name
        return CompletedProcess(command, 8, f"{executable} version 8.1.2\n", "")

    dependencies = preflight_audio_tools(
        which=dependency_probe.which,
        environ=dependency_probe.environ,
        runner=version_runner,
    )

    assert dependencies.provenance["executables"]["ffmpeg"] == "ffmpeg version 8.1.2"


@pytest.mark.parametrize(("mean", "peak", "usable", "dimensions"), [
    (-30.0, -5.0, True, "all"),
    (-36.0, -10.0, True, "text_only"),
    (-30.0, -21.0, True, "text_only"),
    (-46.0, -10.0, False, "none"),
    (-30.0, -35.0, False, "none"),
    (-30.0, -0.1, False, "none"),
])
def test_quality_policy_boundaries(
    mean: float, peak: float, usable: bool, dimensions: str
) -> None:
    decision = quality_decision({"mean_dbfs": mean, "peak_dbfs": peak})

    assert (decision.usable, decision.dimension_set) == (usable, dimensions)
    assert decision.policy_version == 1


def test_quality_policy_is_versioned_diagnostic_internal() -> None:
    decision = quality_decision({"mean_dbfs": -30.0, "peak_dbfs": -5.0})

    assert decision.standard_basis == "diagnostic_internal"
