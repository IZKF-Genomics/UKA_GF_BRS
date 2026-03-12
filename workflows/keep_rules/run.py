#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES_PATH = "/data/shared/bpm_manifests/keep_rules.yaml"
DEFAULT_SOURCE_ROOTS = "/data/raw,/data/fastq"
DEFAULT_BROWSE_ROOT = "/data/fastq"
RUN_PREFIX_RE = re.compile(r"^\d{6}_")
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


def load_ctx() -> dict[str, Any]:
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


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


def _print_section(title: str) -> None:
    print("\n" + _title("=" * 80))
    print(_title(title))
    print(_title("=" * 80))


def _input_with_default(prompt: str, default: str) -> str:
    answer = input(_title(f"{prompt} [{default}]: ")).strip()
    return answer or default


def _input_yes_no(prompt: str, default_yes: bool = False) -> bool:
    suffix = "Y/n" if default_yes else "y/N"
    answer = input(_title(f"{prompt} [{suffix}]: ")).strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}


def _choose_browse_root(current: Path) -> Path:
    _print_section("keep_rules Browse Root")
    print(_dim("Choose which path to scan before opening TUI."))
    options = [
        ("1", "/data/fastq"),
        ("2", "/data/projects"),
        ("3", "/data/raw"),
        ("4", "custom path"),
    ]
    for key, label in options:
        print(f"  {key}. {label}")
    choice = _input_with_default("Browse root option", "1").strip().lower()
    if choice in {"1", "fastq"}:
        return Path("/data/fastq").resolve()
    if choice in {"2", "projects"}:
        return Path("/data/projects").resolve()
    if choice in {"3", "raw"}:
        return Path("/data/raw").resolve()
    if choice in {"4", "custom"}:
        custom = _input_with_default("Custom browse root", str(current)).strip()
        return Path(custom).expanduser().resolve()
    # Keep previous/default on unknown input.
    return current


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _current_user() -> str:
    return (
        os.environ.get("SUDO_USER")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or getpass.getuser()
    )


def _validate_keep_until(value: str) -> str | None:
    v = value.strip()
    if not v:
        return None
    try:
        date.fromisoformat(v)
    except ValueError as exc:
        raise SystemExit(f"Invalid keep_until date: {value}. Use YYYY-MM-DD.") from exc
    return v


def _default_rules() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": _now_iso(),
        "runs": {},
    }


