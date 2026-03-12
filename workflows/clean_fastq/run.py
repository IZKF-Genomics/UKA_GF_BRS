#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
import yaml

DEFAULT_SOURCE_ROOT = "/data/fastq"
DEFAULT_RETENTION_DAYS = 90
DEFAULT_MANIFEST_DIR = "/data/shared/bpm_manifests"
DEFAULT_KEEP_RULES_PATH = "/data/shared/bpm_manifests/keep_rules.yaml"
DEFAULT_CLEAN_PATTERNS = [
    "*.fastq.gz",
    "*.fq.gz",
    ".pixi",
    "work",
    ".renv",
    ".Rproj.user",
    ".nextflow",
    ".nextflow.log*",
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


def _dim(text: str) -> str:
    return _style(text, "2")


@dataclass
class RunCandidate:
    run_id: str
    run_date: date
    retention_reference_date: date
    retention_reference_source: str
    source_path: Path
    total_size_bytes: int
    estimated_reclaim_bytes: int
    estimated_after_bytes: int
    estimated_reclaim_pct: float


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


def _parse_exported_at_date(value: Any) -> date | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def _load_active_keep_runs(keep_rules_path: Path) -> tuple[set[str], list[str]]:
    if not keep_rules_path.exists():
        return set(), []
    try:
        payload = yaml.safe_load(keep_rules_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return set(), [f"Failed to parse keep_rules file {keep_rules_path}: {exc}"]
    if not isinstance(payload, dict):
        return set(), [f"Invalid keep_rules format in {keep_rules_path}: expected mapping"]

    runs = payload.get("runs") or {}
    if not isinstance(runs, dict):
        return set(), [f"Invalid keep_rules.runs format in {keep_rules_path}: expected mapping"]

    today = date.today()
    active: set[str] = set()
    notes: list[str] = []
    for run_id, rec in runs.items():
        run_id_s = str(run_id).strip()
        if not run_id_s:
            continue
        if not isinstance(rec, dict):
            notes.append(f"Invalid keep_rules record for run_id={run_id_s}: expected mapping")
            continue
        if rec.get("keep", True) is False:
            continue
        keep_until_raw = rec.get("keep_until")
        if keep_until_raw in (None, ""):
            active.add(run_id_s)
            continue
        try:
            keep_until = date.fromisoformat(str(keep_until_raw))
        except ValueError:
            notes.append(f"Invalid keep_until in keep_rules for run_id={run_id_s}: {keep_until_raw}")
            active.add(run_id_s)
            continue
        if keep_until >= today:
            active.add(run_id_s)
    return active, notes


def _get_retention_reference(run_dir: Path, run_date: date) -> tuple[date, str]:
    meta_path = run_dir / "bpm.meta.yaml"
    if not meta_path.exists():
        return run_date, "run_name_prefix"
    try:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return run_date, "run_name_prefix"

    export = meta.get("export") or {}
    for key_path in (
        ("last_exported_at",),
        ("demux", "last_exported_at"),
    ):
        cur: Any = export
        for key in key_path:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(key)
        parsed = _parse_exported_at_date(cur)
        if parsed is not None:
            return parsed, "export_last_exported_at"

    return run_date, "run_name_prefix"


def _du_size_bytes(path: Path) -> int:
    import subprocess

    result = subprocess.run(["du", "-sb", str(path)], check=True, text=True, capture_output=True)
    return int(result.stdout.strip().split()[0])


def _compute_cutoff(retention_days: int) -> date:
    return date.today() - timedelta(days=retention_days)


def _discover_candidates(
    source_root: Path,
    retention_days: int,
    skip_runs: set[str],
    keep_run_ids: set[str],
) -> tuple[list[RunCandidate], list[str]]:
    issues: list[str] = []
    cutoff = _compute_cutoff(retention_days)
    candidates: list[RunCandidate] = []

    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir():
            continue
        run_date = _parse_run_date(entry.name)
        if run_date is None:
            continue
        ref_date, ref_source = _get_retention_reference(entry, run_date)
        if ref_date >= cutoff:
            continue
        if entry.name in skip_runs:
            continue
        if entry.name in keep_run_ids:
            continue
        try:
            total_size_bytes = _du_size_bytes(entry)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"Failed to calculate size for {entry}: {exc}")
            continue
        candidates.append(
            RunCandidate(
                run_id=entry.name,
                run_date=run_date,
                retention_reference_date=ref_date,
                retention_reference_source=ref_source,
                source_path=entry,
                total_size_bytes=total_size_bytes,
                estimated_reclaim_bytes=0,
                estimated_after_bytes=total_size_bytes,
                estimated_reclaim_pct=0.0,
            )
        )

    candidates.sort(key=lambda c: (c.run_date, c.run_id))
    return candidates, issues


def _print_section(title: str) -> None:
    print("\n" + _title("=" * 80))
    print(_title(title))
    print(_title("=" * 80))


def _print_plan(
    candidates: list[RunCandidate],
    retention_days: int,
    skip_runs: set[str],
    keep_run_ids: set[str],
    patterns: list[str],
) -> None:
    cutoff = _compute_cutoff(retention_days)
    _print_section("Clean Plan")
    print(f"Retention days: {retention_days}")
    print(f"Clean runs older than: {cutoff.isoformat()} (strictly before this date)")
    print("Retention reference: export.last_exported_at -> run-name YYMMDD prefix")
    print(f"Runs skipped by user: {', '.join(sorted(skip_runs)) if skip_runs else '(none)'}")
    print(f"Runs protected by keep_rules: {len(keep_run_ids)}")
    print(f"Clean patterns: {', '.join(patterns) if patterns else '(none)'}")

    if not candidates:
        print("\nNo run directories match the clean criteria.")
        return

    run_col = max(38, min(54, max(len(c.run_id) for c in candidates) + 2))
    current_col = 14
    after_col = 20
    pct_col = 14
    row_fmt = f"{{no:>4}}  {{run:<{run_col}}}{{current:>{current_col}}}  {{after:>{after_col}}}  {{pct:>{pct_col}}}"

    print("\nSelected runs:")
    header = row_fmt.format(
        no="No.",
        run="Run ID",
        current="Current Size",
        after="Est. Size After Clean",
        pct="Est. Reclaim %",
    )
    print(_dim(header))
    print(_dim("-" * len(header)))
    for i, c in enumerate(candidates, start=1):
        print(
            row_fmt.format(
                no=f"{i}.",
                run=c.run_id,
                current=_format_bytes(c.total_size_bytes),
                after=_format_bytes(c.estimated_after_bytes),
                pct=f"{c.estimated_reclaim_pct:5.1f}%",
            )
        )

    total = sum(c.total_size_bytes for c in candidates)
    total_after = sum(c.estimated_after_bytes for c in candidates)
    total_reclaim = sum(c.estimated_reclaim_bytes for c in candidates)
    total_pct = 0.0 if total == 0 else (total_reclaim * 100.0 / total)
    print("\nSummary:")
    print(_ok(f"- Run count: {len(candidates)}"))
    print(_ok(f"- Total current size: {_format_bytes(total)}"))
    print(_ok(f"- Estimated size after clean: {_format_bytes(total_after)}"))
    print(_ok(f"- Estimated reclaimable size: {_format_bytes(total_reclaim)} ({total_pct:.1f}%)"))


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
    retention_days: int,
    patterns: list[str],
    skip_runs: set[str],
) -> tuple[str, int, list[str], set[str]]:
    _print_section("clean_fastq Interactive Setup")
    print(_dim("Press Enter to keep defaults."))

    source_root = _input_with_default("Source root", source_root)

    retention_raw = _input_with_default("Retention days", str(retention_days))
    try:
        retention_days = int(retention_raw)
    except ValueError:
        raise SystemExit(f"Invalid retention days: {retention_raw}")

    patterns_raw = _input_with_default("Clean patterns (comma-separated)", ",".join(patterns))
    patterns = _split_csv(patterns_raw)

    skip_raw = _input_with_default("Skip run IDs (comma-separated; optional)", ",".join(sorted(skip_runs)))
    skip_runs = set(_split_csv(skip_raw))

    return source_root, retention_days, patterns, skip_runs


