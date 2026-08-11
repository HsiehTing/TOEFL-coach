# Bug Capture CLI contract

Run from the repository root:

```text
python3 tools/capture_bug_report.py \
  --format json \
  --title "..." \
  --purpose "..." \
  --expected "..." \
  --observed "..." \
  --step "..." \
  --affected-flow "..." \
  --timing "..." \
  --attach path/to/log-or-screenshot
```

Required fields are `--title`, `--purpose`, `--expected`, `--observed`, and one or more `--step` values. Include `--affected-flow`, `--timing`, `--reproducibility`, and `--impact` whenever known. `--attach` may be repeated. Attachments are copied into the report and recorded with SHA-256 checksums.

The command accepts only small text/log/structured-data or image attachments. It rejects raw audio, credentials, keys, suspicious filenames, and files larger than 10 MiB before creating a report. Attachment metadata stores filename, relative path, MIME type, size, and SHA-256, not the original absolute path.

The command creates `tracker/bug-reports/BUG-YYYYMMDD-NNN/` with:

- `report.yaml`: reported facts and attachment manifest.
- `snapshot.json`: capture time, runtime, Git revision, branch, and worktree status.
- `reproduction.md`: readable reproduction record.
- `attachments/`: optional explicit evidence copies.
- `.ready`: SHA-256 of `report.yaml`; indicates a complete initial artifact that recovery may link.

After any successful capture, run:

```text
python3 tools/verify_bug_reports.py --format json
```

If a capture publishes the artifact but cannot update the roadmap ledger, run:

```text
python3 tools/recover_bug_reports.py
python3 tools/verify_bug_reports.py
```

Recovery only links complete `.ready` reports that have no ledger row. Do not edit the ledger manually.

After investigation, append (never overwrite) a closure record. `fixed_verified` additionally requires `--fix-reference`:

```text
python3 tools/resolve_bug_report.py \
  --bug-id BUG-YYYYMMDD-NNN \
  --outcome fixed_verified \
  --diagnosis "..." \
  --fix-reference <commit-or-pr> \
  --validation-command "..." \
  --validation-result "passed"
```

The roadmap status is derived from the latest immutable resolution evidence. To create a compact, privacy-safe operations view, run `python3 tools/rebuild_bug_report_index.py`; it never copies logs, screenshots, or learner content.

Use both `--include-git-diff` and `--confirm-safe-git-diff` only after checking that the diff is necessary and safe to retain. Together they add unstaged and staged diffs to `snapshot.json`; retaining a diff is intentionally double opt-in.