def _load_rules(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_rules()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Failed to parse keep_rules file {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid keep_rules format in {path}: expected mapping at top level")

    payload.setdefault("schema_version", 1)
    payload.setdefault("updated_at", _now_iso())
    runs = payload.get("runs")
    if not isinstance(runs, dict):
        payload["runs"] = {}
    return payload


def _save_rules(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _now_iso()
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _discover_run_ids(source_roots: list[Path]) -> tuple[set[str], list[str]]:
    found: set[str] = set()
    notes: list[str] = []

    for root in source_roots:
        if not root.exists() or not root.is_dir():
            notes.append(f"Source root missing or not a directory: {root}")
            continue

        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if RUN_PREFIX_RE.match(entry.name):
                found.add(entry.name)
                continue
            # Scan one more level (instrument -> run).
            for sub in entry.iterdir():
                if not sub.is_dir():
                    continue
                if RUN_PREFIX_RE.match(sub.name):
                    found.add(sub.name)
    return found, notes


def _parse_index_selection(raw: str, max_index: int) -> list[int]:
    picks: set[int] = set()
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        if "-" in part:
            left, right = part.split("-", 1)
            try:
                a = int(left)
                b = int(right)
            except ValueError as exc:
                raise SystemExit(f"Invalid range token: {part}") from exc
            if a > b:
                a, b = b, a
            for idx in range(a, b + 1):
                if idx < 1 or idx > max_index:
                    raise SystemExit(f"Selection index out of range: {idx}")
                picks.add(idx)
            continue
        try:
            idx = int(part)
        except ValueError as exc:
            raise SystemExit(f"Invalid selection token: {part}") from exc
        if idx < 1 or idx > max_index:
            raise SystemExit(f"Selection index out of range: {idx}")
        picks.add(idx)
    return sorted(picks)


def _prompt_select_run_ids(source_roots: list[Path]) -> list[str]:
    discovered, notes = _discover_run_ids(source_roots)
    for note in notes:
        print(_warn(f"- {note}"))

    if not discovered:
        raw = _input_with_default("No runs discovered. Enter run IDs (comma-separated)", "")
        return _split_csv(raw)

    pool = sorted(discovered)
    keyword = _input_with_default("Filter keyword for run IDs (optional)", "").strip()
    if keyword:
        pool = [r for r in pool if keyword in r]
    if not pool:
        print(_warn("No runs match filter."))
        raw = _input_with_default("Enter run IDs (comma-separated)", "")
        return _split_csv(raw)

    _print_section("Run Browser")
    print(f"Discovered runs: {len(pool)}")
    for i, run_id in enumerate(pool, start=1):
        print(f"{i:>4}. {run_id}")

    while True:
        select_raw = _input_with_default(
            "Select by number/range (e.g. 1,3-5), 'm' for manual IDs, or 'q' to cancel",
            "",
        ).strip()
        lowered = select_raw.lower()
        if lowered in {"q", "quit", "exit"}:
            return []
        if lowered in {"m", "manual"}:
            raw = _input_with_default("Run IDs (comma-separated)", "")
            return _split_csv(raw)
        if not select_raw:
            print(_warn("No selection entered. Choose numbers, 'm' for manual, or 'q' to cancel."))
            continue
        try:
            selected_idx = _parse_index_selection(select_raw, len(pool))
            return [pool[i - 1] for i in selected_idx]
        except SystemExit as exc:
            print(_warn(str(exc)))


def _print_rules(path: Path, payload: dict[str, Any]) -> None:
    runs = payload.get("runs") or {}
    _print_section("keep_rules")
    print(f"Rules file: {path}")
    print(f"Run entries: {len(runs)}")
    if not runs:
        print(_warn("No run keep rules."))
        return

    run_col = max(34, min(60, max(len(k) for k in runs) + 2))
    row_fmt = f"{{run:<{run_col}}}{{keep_until:>14}}  {{set_by:<16}}  {{set_at}}"
    header = row_fmt.format(run="Run ID", keep_until="Keep Until", set_by="Set By", set_at="Set At")
    print(_dim(header))
    print(_dim("-" * len(header)))
    for run_id in sorted(runs):
        rec = runs.get(run_id) or {}
        print(
            row_fmt.format(
                run=run_id,
                keep_until=str(rec.get("keep_until") or "-"),
                set_by=str(rec.get("set_by") or "-"),
                set_at=str(rec.get("set_at") or "-"),
            )
        )


def _apply_add(payload: dict[str, Any], run_ids: list[str], keep_until: str | None, user: str) -> int:
    runs = payload.setdefault("runs", {})
    changed = 0
    stamp = _now_iso()
    for run_id in sorted(set(run_ids)):
        prev = runs.get(run_id) if isinstance(runs, dict) else None
        rec = {
            "keep": True,
            "set_by": user,
            "set_at": stamp,
            "keep_until": keep_until,
        }
        if prev != rec:
            runs[run_id] = rec
            changed += 1
    return changed


def _apply_remove(payload: dict[str, Any], run_ids: list[str]) -> int:
    runs = payload.setdefault("runs", {})
    changed = 0
    for run_id in sorted(set(run_ids)):
        if run_id in runs:
            del runs[run_id]
            changed += 1
    return changed


def _prune_candidates(payload: dict[str, Any], source_roots: list[Path]) -> tuple[list[str], list[str]]:
    runs = payload.get("runs") or {}
    existing, notes = _discover_run_ids(source_roots)
    stale = sorted([run_id for run_id in runs if run_id not in existing])
    return stale, notes


def _run_keep_tui(payload: dict[str, Any], rules_path: Path, browse_root: Path) -> None:
    import curses

    discovered, notes = _discover_run_ids([browse_root])
    if notes:
        for note in notes:
            print(_warn(f"- {note}"))
    if not discovered:
        print(_warn(f"No run IDs discovered under {browse_root}"))
        return

    runs = sorted(discovered)
    existing = payload.get("runs") or {}

    marked: dict[str, bool] = {run_id: bool((existing.get(run_id) or {}).get("keep", False)) for run_id in runs}
    keep_until: dict[str, str | None] = {
        run_id: (existing.get(run_id) or {}).get("keep_until") for run_id in runs
    }
    set_by_map: dict[str, str] = {
        run_id: str((existing.get(run_id) or {}).get("set_by") or "-") for run_id in runs
    }

    def _apply_changes() -> tuple[int, int]:
        added_or_updated = 0
        removed = 0
        user = _current_user()
        stamp = _now_iso()
        run_map = payload.setdefault("runs", {})

        for run_id in runs:
            old = run_map.get(run_id)
            if marked.get(run_id, False):
                rec = {
                    "keep": True,
                    "set_by": user,
                    "set_at": stamp,
                    "keep_until": keep_until.get(run_id) or None,
                }
                if old != rec:
                    run_map[run_id] = rec
                    added_or_updated += 1
            else:
                if run_id in run_map:
                    del run_map[run_id]
                    removed += 1
        _save_rules(rules_path, payload)
        return added_or_updated, removed

    def _curses_main(stdscr) -> tuple[bool, int, int]:
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        use_colors = False
        color_header = curses.A_BOLD
        color_help = curses.A_DIM
        color_row = curses.A_NORMAL
        color_marked = curses.A_BOLD
        color_selected = curses.A_REVERSE | curses.A_BOLD
        color_status = curses.A_BOLD
        color_summary = curses.A_DIM

        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)   # header
                curses.init_pair(2, curses.COLOR_WHITE, -1)  # regular/help
                curses.init_pair(3, curses.COLOR_GREEN, -1)  # marked rows
                curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)  # selected row
                curses.init_pair(5, curses.COLOR_YELLOW, -1)  # status
                use_colors = True
                color_header = curses.color_pair(1) | curses.A_BOLD
                color_help = curses.color_pair(2) | curses.A_DIM
                color_row = curses.color_pair(2)
                color_marked = curses.color_pair(3) | curses.A_BOLD
                color_selected = curses.color_pair(4) | curses.A_BOLD
                color_status = curses.color_pair(5) | curses.A_BOLD
                color_summary = curses.color_pair(2) | curses.A_DIM
            except curses.error:
                use_colors = False

        idx = 0
        top = 0
        changed = False
        add_count = 0
        remove_count = 0

        def _render(status: str = "") -> None:
            nonlocal top
            h, w = stdscr.getmaxyx()
            stdscr.erase()
            header = f"keep_rules TUI | root={browse_root} | runs={len(runs)}"
            help_line = "Up/Down: move  Space: toggle keep  u: keep-until  s: save  q: quit"
            stdscr.addnstr(0, 0, header.ljust(max(0, w - 1)), w - 1, color_header)
            stdscr.addnstr(1, 0, help_line.ljust(max(0, w - 1)), w - 1, color_help)

            list_top = 4
            list_h = max(1, h - 6)
            run_col = max(20, min(48, w - 32))
            row_fmt = f"{{sel:<3}} {{run:<{run_col}}} {{ku:<10}} {{set_by}}"
            list_header = row_fmt.format(sel="Sel", run="Run ID", ku="Keep Until", set_by="Set By")
            stdscr.addnstr(3, 0, list_header.ljust(max(0, w - 1)), w - 1, color_help | curses.A_BOLD)
            if idx < top:
                top = idx
            elif idx >= top + list_h:
                top = idx - list_h + 1

            for row in range(list_h):
                pos = top + row
                y = list_top + row
                if pos >= len(runs):
                    stdscr.addnstr(y, 0, " " * max(0, w - 1), w - 1, color_row)
                    continue
                run_id = runs[pos]
                mark = "[x]" if marked.get(run_id, False) else "[ ]"
                ku = keep_until.get(run_id) or "-"
                set_by = set_by_map.get(run_id, "-")
                line = row_fmt.format(sel=mark, run=run_id, ku=ku, set_by=set_by)
                attr = color_selected if pos == idx else (color_marked if marked.get(run_id, False) else color_row)
                stdscr.addnstr(y, 0, line.ljust(max(0, w - 1)), w - 1, attr)

            summary = f"Marked: {sum(1 for v in marked.values() if v)}  Changed: {'yes' if changed else 'no'}"
            stdscr.addnstr(h - 2, 0, summary.ljust(max(0, w - 1)), w - 1, color_summary)
            if status:
                stdscr.addnstr(h - 1, 0, status.ljust(max(0, w - 1)), w - 1, color_status)
            elif use_colors:
                stdscr.addnstr(h - 1, 0, " " * max(0, w - 1), w - 1, color_row)
            stdscr.refresh()

        def _prompt_keep_until(current: str | None) -> str | None:
            curses.curs_set(1)
            h, w = stdscr.getmaxyx()
            prompt = "keep_until for selected run (YYYY-MM-DD, empty clears)"
            while True:
                stdscr.move(h - 2, 0)
                stdscr.clrtoeol()
                stdscr.addnstr(h - 2, 0, prompt, w - 1)
                stdscr.move(h - 1, 0)
                stdscr.clrtoeol()
                if current:
                    stdscr.addnstr(h - 1, 0, f"current={current} -> ", w - 1)
                stdscr.refresh()
                curses.echo()
                prefix = f"current={current} -> " if current else ""
                raw = stdscr.getstr(h - 1, min(len(prefix), max(0, w - 2)), max(1, w - len(prefix) - 1))
                curses.noecho()
                text = raw.decode("utf-8", errors="ignore").strip()
                try:
                    parsed = _validate_keep_until(text)
                except SystemExit:
                    stdscr.move(h - 2, 0)
                    stdscr.clrtoeol()
                    stdscr.move(h - 1, 0)
                    stdscr.clrtoeol()
                    stdscr.addnstr(h - 1, 0, "Invalid date. Use YYYY-MM-DD.", w - 1, curses.A_BOLD)
                    stdscr.refresh()
                    curses.napms(900)
                    continue
                finally:
                    curses.curs_set(0)
                return parsed

        _render()
        while True:
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                idx = max(0, idx - 1)
                _render()
            elif key in (curses.KEY_DOWN, ord("j")):
                idx = min(len(runs) - 1, idx + 1)
                _render()
            elif key == ord(" "):
                run_id = runs[idx]
                marked[run_id] = not marked.get(run_id, False)
                changed = True
                _render()
            elif key == ord("u"):
                run_id = runs[idx]
                ku = _prompt_keep_until(keep_until.get(run_id))
                keep_until[run_id] = ku
                if ku is not None:
                    marked[run_id] = True
                changed = True
                _render("keep_until updated")
            elif key == ord("s"):
                add_count, remove_count = _apply_changes()
                changed = False
                _render(f"Saved: {add_count} added/updated, {remove_count} removed")
                curses.napms(900)
                return True, add_count, remove_count
            elif key == ord("q"):
                if changed:
                    _render("Unsaved changes. Press q again to discard.")
                    key2 = stdscr.getch()
                    if key2 == ord("q"):
                        return False, 0, 0
                    _render()
                    continue
                return False, 0, 0

    saved, add_count, remove_count = curses.wrapper(_curses_main)
    _print_section("keep_rules TUI")
    print(f"Rules file: {rules_path}")
    if saved:
        print(_ok(f"Saved keep rules: {add_count} added/updated, {remove_count} removed"))
    else:
        print(_warn("No changes saved."))


def _interactive_action(
    action: str,
    run_ids: list[str],
    keep_until: str | None,
    source_roots: list[Path],
    apply: bool,
) -> tuple[str, list[str], str | None, list[Path], bool]:
    _print_section("keep_rules Interactive Setup")
    print(_dim("Press Enter to keep defaults."))

    if action == "interactive":
        action = _input_with_default("Action (list/add/remove/prune)", "list").strip().lower()

    if action in {"add", "remove"} and not run_ids:
        if _input_yes_no("Browse discovered run IDs?", default_yes=True):
            run_ids = _prompt_select_run_ids(source_roots)
        else:
            run_raw = _input_with_default("Run IDs (comma-separated)", "")
            run_ids = _split_csv(run_raw)
    if action == "add" and keep_until is None:
        keep_until = _validate_keep_until(_input_with_default("Keep until (YYYY-MM-DD; optional)", ""))
    if action == "prune":
        roots_raw = _input_with_default("Source roots (comma-separated)", ",".join(str(p) for p in source_roots))
        source_roots = [Path(p).expanduser().resolve() for p in _split_csv(roots_raw)]
        apply = _parse_bool(_input_with_default("Apply prune (true/false)", "true" if apply else "false"), apply)

    return action, run_ids, keep_until, source_roots, apply


def _parse_params() -> dict[str, Any]:
    ctx = load_ctx()
    params = dict(ctx.get("params") or {})

    parser = argparse.ArgumentParser(description="Manage keep rules for archive/cleanup workflows.")
    parser.add_argument("--action", default="interactive", choices=["interactive", "list", "add", "remove", "prune"])
    parser.add_argument("--tui", nargs="?", const="true", default="true")
    parser.add_argument("--browse-root", default=DEFAULT_BROWSE_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-ids", default="")
    parser.add_argument("--keep-until", default="")
    parser.add_argument("--rules-path", default=DEFAULT_RULES_PATH)
    parser.add_argument("--source-roots", default=DEFAULT_SOURCE_ROOTS)
    parser.add_argument("--apply", nargs="?", const="true", default="false")
    parser.add_argument("--non-interactive", nargs="?", const="true", default="false")
    parser.add_argument("--interactive", nargs="?", const="true", default="true")
    parser.add_argument("--yes", nargs="?", const="true", default="false")

    if params:
        return params

    args = parser.parse_args()
    return {
        "action": args.action,
        "tui": args.tui,
        "browse_root": args.browse_root,
        "run_id": args.run_id,
        "run_ids": args.run_ids,
        "keep_until": args.keep_until,
        "rules_path": args.rules_path,
        "source_roots": args.source_roots,
        "apply": args.apply,
        "non_interactive": args.non_interactive,
        "interactive": args.interactive,
        "yes": args.yes,
    }


def main() -> None:
    params = _parse_params()
    action = str(params.get("action") or "interactive").strip().lower()
    tui = _parse_bool(params.get("tui"), True)
    browse_root = Path(str(params.get("browse_root") or DEFAULT_BROWSE_ROOT)).expanduser().resolve()
    run_ids = _split_csv(params.get("run_ids"))
    run_id_single = str(params.get("run_id") or "").strip()
    if run_id_single:
        run_ids.append(run_id_single)
    keep_until = _validate_keep_until(str(params.get("keep_until") or ""))
    rules_path = Path(str(params.get("rules_path") or DEFAULT_RULES_PATH)).expanduser().resolve()
    source_roots = [Path(p).expanduser().resolve() for p in _split_csv(params.get("source_roots") or DEFAULT_SOURCE_ROOTS)]
    apply = _parse_bool(params.get("apply"), False)
    non_interactive = _parse_bool(params.get("non_interactive"), False)
    interactive = _parse_bool(params.get("interactive"), True)
    yes = _parse_bool(params.get("yes"), False)

    if non_interactive:
        interactive = False
        yes = True

    payload = _load_rules(rules_path)

    # Default UX: launch TUI directly when action is interactive.
    if action == "interactive" and tui:
        if not sys.stdin.isatty():
            print(_warn("TUI requires a TTY. Falling back to list mode."))
            action = "list"
        else:
            browse_root = _choose_browse_root(browse_root)
            _run_keep_tui(payload, rules_path, browse_root)
            return

    if interactive and sys.stdin.isatty():
        action, run_ids, keep_until, source_roots, apply = _interactive_action(
            action, run_ids, keep_until, source_roots, apply
        )
    elif action == "interactive":
        action = "list"

    if action not in {"list", "add", "remove", "prune"}:
        raise SystemExit(f"Unsupported action: {action}")

    if action == "list":
        _print_rules(rules_path, payload)
        return

    if action == "add":
        if not run_ids:
            if interactive and sys.stdin.isatty():
                print(_warn("No run IDs selected. No changes applied."))
                return
            raise SystemExit("No run IDs provided. Use --run-id or --run-ids.")
        changed = _apply_add(payload, run_ids, keep_until, _current_user())
        _save_rules(rules_path, payload)
        print(_ok(f"Updated keep rules: {changed} entries added/updated"))
        print(_ok(f"Rules file: {rules_path}"))
        return

    if action == "remove":
        if not run_ids:
            if interactive and sys.stdin.isatty():
                print(_warn("No run IDs selected. No changes applied."))
                return
            raise SystemExit("No run IDs provided. Use --run-id or --run-ids.")
        changed = _apply_remove(payload, run_ids)
        _save_rules(rules_path, payload)
        print(_ok(f"Updated keep rules: {changed} entries removed"))
        print(_ok(f"Rules file: {rules_path}"))
        return

    # action == prune
    stale, notes = _prune_candidates(payload, source_roots)
    _print_section("keep_rules prune")
    print(f"Rules file: {rules_path}")
    print(f"Source roots: {', '.join(str(p) for p in source_roots)}")
    for note in notes:
        print(_warn(f"- {note}"))
    print(f"Stale keep entries (not found in source roots): {len(stale)}")
    if stale:
        for run_id in stale[:50]:
            print(f"  - {run_id}")
        if len(stale) > 50:
            print(_dim(f"  ... and {len(stale) - 50} more"))

    if not stale:
        print(_ok("Nothing to prune."))
        return

    if not apply:
        print(_warn("Dry-run only. Re-run with --apply true to remove stale entries."))
        return

    if not yes and interactive and sys.stdin.isatty():
        if not _input_yes_no("Apply prune and remove all stale keep entries?", default_yes=False):
            raise SystemExit("Cancelled by user.")
    elif not yes and not non_interactive:
        raise SystemExit("Global confirmation required. Re-run with --yes true or interactive mode.")

    changed = _apply_remove(payload, stale)
    _save_rules(rules_path, payload)
    print(_ok(f"Pruned keep rules: {changed} entries removed"))
    print(_ok(f"Rules file: {rules_path}"))


if __name__ == "__main__":
    main()