def _collect_clean_targets(run_dir: Path, patterns: list[str]) -> list[Path]:
    raw: set[Path] = set()
    for pat in patterns:
        for p in run_dir.rglob(pat):
            if p == run_dir:
                continue
            raw.add(p)

    # Keep only top-most targets to avoid redundant deletes.
    minimized: list[Path] = []
    for p in sorted(raw, key=lambda x: len(x.parts)):
        if any(parent == p or p.is_relative_to(parent) for parent in minimized):
            continue
        minimized.append(p)

    # Delete deeper paths first.
    minimized.sort(key=lambda x: len(x.parts), reverse=True)
    return minimized


def _path_size_bytes(path: Path) -> int:
    try:
        if path.is_symlink() or path.is_file():
            return path.lstat().st_size
        if path.is_dir():
            total = 0
            for root, dirs, files in os.walk(path, followlinks=False):
                root_p = Path(root)
                for d in dirs:
                    dpath = root_p / d
                    if dpath.is_symlink():
                        try:
                            total += dpath.lstat().st_size
                        except OSError:
                            pass
                for f in files:
                    fpath = root_p / f
                    try:
                        total += fpath.lstat().st_size
                    except OSError:
                        pass
            return total
    except OSError:
        return 0
    return 0


def _estimate_cleanup_impact(run_dir: Path, total_size_bytes: int, patterns: list[str]) -> tuple[int, int, float]:
    targets = _collect_clean_targets(run_dir, patterns)
    reclaim_bytes = sum(_path_size_bytes(t) for t in targets)
    reclaim_bytes = min(reclaim_bytes, total_size_bytes)
    after_bytes = max(0, total_size_bytes - reclaim_bytes)
    pct = 0.0 if total_size_bytes == 0 else (reclaim_bytes * 100.0 / total_size_bytes)
    return reclaim_bytes, after_bytes, pct


