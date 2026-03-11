#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_ROOT = "/data/raw"
DEFAULT_TARGET_ROOT = "/mnt/nextgen2/archive/raw"
DEFAULT_RETENTION_DAYS = 90
DEFAULT_MANIFEST_DIR = "/data/raw/.archive_manifests"
DEFAULT_INSTRUMENTS = [
    "miseq1_M00818",
    "miseq2_M04404",
    "miseq3_M00403",
    "nextseq500_NB501289",
    "novaseq_A01742",
]
RUN_PREFIX_RE = re.compile(r"^(?P<prefix>\d{6})_")
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _style(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _title(text: str) -> str:
    return _style(text, "1;36")


def _ok(text: str) -> str:
    return _style(text, "1;32")


def _warn(text: str) -> str:
    return _style(text, "1;33")


def _err(text: str) -> str:
    return _style(text, "1;31")


def _cmd(text: str) -> str:
    return _style(text, "36")


def _dim(text: str) -> str:
    return _style(text, "2")


@dataclass
class RunCandidate:
    instrument: str
    run_id: str
    run_date: date
    source_path: Path
    target_instrument_path: Path
    target_run_path: Path
    size_bytes: int


def load_ctx() -> dict[str, Any]:
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


def _format_bytes(num_bytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def _parse_run_date(run_id: str) -> date | None:
    match = RUN_PREFIX_RE.match(run_id)
    if not match:
        return None
    prefix = match.group("prefix")
    try:
        yy = int(prefix[0:2])
        mm = int(prefix[2:4])
        dd = int(prefix[4:6])
        return date(2000 + yy, mm, dd)
    except ValueError:
        return None


def _du_size_bytes(path: Path) -> int:
    result = subprocess.run(
        ["du", "-sb", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    first = result.stdout.strip().split()[0]
    return int(first)


def _compute_cutoff(retention_days: int) -> date:
    return date.today() - timedelta(days=retention_days)


def _discover_candidates(
    source_root: Path,
    target_root: Path,
    instruments: list[str],
    retention_days: int,
    skip_runs: set[str],
) -> tuple[list[RunCandidate], list[str]]:
    issues: list[str] = []
    cutoff = _compute_cutoff(retention_days)
    candidates: list[RunCandidate] = []

    for instrument in instruments:
        src_instrument = source_root / instrument
        dst_instrument = target_root / instrument

        if not src_instrument.exists() or not src_instrument.is_dir():
            issues.append(f"Missing source instrument directory: {src_instrument}")
            continue

        for entry in sorted(src_instrument.iterdir()):
            if not entry.is_dir():
                continue
            run_date = _parse_run_date(entry.name)
            if run_date is None:
                continue
            if run_date >= cutoff:
                continue
            if entry.name in skip_runs:
                continue
            try:
                size_bytes = _du_size_bytes(entry)
            except Exception as exc:  # noqa: BLE001
                issues.append(f"Failed to calculate size for {entry}: {exc}")
                continue

            candidates.append(
                RunCandidate(
                    instrument=instrument,
                    run_id=entry.name,
                    run_date=run_date,
                    source_path=entry,
                    target_instrument_path=dst_instrument,
                    target_run_path=dst_instrument / entry.name,
                    size_bytes=size_bytes,
                )
            )

    candidates.sort(key=lambda c: (c.instrument, c.run_date, c.run_id))
    return candidates, issues


def _print_section(title: str) -> None:
    print("\n" + _title("=" * 80))
    print(_title(title))
    print(_title("=" * 80))


def _print_plan(candidates: list[RunCandidate], retention_days: int, skip_runs: set[str]) -> None:
    cutoff = _compute_cutoff(retention_days)
    _print_section("Archive Plan")
    print(f"Retention days: {retention_days}")
    print(f"Archive runs older than: {cutoff.isoformat()} (strictly before this date)")
    print(f"Runs skipped by user: {', '.join(sorted(skip_runs)) if skip_runs else '(none)'}")

    if not candidates:
        print("\nNo run directories match the archive criteria.")
        return

    print("\nSelected runs:")
    for idx, item in enumerate(candidates, start=1):
        print(
            f"{_dim(f'{idx:>3}.')} {item.instrument:<24} {item.run_id:<34} "
            f"{_format_bytes(item.size_bytes):>10}"
        )

    total = sum(c.size_bytes for c in candidates)
    print("\nSummary:")
    print(_ok(f"- Run count: {len(candidates)}"))
    print(_ok(f"- Total size: {_format_bytes(total)}"))


def _input_with_default(prompt: str, default: str) -> str:
    answer = input(_title(f"{prompt} [{default}]: ")).strip()
    return answer or default


def _input_yes_no(prompt: str, default_yes: bool = False) -> bool:
    suffix = "Y/n" if default_yes else "y/N"
    answer = input(_title(f"{prompt} [{suffix}]: ")).strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}


def _interactive_overrides(
    source_root: str,
    target_root: str,
    retention_days: int,
    instruments: list[str],
    skip_runs: set[str],
) -> tuple[str, str, int, list[str], set[str]]:
    _print_section("archive_rawdata Interactive Setup")
    print(_dim("Press Enter to keep defaults."))

    source_root = _input_with_default("Source root", source_root)
    target_root = _input_with_default("Target root", target_root)

    retention_raw = _input_with_default("Retention days", str(retention_days))
    try:
        retention_days = int(retention_raw)
    except ValueError:
        raise SystemExit(f"Invalid retention days: {retention_raw}")

    inst_default = ",".join(instruments)
    inst_raw = _input_with_default("Instrument folders (comma-separated)", inst_default)
    instruments = [v for v in _split_csv(inst_raw) if v]
    if not instruments:
        raise SystemExit("No instrument folders provided.")

    skip_default = ",".join(sorted(skip_runs))
    skip_raw = _input_with_default("Skip run IDs (comma-separated; optional)", skip_default)
    skip_runs = set(_split_csv(skip_raw))

    return source_root, target_root, retention_days, instruments, skip_runs


def _prompt_additional_skips(candidates: list[RunCandidate], skip_runs: set[str]) -> set[str]:
    if not candidates:
        return skip_runs
    print("\n" + _title("Optional: enter additional run IDs to skip from this plan."))
    entered = input(_title("Additional skips (comma-separated, or Enter for none): ")).strip()
    if not entered:
        return skip_runs

    planned_ids = {c.run_id for c in candidates}
    for run_id in _split_csv(entered):
        if run_id in planned_ids:
            skip_runs.add(run_id)
        else:
            print(_warn(f"[warning] Run ID not in current plan, ignored: {run_id}"))
    return skip_runs


def _ensure_target_free_space(target_root: Path, required_bytes: int, min_free_gb: int) -> None:
    usage = shutil.disk_usage(target_root)
    free_bytes = usage.free
    min_free_bytes = min_free_gb * 1024 * 1024 * 1024
    if free_bytes < min_free_bytes:
        raise SystemExit(
            f"Insufficient free space on {target_root}: {_format_bytes(free_bytes)} free, "
            f"requires at least {_format_bytes(min_free_bytes)}"
        )
    if required_bytes > free_bytes:
        raise SystemExit(
            f"Insufficient free space on {target_root}: need {_format_bytes(required_bytes)}, "
            f"but only {_format_bytes(free_bytes)} free"
        )


def _assert_writable_dir(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"Target directory missing or not a directory: {path}")
    if not os.access(path, os.W_OK | os.X_OK):
        raise SystemExit(f"No write permission for target directory: {path}")
    try:
        with tempfile.NamedTemporaryFile(prefix=".archive_rawdata_write_test_", dir=path, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Cannot write to target directory {path}: {exc}") from exc


def _preflight_target_paths(target_root: Path, candidates: list[RunCandidate]) -> None:
    _assert_writable_dir(target_root)
    seen: set[Path] = set()
    for candidate in candidates:
        instrument_dir = candidate.target_instrument_path
        if instrument_dir in seen:
            continue
        if not instrument_dir.exists():
            try:
                instrument_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"Failed to create target instrument directory {instrument_dir}: {exc}") from exc
        _assert_writable_dir(instrument_dir)
        seen.add(instrument_dir)


def _run_cmd(cmd: list[str]) -> None:
    print(_cmd("+ " + " ".join(cmd)))
    subprocess.run(cmd, check=True)


def _rsync_copy(candidate: RunCandidate) -> None:
    candidate.target_instrument_path.mkdir(parents=True, exist_ok=True)
    _run_cmd(
        [
            "rsync",
            "-a",
            "--human-readable",
            "--info=progress2",
            "--no-inc-recursive",
            "--partial",
            str(candidate.source_path),
            str(candidate.target_instrument_path),
        ]
    )


def _rsync_verify(candidate: RunCandidate) -> None:
    verify = subprocess.run(
        [
            "rsync",
            "-avhn",
            "--delete",
            f"{candidate.source_path}/",
            f"{candidate.target_run_path}/",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    lines = [line for line in verify.stdout.splitlines() if line.strip()]
    payload_lines = [line for line in lines if not line.startswith(("sending ", "sent ", "total size is "))]
    if payload_lines:
        raise RuntimeError(
            "Verification mismatch after copy for "
            f"{candidate.run_id}. rsync dry-run reported differences."
        )


def _acquire_lock(lock_path: Path) -> int:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(lock_path), flags)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    return fd


def _release_lock(fd: int, lock_path: Path) -> None:
    os.close(fd)
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _append_log(log_path: Path, message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def _manifest_setup_hint(dir_path: Path) -> str:
    return (
        f"Manifest/log directory is not writable: {dir_path}\n"
        "Choose one of:\n"
        f"1) Create and grant access:\n"
        f"   sudo mkdir -p {dir_path}\n"
        f"   sudo chown root:bioinfo {dir_path}\n"
        f"   sudo chmod 2775 {dir_path}\n"
        "2) Use another writable location:\n"
        "   --manifest-dir /data/shared/archive_manifests\n"
        "   or --manifest-path /data/shared/archive_manifests/<name>.json"
    )


def _preflight_manifest_paths(manifest_path: Path, log_path: Path) -> None:
    for dir_path in (manifest_path.parent, log_path.parent):
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(_manifest_setup_hint(dir_path) + f"\nDetail: {exc}") from exc

        if not os.access(dir_path, os.W_OK | os.X_OK):
            raise SystemExit(_manifest_setup_hint(dir_path))

    try:
        with tempfile.NamedTemporaryFile(prefix=".archive_manifest_write_test_", dir=manifest_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(manifest_path.parent) + f"\nDetail: {exc}") from exc

    try:
        with tempfile.NamedTemporaryFile(prefix=".archive_log_write_test_", dir=log_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(log_path.parent) + f"\nDetail: {exc}") from exc


def _manifest_payload(metadata: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **metadata,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "records": records,
    }


def _write_manifest(manifest_path: Path, metadata: dict[str, Any], records: list[dict[str, Any]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(_manifest_payload(metadata, records), indent=2),
        encoding="utf-8",
    )


def _parse_params() -> dict[str, Any]:
    ctx = load_ctx()
    params = dict(ctx.get("params") or {})

    parser = argparse.ArgumentParser(description="Archive old raw sequencing run folders with rsync.")
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--target-root", default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--instrument-folders", default=",".join(DEFAULT_INSTRUMENTS))
    parser.add_argument("--skip-runs", default="")
    parser.add_argument("--non-interactive", nargs="?", const="true", default="false")
    parser.add_argument("--interactive", nargs="?", const="true", default="true")
    parser.add_argument("--yes", nargs="?", const="true", default="false")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")
    parser.add_argument("--cleanup", nargs="?", const="true", default="false")
    parser.add_argument("--min-free-gb", type=int, default=500)
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)

    if params:
        return params

    args = parser.parse_args()
    return {
        "source_root": args.source_root,
        "target_root": args.target_root,
        "retention_days": args.retention_days,
        "instrument_folders": args.instrument_folders,
        "skip_runs": args.skip_runs,
        "non_interactive": args.non_interactive,
        "interactive": args.interactive,
        "yes": args.yes,
        "dry_run": args.dry_run,
        "cleanup": args.cleanup,
        "min_free_gb": args.min_free_gb,
        "manifest_path": args.manifest_path,
        "manifest_dir": args.manifest_dir,
    }


def main() -> None:
    params = _parse_params()

    source_root = str(params.get("source_root") or DEFAULT_SOURCE_ROOT).strip()
    target_root = str(params.get("target_root") or DEFAULT_TARGET_ROOT).strip()
    retention_days = _parse_int(params.get("retention_days"), DEFAULT_RETENTION_DAYS)
    instruments = _split_csv(params.get("instrument_folders") or ",".join(DEFAULT_INSTRUMENTS))
    if not instruments:
        instruments = list(DEFAULT_INSTRUMENTS)

    skip_runs = set(_split_csv(params.get("skip_runs")))
    non_interactive = _parse_bool(params.get("non_interactive"), False)
    interactive = _parse_bool(params.get("interactive"), True)
    dry_run = _parse_bool(params.get("dry_run"), False)
    cleanup_requested = _parse_bool(params.get("cleanup"), False)
    yes = _parse_bool(params.get("yes"), False)
    min_free_gb = _parse_int(params.get("min_free_gb"), 500)
    manifest_path_raw = str(params.get("manifest_path") or "").strip()
    manifest_dir = Path(str(params.get("manifest_dir") or DEFAULT_MANIFEST_DIR)).expanduser().resolve()

    if retention_days < 0:
        raise SystemExit("retention_days must be >= 0")

    if cleanup_requested:
        print(_warn("[warning] cleanup in archive_rawdata is deprecated and ignored. Use archive_cleanup workflow."))

    if non_interactive:
        interactive = False
        yes = True
        print(_dim("[mode] non_interactive=true -> interactive disabled, global confirmation auto-approved"))

    if interactive and sys.stdin.isatty():
        source_root, target_root, retention_days, instruments, skip_runs = _interactive_overrides(
            source_root,
            target_root,
            retention_days,
            instruments,
            skip_runs,
        )

    source_root_path = Path(source_root).expanduser().resolve()
    target_root_path = Path(target_root).expanduser().resolve()

    if not source_root_path.exists() or not source_root_path.is_dir():
        raise SystemExit(f"Source root not found or not a directory: {source_root_path}")
    if not target_root_path.exists() or not target_root_path.is_dir():
        raise SystemExit(f"Target root not found or not a directory: {target_root_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_manifest_path = manifest_dir / f"archive_rawdata_{timestamp}.json"
    manifest_path = Path(manifest_path_raw).expanduser().resolve() if manifest_path_raw else default_manifest_path
    log_path = manifest_path.parent / f"{manifest_path.stem}.log"

    _print_section("Path Confirmation")
    print(f"Source root: {source_root_path}")
    print(f"Target root: {target_root_path}")
    print(f"Instrument folders: {', '.join(instruments)}")
    print(f"Manifest path: {manifest_path}")
    print(f"Log path: {log_path}")

    # Fail fast before expensive discovery/copy if manifest/log location is not writable.
    _preflight_manifest_paths(manifest_path, log_path)

    candidates, issues = _discover_candidates(
        source_root=source_root_path,
        target_root=target_root_path,
        instruments=instruments,
        retention_days=retention_days,
        skip_runs=skip_runs,
    )

    if issues:
        _print_section("Discovery Notes")
        for issue in issues:
            print(_warn(f"- {issue}"))

    if interactive and sys.stdin.isatty():
        _print_plan(candidates, retention_days, skip_runs)
        skip_runs = _prompt_additional_skips(candidates, skip_runs)
        candidates, issues2 = _discover_candidates(
            source_root=source_root_path,
            target_root=target_root_path,
            instruments=instruments,
            retention_days=retention_days,
            skip_runs=skip_runs,
        )
        if issues2:
            _print_section("Discovery Notes (After Skip Updates)")
            for issue in issues2:
                print(_warn(f"- {issue}"))

    _print_plan(candidates, retention_days, skip_runs)

    if not candidates:
        print(_warn("\nNothing to archive. Exiting."))
        return

    if not yes:
        if not (interactive and sys.stdin.isatty()):
            raise SystemExit("Global confirmation required. Re-run with --yes or interactive mode.")
        if not _input_yes_no("Proceed with archive/copy/verify sequence for all selected runs?", default_yes=False):
            raise SystemExit("Cancelled by user.")

    lock_path = Path("/tmp/archive_rawdata.lock")
    try:
        lock_fd = _acquire_lock(lock_path)
    except FileExistsError:
        raise SystemExit(f"Another archive_rawdata process is running (lock exists: {lock_path})")

    metadata: dict[str, Any] = {
        "workflow_id": "archive_rawdata",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root_path),
        "target_root": str(target_root_path),
        "retention_days": retention_days,
        "instrument_folders": instruments,
        "skip_runs": sorted(skip_runs),
        "dry_run": dry_run,
        "cleanup_in_archive": False,
        "log_path": str(log_path),
    }

    records: list[dict[str, Any]] = []
    copy_failures = 0
    verify_failures = 0

    try:
        required = sum(c.size_bytes for c in candidates)
        _ensure_target_free_space(target_root_path, required, min_free_gb)
        _preflight_target_paths(target_root_path, candidates)

        _append_log(log_path, f"archive_rawdata start: runs={len(candidates)} total_size={required}")

        for candidate in candidates:
            rec: dict[str, Any] = {
                "instrument": candidate.instrument,
                "run_id": candidate.run_id,
                "run_date": candidate.run_date.isoformat(),
                "source": str(candidate.source_path),
                "target": str(candidate.target_run_path),
                "size_bytes": candidate.size_bytes,
                "copy_status": "pending",
                "verify_status": "pending",
                "cleanup_status": "pending_external_cleanup",
                "status": "planned",
                "errors": [],
                "log_path": str(log_path),
            }

            if dry_run:
                rec["copy_status"] = "skipped_dry_run"
                rec["verify_status"] = "skipped_dry_run"
                rec["status"] = "dry_run_only"
                records.append(rec)
                print(_warn(f"[dry-run] Would archive {candidate.source_path} -> {candidate.target_run_path}"))
                _write_manifest(manifest_path, metadata, records)
                continue

            _append_log(log_path, f"run_start {candidate.run_id}")
            try:
                _rsync_copy(candidate)
                rec["copy_status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                rec["copy_status"] = "failed"
                rec["verify_status"] = "skipped_due_to_copy_failure"
                rec["status"] = "failed"
                rec["errors"].append(f"copy: {exc}")
                copy_failures += 1
                _append_log(log_path, f"run_copy_failed {candidate.run_id}: {exc}")
                records.append(rec)
                _write_manifest(manifest_path, metadata, records)
                continue

            try:
                _rsync_verify(candidate)
                rec["verify_status"] = "ok"
                rec["status"] = "copied_verified"
                _append_log(log_path, f"run_verified {candidate.run_id}")
            except Exception as exc:  # noqa: BLE001
                rec["verify_status"] = "failed"
                rec["status"] = "failed"
                rec["errors"].append(f"verify: {exc}")
                verify_failures += 1
                _append_log(log_path, f"run_verify_failed {candidate.run_id}: {exc}")

            records.append(rec)
            _write_manifest(manifest_path, metadata, records)

        _append_log(
            log_path,
            f"archive_rawdata done: processed={len(records)} copy_failures={copy_failures} verify_failures={verify_failures}",
        )

        _print_section("Done")
        print(_ok(f"Manifest: {manifest_path}"))
        print(_ok(f"Log: {log_path}"))
        print(_ok(f"Processed runs: {len(records)}"))
        print(_ok(f"Copy-failed runs: {copy_failures}" if copy_failures == 0 else f"Copy-failed runs: {copy_failures}"))
        if verify_failures:
            print(_err(f"Verify-failed runs: {verify_failures}"))
        else:
            print(_ok("Verify-failed runs: 0"))

        if copy_failures or verify_failures:
            raise SystemExit(1)
    finally:
        _release_lock(lock_fd, lock_path)


if __name__ == "__main__":
    main()
