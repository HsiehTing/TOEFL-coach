"""Immutable, reproducible bug-capture artifacts for the coaching system."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from toefl_tracker.io import atomic_write_text
from toefl_tracker.models import ValidationError


_LEDGER_MARKER = "<!-- BUG-CAPTURE-LEDGER -->"
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
_SAFE_ATTACHMENT_SUFFIXES = {
    ".txt", ".log", ".md", ".json", ".yaml", ".yml", ".csv",
    ".png", ".jpg", ".jpeg", ".webp",
}
_DENIED_ATTACHMENT_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".pem", ".key", ".p12", ".pfx"}
_DENIED_ATTACHMENT_NAMES = {".env", "id_rsa", "id_ed25519", "credentials", "credentials.json"}
_RESOLUTION_OUTCOMES = {"fixed_verified", "duplicate", "cannot_reproduce", "wont_fix"}


@contextmanager
def _capture_lock(root: Path):
    """Serialize ID allocation and ledger writes for bug-capture records."""
    reports = root / "tracker/bug-reports"
    reports.mkdir(parents=True, exist_ok=True)
    lock = reports / ".capture.lock"
    with lock.open("a+b") as handle:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            if not handle.read(1):
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _required_text(value: str | None, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"bug capture {field} must be a non-empty string")
    return value.strip()


def _utc_now(reported_at: datetime | None) -> datetime:
    value = reported_at or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValidationError("bug capture reported_at must include a timezone")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _run_git(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode:
        return None
    return result.stdout.rstrip("\n")


def _repository_snapshot(root: Path, *, include_git_diff: bool) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "repository_identity": "sha256:" + hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest(),
        "branch": _run_git(root, "branch", "--show-current"),
        "head": _run_git(root, "rev-parse", "HEAD"),
        "status_porcelain": (_run_git(root, "status", "--porcelain=v1") or "").splitlines(),
    }
    if include_git_diff:
        snapshot["working_diff"] = _run_git(root, "diff", "--binary") or ""
        snapshot["staged_diff"] = _run_git(root, "diff", "--binary", "--cached") or ""
    return snapshot


def _next_bug_id(root: Path, day: str) -> str:
    reports = root / "tracker/bug-reports"
    prefix = f"BUG-{day}-"
    suffixes = [
        int(path.name.removeprefix(prefix))
        for path in reports.glob(f"{prefix}*")
        if path.is_dir() and path.name.removeprefix(prefix).isdigit()
    ]
    return f"{prefix}{max(suffixes, default=0) + 1:03d}"


def _copy_attachments(destination: Path, attachments: Iterable[Path]) -> list[dict[str, Any]]:
    copied: list[dict[str, str]] = []
    seen: set[Path] = set()
    destination.mkdir(parents=True, exist_ok=True)
    for source in attachments:
        resolved = source.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.is_file():
            raise ValidationError(f"bug capture attachment is not a file: {source}")
        name = resolved.name
        target = destination / name
        suffix = 2
        while target.exists():
            target = destination / f"{resolved.stem}-{suffix}{resolved.suffix}"
            suffix += 1
        shutil.copy2(resolved, target)
        copied.append(
            {
                "original_name": resolved.name,
                "stored_path": str(target.relative_to(destination.parent)),
                "size_bytes": target.stat().st_size,
                "mime_type": mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    return copied


def _validate_attachments(attachments: Iterable[Path]) -> list[Path]:
    """Resolve all attachments before a new immutable report directory is made."""
    resolved: list[Path] = []
    seen: set[Path] = set()
    for source in attachments:
        path = source.resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            raise ValidationError(f"bug capture attachment is not a file: {source}")
        name = path.name.lower()
        if (
            path.suffix.lower() not in _SAFE_ATTACHMENT_SUFFIXES
            or path.suffix.lower() in _DENIED_ATTACHMENT_SUFFIXES
            or name in _DENIED_ATTACHMENT_NAMES
            or any(token in name for token in ("credential", "secret", "token", "password"))
        ):
            raise ValidationError("bug capture attachment type is not allowed")
        if path.stat().st_size > _MAX_ATTACHMENT_BYTES:
            raise ValidationError("bug capture attachment exceeds the size limit")
        resolved.append(path)
    return resolved


def _reproduction_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['bug_id']} — {report['title']}",
        "",
        f"Status: `{report['status']}`",
        f"Reported at: `{report['reported_at']}`",
        f"Intended purpose: {report['purpose']}",
        f"Affected flow: {report.get('affected_flow') or 'not specified'}",
        f"Timing / trigger: {report.get('timing') or 'not specified'}",
        f"Reproducibility: {report.get('reproducibility') or 'not specified'}",
        f"Impact: {report.get('impact') or 'not specified'}",
        "",
        "## Expected behavior",
        "",
        report["expected"],
        "",
        "## Observed behavior",
        "",
        report["observed"],
        "",
        "## Steps immediately before the failure",
        "",
    ]
    lines.extend(f"{number}. {step}" for number, step in enumerate(report["steps"], start=1))
    lines.extend([
        "",
        "## Captured evidence",
        "",
        "- `snapshot.json` records repository revision, worktree state, runtime, and capture time.",
        "- `attachments/` contains user-supplied logs, screenshots, or artifacts with SHA-256 checksums.",
        "- The roadmap ledger links this Bug ID; fix work must consult this artifact before changing behavior.",
        "",
    ])
    return "\n".join(lines)


def _ledger_bug_ids(text: str) -> set[str]:
    return {
        line.split("`")[1]
        for line in text.splitlines()
        if line.startswith("| `BUG-") and line.count("`") >= 2
    }


def _report_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _append_to_roadmap(roadmap: Path, report: dict[str, Any], report_digest: str) -> None:
    text = roadmap.read_text(encoding="utf-8")
    if _LEDGER_MARKER not in text:
        raise ValidationError("roadmap is missing the bug-capture ledger marker")
    if report["bug_id"] in _ledger_bug_ids(text):
        raise ValidationError(f"roadmap already links bug capture: {report['bug_id']}")
    artifact = (Path("tracker/bug-reports") / report["bug_id"] / "reproduction.md").as_posix()
    title = report["title"].replace("|", "\\|").replace("\n", " ")
    row = (
        f"| `{report['bug_id']}` | reported | {title} | [reproduction]({artifact}) | "
        f"`v{report['schema_version']}` `{report_digest}` |\n"
    )
    atomic_write_text(roadmap, text.replace(_LEDGER_MARKER, _LEDGER_MARKER + "\n" + row, 1))


def _ready_report(directory: Path) -> tuple[dict[str, Any], str] | None:
    report_path = directory / "report.yaml"
    required = (report_path, directory / "snapshot.json", directory / "reproduction.md", directory / ".ready")
    if not directory.is_dir() or not all(path.is_file() for path in required):
        return None
    try:
        report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
        marker = (directory / ".ready").read_text(encoding="utf-8").strip()
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(report, dict) or report.get("bug_id") != directory.name:
        return None
    digest = _report_digest(report_path)
    if marker != digest:
        return None
    return report, digest


def _report_directory(root: Path, bug_id: str) -> tuple[Path, dict[str, Any], str]:
    if not isinstance(bug_id, str) or not bug_id.startswith("BUG-"):
        raise ValidationError("bug resolution requires a valid Bug ID")
    directory = root / "tracker/bug-reports" / bug_id
    ready = _ready_report(directory)
    if ready is None:
        raise ValidationError("bug resolution requires a complete captured report")
    report, digest = ready
    return directory, report, digest


def _resolution_rows(directory: Path) -> list[tuple[Path, dict[str, Any]]]:
    folder = directory / "resolutions"
    rows: list[tuple[Path, dict[str, Any]]] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.glob("RES-*.yaml")):
        try:
            row = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(row, dict):
            rows.append((path, row))
    return rows


def _latest_resolution(directory: Path) -> dict[str, Any] | None:
    rows = _resolution_rows(directory)
    if not rows:
        return None
    return max((row for _, row in rows), key=lambda row: (str(row.get("recorded_at", "")), str(row.get("resolution_id", ""))))


def _set_ledger_status(roadmap: Path, bug_id: str, status: str) -> None:
    text = roadmap.read_text(encoding="utf-8")
    pattern = rf"(?m)^(\| `{re.escape(bug_id)}` \| )[^|]+( \|)"
    updated, count = re.subn(pattern, rf"\g<1>{status}\g<2>", text)
    if count != 1:
        raise ValidationError("bug resolution requires exactly one roadmap ledger entry")
    atomic_write_text(roadmap, updated)


def bug_capture_receipt(root: Path, report_dir: Path, *, roadmap: Path | None = None) -> dict[str, Any]:
    """Return a stable machine-readable receipt for a captured record."""
    root = root.resolve()
    directory = report_dir.resolve()
    ready = _ready_report(directory)
    if ready is None:
        raise ValidationError("bug capture receipt requires a complete report")
    report, digest = ready
    problems = verify_bug_reports(root, roadmap=roadmap)
    return {
        "bug_id": report["bug_id"],
        "report_path": str(directory.relative_to(root)),
        "schema_version": report["schema_version"],
        "ledger_path": str((roadmap or root / "docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md").resolve().relative_to(root)),
        "attachment_count": len(report["attachments"]),
        "privacy_flags": {"git_diff_retained": "working_diff" in json.loads((directory / "snapshot.json").read_text(encoding="utf-8"))["repository"]},
        "report_digest": digest,
        "validation": {"passed": not problems, "problems": problems},
    }


def append_bug_resolution(
    root: Path,
    *,
    bug_id: str,
    outcome: str,
    diagnosis: str,
    validation_command: str,
    validation_result: str,
    fix_reference: str | None = None,
    recorded_at: datetime | None = None,
    roadmap: Path | None = None,
) -> Path:
    """Append immutable closure evidence and refresh only its derived ledger status."""
    root = root.resolve()
    if outcome not in _RESOLUTION_OUTCOMES:
        raise ValidationError("bug resolution outcome is invalid")
    if outcome == "fixed_verified" and not isinstance(fix_reference, str):
        raise ValidationError("fixed_verified resolution requires a fix reference")
    timestamp = _utc_now(recorded_at)
    roadmap = (roadmap or root / "docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md").resolve()
    if not roadmap.is_file() or _LEDGER_MARKER not in roadmap.read_text(encoding="utf-8"):
        raise ValidationError("bug resolution requires the configured roadmap and its ledger marker")
    with _capture_lock(root):
        directory, report, digest = _report_directory(root, bug_id)
        if bug_id not in _ledger_bug_ids(roadmap.read_text(encoding="utf-8")):
            raise ValidationError("bug resolution requires a captured roadmap ledger entry")
        resolutions = directory / "resolutions"
        resolutions.mkdir(exist_ok=True)
        number = len(list(resolutions.glob("RES-*.yaml"))) + 1
        resolution_id = f"RES-{number:03d}"
        resolution = {
            "schema_version": 1,
            "resolution_id": resolution_id,
            "bug_id": report["bug_id"],
            "recorded_at": timestamp.isoformat(),
            "outcome": outcome,
            "diagnosis": _required_text(diagnosis, "diagnosis"),
            "fix_reference": _required_text(fix_reference, "fix reference") if fix_reference is not None else None,
            "validation_command": _required_text(validation_command, "validation command"),
            "validation_result": _required_text(validation_result, "validation result"),
            "initial_report_digest": digest,
        }
        path = resolutions / f"{resolution_id}.yaml"
        atomic_write_text(path, yaml.safe_dump(resolution, allow_unicode=True, sort_keys=False))
        _set_ledger_status(roadmap, bug_id, outcome)
        return path


def build_bug_index(root: Path, *, roadmap: Path | None = None) -> dict[str, Any]:
    """Build a privacy-safe operational view from immutable reports and resolutions."""
    root = root.resolve()
    reports = root / "tracker/bug-reports"
    rows: list[dict[str, Any]] = []
    if reports.is_dir():
        for directory in sorted(path for path in reports.glob("BUG-*") if path.is_dir()):
            ready = _ready_report(directory)
            if ready is None:
                continue
            report, _ = ready
            resolution = _latest_resolution(directory)
            rows.append({
                "bug_id": report["bug_id"],
                "status": resolution["outcome"] if resolution else "reported",
                "affected_flow": report.get("affected_flow") or "unspecified",
                "reproducibility": report.get("reproducibility") or "unknown",
                "artifact_complete": not any(
                    problem.endswith(f": {report['bug_id']}") for problem in verify_bug_reports(root, roadmap=roadmap)
                ),
            })
    statuses: dict[str, int] = {}
    flows: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        flows[row["affected_flow"]] = flows.get(row["affected_flow"], 0) + 1
    return {"schema_version": 1, "reports": rows, "by_status": statuses, "by_affected_flow": flows}


def write_bug_index(root: Path, *, roadmap: Path | None = None) -> Path:
    """Write a derived index without copying transcripts, logs, or screenshots."""
    index = build_bug_index(root, roadmap=roadmap)
    destination = root / "tracker/bug-reports/index.yaml"
    atomic_write_text(destination, yaml.safe_dump(index, allow_unicode=True, sort_keys=False))
    return destination


def capture_bug_report(
    root: Path,
    *,
    title: str,
    purpose: str,
    expected: str,
    observed: str,
    steps: Iterable[str],
    affected_flow: str | None = None,
    timing: str | None = None,
    reproducibility: str | None = None,
    impact: str | None = None,
    attachments: Iterable[Path] = (),
    include_git_diff: bool = False,
    confirm_safe_git_diff: bool = False,
    reported_at: datetime | None = None,
    roadmap: Path | None = None,
    failpoint: Callable[[str], None] | None = None,
) -> Path:
    """Persist a bug's reproduction context, then add its ID to the single roadmap."""
    root = root.resolve()
    if not root.is_dir():
        raise ValidationError("bug capture root must be an existing directory")
    if include_git_diff and not confirm_safe_git_diff:
        raise ValidationError("bug capture requires explicit confirmation before retaining a git diff")
    captured_at = _utc_now(reported_at)
    clean_steps = [_required_text(step, "step") for step in steps]
    if not clean_steps:
        raise ValidationError("bug capture requires at least one reproduction step")
    roadmap = (roadmap or root / "docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md").resolve()
    if not roadmap.is_file() or _LEDGER_MARKER not in roadmap.read_text(encoding="utf-8"):
        raise ValidationError("bug capture requires the configured roadmap and its ledger marker")
    attachment_paths = _validate_attachments(attachments)
    reports = root / "tracker/bug-reports"
    with _capture_lock(root):
        bug_id = _next_bug_id(root, captured_at.strftime("%Y%m%d"))
        report_dir = reports / bug_id
        staging_root = reports / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f"{bug_id}.", dir=staging_root))
        published = False
        try:
            attachment_rows = _copy_attachments(staging / "attachments", attachment_paths)
            report = {
                "schema_version": 1,
                "bug_id": bug_id,
                "status": "reported",
                "reported_at": captured_at.isoformat(),
                "title": _required_text(title, "title"),
                "purpose": _required_text(purpose, "purpose"),
                "affected_flow": affected_flow.strip() if isinstance(affected_flow, str) and affected_flow.strip() else None,
                "timing": timing.strip() if isinstance(timing, str) and timing.strip() else None,
                "reproducibility": reproducibility.strip() if isinstance(reproducibility, str) and reproducibility.strip() else None,
                "impact": impact.strip() if isinstance(impact, str) and impact.strip() else None,
                "expected": _required_text(expected, "expected"),
                "observed": _required_text(observed, "observed"),
                "steps": clean_steps,
                "attachments": attachment_rows,
            }
            snapshot = {
                "schema_version": 1,
                "captured_at": captured_at.isoformat(),
                "runtime": {
                    "python": sys.version.split()[0],
                    "platform": platform.platform(),
                },
                "repository": _repository_snapshot(root, include_git_diff=include_git_diff),
                "attachment_checksums": attachment_rows,
            }
            atomic_write_text(staging / "report.yaml", yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
            atomic_write_text(staging / "snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
            atomic_write_text(staging / "reproduction.md", _reproduction_markdown(report))
            digest = _report_digest(staging / "report.yaml")
            atomic_write_text(staging / ".ready", digest + "\n")
            if failpoint is not None:
                failpoint("after_staging")
            staging.rename(report_dir)
            published = True
            if failpoint is not None:
                failpoint("after_publish")
            _append_to_roadmap(roadmap, report, digest)
            return report_dir
        finally:
            if not published and staging.exists():
                shutil.rmtree(staging)


def recover_bug_reports(root: Path, *, roadmap: Path | None = None) -> list[Path]:
    """Link complete, ready reports that a prior capture published but did not ledger."""
    root = root.resolve()
    roadmap = (roadmap or root / "docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md").resolve()
    if not roadmap.is_file() or _LEDGER_MARKER not in roadmap.read_text(encoding="utf-8"):
        raise ValidationError("bug capture recovery requires the configured roadmap and its ledger marker")
    linked: list[Path] = []
    with _capture_lock(root):
        existing = _ledger_bug_ids(roadmap.read_text(encoding="utf-8"))
        reports = root / "tracker/bug-reports"
        for directory in sorted(path for path in reports.glob("BUG-*") if path.is_dir()):
            ready = _ready_report(directory)
            if ready is None or directory.name in existing:
                continue
            report, digest = ready
            _append_to_roadmap(roadmap, report, digest)
            existing.add(directory.name)
            linked.append(directory)
    return linked


def verify_bug_reports(root: Path, *, roadmap: Path | None = None) -> list[str]:
    """Report broken Bug Capture links without changing any artifact or ledger."""
    root = root.resolve()
    roadmap = (roadmap or root / "docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md").resolve()
    if not roadmap.is_file() or _LEDGER_MARKER not in roadmap.read_text(encoding="utf-8"):
        return ["configured roadmap is missing the bug-capture ledger marker"]
    ledger_lines = {
        line.split("`")[1]: line
        for line in roadmap.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `BUG-") and line.count("`") >= 2
    }
    reports = root / "tracker/bug-reports"
    problems: list[str] = []
    ready_ids: set[str] = set()
    if reports.exists():
        for staging in sorted(path for path in (reports / ".staging").glob("*") if path.is_dir()) if (reports / ".staging").exists() else []:
            problems.append(f"incomplete staging artifact: {staging.name}")
        for directory in sorted(path for path in reports.glob("BUG-*") if path.is_dir()):
            ready = _ready_report(directory)
            if ready is None:
                problems.append(f"invalid or incomplete report artifact: {directory.name}")
                continue
            report, digest = ready
            ready_ids.add(directory.name)
            line = ledger_lines.get(directory.name)
            if line is None:
                problems.append(f"ready report is missing a roadmap link: {directory.name}")
            elif digest not in line:
                problems.append(f"roadmap artifact hash does not match report: {directory.name}")
            elif f"`v{report.get('schema_version')}`" not in line:
                problems.append(f"roadmap schema version does not match report: {directory.name}")
            resolution_rows = _resolution_rows(directory)
            resolution_ids: set[str] = set()
            for path, resolution in resolution_rows:
                resolution_id = resolution.get("resolution_id")
                if (
                    resolution.get("schema_version") != 1
                    or not isinstance(resolution_id, str)
                    or resolution_id in resolution_ids
                    or resolution.get("bug_id") != directory.name
                    or resolution.get("outcome") not in _RESOLUTION_OUTCOMES
                    or resolution.get("initial_report_digest") != digest
                    or any(not isinstance(resolution.get(field), str) or not resolution[field].strip() for field in ("diagnosis", "validation_command", "validation_result", "recorded_at"))
                    or (resolution.get("outcome") == "fixed_verified" and not isinstance(resolution.get("fix_reference"), str))
                ):
                    problems.append(f"invalid resolution evidence: {directory.name}/{path.name}")
                resolution_ids.add(str(resolution_id))
            expected_status = _latest_resolution(directory)
            expected_status = expected_status["outcome"] if expected_status else "reported"
            if line is not None and f"| {expected_status} |" not in line:
                problems.append(f"roadmap status does not match resolution evidence: {directory.name}")
    for bug_id in ledger_lines:
        if bug_id not in ready_ids:
            problems.append(f"roadmap links a missing or incomplete report: {bug_id}")
    return sorted(problems)