def _remove_target(path: Path) -> tuple[str, str | None]:
    try:
        if not path.exists() and not path.is_symlink():
            return "missing", None
        if path.is_symlink() or path.is_file():
            path.unlink()
            return "file", None
        if path.is_dir():
            shutil.rmtree(path)
            return "dir", None
        return "skip", "unsupported path type"
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)


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


def _manifest_setup_hint(dir_path: Path) -> str:
    return (
        f"Manifest/log directory is not writable: {dir_path}\n"
        "Choose one of:\n"
        f"1) Create and grant access:\n"
        f"   sudo mkdir -p {dir_path}\n"
        f"   sudo chown root:bioinfo {dir_path}\n"
        f"   sudo chmod 2775 {dir_path}\n"
        "2) Use another writable location:\n"
        "   --manifest-dir /data/shared/bpm_manifests\n"
        "   or --manifest-path /data/shared/bpm_manifests/<name>.json"
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
        with tempfile.NamedTemporaryFile(prefix=".clean_fastq_manifest_write_test_", dir=manifest_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(manifest_path.parent) + f"\nDetail: {exc}") from exc

    try:
        with tempfile.NamedTemporaryFile(prefix=".clean_fastq_log_write_test_", dir=log_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(log_path.parent) + f"\nDetail: {exc}") from exc


def _append_log(log_path: Path, message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def _write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_params() -> dict[str, Any]:
    ctx = load_ctx()
    params = dict(ctx.get("params") or {})

    parser = argparse.ArgumentParser(description="Clean FASTQ run folders by removing pattern-matched files/directories.")
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--clean-patterns", default=",".join(DEFAULT_CLEAN_PATTERNS))
    parser.add_argument("--skip-runs", default="")
    parser.add_argument("--non-interactive", nargs="?", const="true", default="false")
    parser.add_argument("--interactive", nargs="?", const="true", default="true")
    parser.add_argument("--yes", nargs="?", const="true", default="false")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--keep-rules-path", default=DEFAULT_KEEP_RULES_PATH)

    if params:
        return params

    args = parser.parse_args()
    return {
        "source_root": args.source_root,
        "retention_days": args.retention_days,
        "clean_patterns": args.clean_patterns,
        "skip_runs": args.skip_runs,
        "non_interactive": args.non_interactive,
        "interactive": args.interactive,
        "yes": args.yes,
        "dry_run": args.dry_run,
        "manifest_path": args.manifest_path,
        "manifest_dir": args.manifest_dir,
        "keep_rules_path": args.keep_rules_path,
    }


def main() -> None:
    params = _parse_params()

    source_root = str(params.get("source_root") or DEFAULT_SOURCE_ROOT).strip()
    retention_days = _parse_int(params.get("retention_days"), DEFAULT_RETENTION_DAYS)
    clean_patterns = _split_csv(params.get("clean_patterns") or ",".join(DEFAULT_CLEAN_PATTERNS))
    for p in DEFAULT_CLEAN_PATTERNS:
        if p not in clean_patterns:
            clean_patterns.append(p)

    skip_runs = set(_split_csv(params.get("skip_runs")))
    non_interactive = _parse_bool(params.get("non_interactive"), False)
    interactive = _parse_bool(params.get("interactive"), True)
    yes = _parse_bool(params.get("yes"), False)
    dry_run = _parse_bool(params.get("dry_run"), False)
    manifest_path_raw = str(params.get("manifest_path") or "").strip()
    manifest_dir = Path(str(params.get("manifest_dir") or DEFAULT_MANIFEST_DIR)).expanduser().resolve()
    keep_rules_path = Path(str(params.get("keep_rules_path") or DEFAULT_KEEP_RULES_PATH)).expanduser().resolve()

    if retention_days < 0:
        raise SystemExit("retention_days must be >= 0")

    if non_interactive:
        interactive = False
        yes = True
        print(_dim("[mode] non_interactive=true -> interactive disabled, global confirmation auto-approved"))

    if interactive and sys.stdin.isatty():
        source_root, retention_days, clean_patterns, skip_runs = _interactive_overrides(
            source_root,
            retention_days,
            clean_patterns,
            skip_runs,
        )

    source_root_path = Path(source_root).expanduser().resolve()
    if not source_root_path.exists() or not source_root_path.is_dir():
        raise SystemExit(f"Source root not found or not a directory: {source_root_path}")
    keep_run_ids, keep_notes = _load_active_keep_runs(keep_rules_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_manifest_path = manifest_dir / f"clean_fastq_{timestamp}.json"
    manifest_path = Path(manifest_path_raw).expanduser().resolve() if manifest_path_raw else default_manifest_path
    log_path = manifest_path.parent / f"{manifest_path.stem}.log"

    _print_section("Path Confirmation")
    print(f"Source root: {source_root_path}")
    print(f"Source layout: flat run directories")
    print(f"Keep rules path: {keep_rules_path}")
    print(f"Protected runs from keep rules: {len(keep_run_ids)}")
    print(f"Manifest path: {manifest_path}")
    print(f"Log path: {log_path}")

    _preflight_manifest_paths(manifest_path, log_path)

    candidates, issues = _discover_candidates(source_root_path, retention_days, skip_runs, keep_run_ids)
    for c in candidates:
        reclaim, after, pct = _estimate_cleanup_impact(c.source_path, c.total_size_bytes, clean_patterns)
        c.estimated_reclaim_bytes = reclaim
        c.estimated_after_bytes = after
        c.estimated_reclaim_pct = pct

    if issues or keep_notes:
        _print_section("Discovery Notes")
        for issue in issues:
            print(_warn(f"- {issue}"))
        for note in keep_notes:
            print(_warn(f"- {note}"))

    _print_plan(candidates, retention_days, skip_runs, keep_run_ids, clean_patterns)
    if not candidates:
        print(_warn("\nNothing to clean. Exiting."))
        return

    if not yes:
        if not (interactive and sys.stdin.isatty()):
            raise SystemExit("Global confirmation required. Re-run with --yes or interactive mode.")
        if not _input_yes_no("Proceed with clean sequence for all selected runs?", default_yes=False):
            raise SystemExit("Cancelled by user.")

    lock_path = Path("/tmp/clean_fastq.lock")
    try:
        lock_fd = _acquire_lock(lock_path)
    except FileExistsError:
        raise SystemExit(f"Another clean_fastq process is running (lock exists: {lock_path})")

    payload: dict[str, Any] = {
        "workflow_id": "clean_fastq",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root_path),
        "retention_days": retention_days,
        "clean_patterns": clean_patterns,
        "skip_runs": sorted(skip_runs),
        "keep_rules_path": str(keep_rules_path),
        "keep_protected_runs": sorted(keep_run_ids),
        "dry_run": dry_run,
        "log_path": str(log_path),
        "records": [],
    }

    try:
        _append_log(log_path, f"clean_fastq start: runs={len(candidates)}")

        for candidate in candidates:
            rec: dict[str, Any] = {
                "run_id": candidate.run_id,
                "run_date": candidate.run_date.isoformat(),
                "retention_reference_date": candidate.retention_reference_date.isoformat(),
                "retention_reference_source": candidate.retention_reference_source,
                "source": str(candidate.source_path),
                "total_size_bytes": candidate.total_size_bytes,
                "clean_patterns": clean_patterns,
                "status": "planned",
                "matched_targets": 0,
                "removed_files": 0,
                "removed_dirs": 0,
                "errors": [],
            }

            targets = _collect_clean_targets(candidate.source_path, clean_patterns)
            rec["matched_targets"] = len(targets)

            if dry_run:
                rec["status"] = "dry_run_only"
                for t in targets:
                    print(_warn(f"[dry-run] Would remove: {t}"))
                payload["records"].append(rec)
                _write_manifest(manifest_path, payload)
                continue

            rec["status"] = "cleaning"
            for t in targets:
                kind, err = _remove_target(t)
                if kind == "file":
                    rec["removed_files"] += 1
                elif kind == "dir":
                    rec["removed_dirs"] += 1
                elif kind == "error":
                    rec["errors"].append(f"{t}: {err}")

            rec["status"] = "failed" if rec["errors"] else ("done_no_matches" if len(targets) == 0 else "done")
            payload["records"].append(rec)
            _write_manifest(manifest_path, payload)

        done = sum(1 for r in payload["records"] if str(r.get("status", "")).startswith("done"))
        failed = sum(1 for r in payload["records"] if r.get("status") == "failed")
        dry = sum(1 for r in payload["records"] if r.get("status") == "dry_run_only")

        _append_log(log_path, f"clean_fastq done: processed={len(payload['records'])} failed={failed}")

        _print_section("Done")
        print(_ok(f"Manifest: {manifest_path}"))
        print(_ok(f"Log: {log_path}"))
        print(_ok(f"Processed runs: {len(payload['records'])}"))
        print(_ok(f"Done runs: {done}"))
        if failed:
            print(_err(f"Failed runs: {failed}"))
        else:
            print(_ok("Failed runs: 0"))
        if dry:
            print(_warn(f"Dry-run-only runs: {dry}"))

        if failed:
            raise SystemExit(1)
    finally:
        _release_lock(lock_fd, lock_path)


if __name__ == "__main__":
    main()
