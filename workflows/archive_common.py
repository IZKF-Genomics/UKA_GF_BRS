from __future__ import annotations

import configparser
import csv
from dataclasses import dataclass
import getpass
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
import pwd
from typing import Any

import yaml

RUN_PREFIX_RE = re.compile(r"^\d{6}_")
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def style(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def title(text: str) -> str:
    return style(text, "1;36")


def ok(text: str) -> str:
    return style(text, "1;32")


def warn(text: str) -> str:
    return style(text, "1;33")


def dim(text: str) -> str:
    return style(text, "2")


def print_section(text: str) -> None:
    print("\n" + title("=" * 80))
    print(title(text))
    print(title("=" * 80))


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def current_user() -> str:
    return (
        os.environ.get("SUDO_USER")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or getpass.getuser()
    )


def validate_keep_until(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"Invalid keep_until date: {value}. Use YYYY-MM-DD.") from exc
    return text


def default_rules() -> dict[str, Any]:
    return {"schema_version": 1, "updated_at": now_iso(), "runs": {}}


def load_rules(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_rules()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Failed to parse keep_rules file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid keep_rules format in {path}: expected mapping at top level")
    payload.setdefault("schema_version", 1)
    payload.setdefault("updated_at", now_iso())
    if not isinstance(payload.get("runs"), dict):
        payload["runs"] = {}
    return payload


def save_rules(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = now_iso()
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_active_keep_runs(path: Path) -> tuple[set[str], list[str]]:
    if not path.exists():
        return set(), []
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return set(), [f"Failed to parse keep_rules file {path}: {exc}"]
    if not isinstance(payload, dict):
        return set(), [f"Invalid keep_rules format in {path}: expected mapping"]
    runs = payload.get("runs") or {}
    if not isinstance(runs, dict):
        return set(), [f"Invalid keep_rules.runs format in {path}: expected mapping"]

    active: set[str] = set()
    notes: list[str] = []
    today = date.today()
    for run_id, rec in runs.items():
        run_id_s = str(run_id).strip()
        if not run_id_s:
            continue
        if not isinstance(rec, dict):
            notes.append(f"Invalid keep_rules record for run_id={run_id_s}: expected mapping")
            continue
        if rec.get("keep", True) is False:
            continue
        raw_keep_until = rec.get("keep_until")
        if raw_keep_until in (None, ""):
            active.add(run_id_s)
            continue
        try:
            keep_until = date.fromisoformat(str(raw_keep_until))
        except ValueError:
            notes.append(f"Invalid keep_until in keep_rules for run_id={run_id_s}: {raw_keep_until}")
            active.add(run_id_s)
            continue
        if keep_until >= today:
            active.add(run_id_s)
    return active, notes


@dataclass(frozen=True)
class RunFolderInfo:
    run_id: str
    path: Path
    owner: str
    project_id: str | None


def path_owner(path: Path) -> str:
    try:
        return pwd.getpwuid(path.stat().st_uid).pw_name
    except Exception:  # noqa: BLE001
        return "-"


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def project_name_from_ini(path: Path) -> str | None:
    ini_path = path / "project.ini"
    if not ini_path.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    if not parser.has_section("Project"):
        return None
    value = parser.get("Project", "project_name", fallback="").strip()
    return value or None


def sample_project_from_samplesheet(path: Path) -> str | None:
    for filename in ("samplesheet.csv", "samplesheet_bclconvert.csv"):
        samplesheet = path / filename
        if not samplesheet.is_file():
            continue
        current_section: str | None = None
        try:
            with samplesheet.open("r", encoding="utf-8", newline="") as fh:
                for raw_line in fh:
                    row = next(csv.reader([raw_line]))
                    first = row[0].strip() if row else ""
                    if not first:
                        continue
                    if first.startswith("[") and first.endswith("]"):
                        current_section = first[1:-1].strip()
                        continue
                    if current_section not in {"BCLConvert_Data", "Data"}:
                        continue
                    try:
                        project_idx = row.index("Sample_Project")
                    except ValueError:
                        return None
                    for data_line in fh:
                        data_row = next(csv.reader([data_line]))
                        first = data_row[0].strip() if data_row else ""
                        if not first:
                            continue
                        if first.startswith("[") and first.endswith("]"):
                            return None
                        if project_idx >= len(data_row):
                            continue
                        project_name = data_row[project_idx].strip()
                        if project_name:
                            return project_name
                    return None
        except Exception:  # noqa: BLE001
            return None
    return None


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def project_id_from_folder(path: Path) -> str | None:
    bpm_meta = load_yaml_file(path / "bpm.meta.yaml")
    project_name = nested_get(bpm_meta, "export", "demux", "project_name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    export_job_spec = load_json_file(path / "export_job_spec.json")
    project_name = export_job_spec.get("project_name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    project_name = sample_project_from_samplesheet(path)
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    project_name = project_name_from_ini(path)
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    project_meta = load_yaml_file(path / "project.yaml")
    project_name = project_meta.get("name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    return None


def build_run_folder_info(run_id: str, path: Path) -> RunFolderInfo:
    return RunFolderInfo(
        run_id=run_id,
        path=path,
        owner=path_owner(path),
        project_id=project_id_from_folder(path),
    )


def discover_runs(source_roots: list[Path]) -> tuple[dict[str, RunFolderInfo], list[str]]:
    found: dict[str, RunFolderInfo] = {}
    notes: list[str] = []
    for root in source_roots:
        if not root.exists() or not root.is_dir():
            notes.append(f"Source root missing or not a directory: {root}")
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if RUN_PREFIX_RE.match(entry.name):
                found.setdefault(entry.name, build_run_folder_info(entry.name, entry))
                continue
            for sub in entry.iterdir():
                if not sub.is_dir():
                    continue
                if RUN_PREFIX_RE.match(sub.name):
                    found.setdefault(sub.name, build_run_folder_info(sub.name, sub))
    return found, notes


def run_keep_tui(rules_path: Path, browse_root: Path, heading: str) -> tuple[bool, int, int]:
    import curses

    payload = load_rules(rules_path)
    discovered, notes = discover_runs([browse_root])
    for note in notes:
        print(warn(f"- {note}"))
    if not discovered:
        print(warn(f"No run IDs discovered under {browse_root}"))
        return False, 0, 0

    runs = sorted(discovered)
    existing = payload.get("runs") or {}
    show_project_id = any(info.project_id for info in discovered.values())
    owner_values = [discovered[run_id].owner for run_id in runs]
    project_values = [discovered[run_id].project_id or "-" for run_id in runs] if show_project_id else []
    marked = {run_id: bool((existing.get(run_id) or {}).get("keep", False)) for run_id in runs}
    keep_until = {run_id: (existing.get(run_id) or {}).get("keep_until") for run_id in runs}
    set_by_map = {run_id: str((existing.get(run_id) or {}).get("set_by") or "-") for run_id in runs}

    def column_width(values: list[str], header: str, min_width: int = 0, max_width: int | None = None) -> int:
        width = max([len(header), min_width, *(len(value) for value in values)], default=len(header))
        if max_width is not None:
            width = min(width, max_width)
        return width

    def clip_text(value: str, width: int) -> str:
        if width <= 0:
            return ""
        if len(value) <= width:
            return value
        if width == 1:
            return value[:1]
        return value[: width - 1] + "~"

    def apply_changes() -> tuple[int, int]:
        added_or_updated = 0
        removed = 0
        user = current_user()
        stamp = now_iso()
        run_map = payload.setdefault("runs", {})
        for run_id in runs:
            old = run_map.get(run_id)
            if marked.get(run_id, False):
                rec = {"keep": True, "set_by": user, "set_at": stamp, "keep_until": keep_until.get(run_id) or None}
                if old != rec:
                    run_map[run_id] = rec
                    added_or_updated += 1
            elif run_id in run_map:
                del run_map[run_id]
                removed += 1
        save_rules(rules_path, payload)
        return added_or_updated, removed

    def curses_main(stdscr) -> tuple[bool, int, int]:
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        color_header = curses.A_BOLD
        color_help = curses.A_DIM
        color_row = curses.A_NORMAL
        color_marked = curses.A_BOLD
        color_selected = curses.A_REVERSE | curses.A_BOLD
        color_status = curses.A_BOLD
        color_summary = curses.A_DIM
        use_colors = False
        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                curses.init_pair(2, curses.COLOR_WHITE, -1)
                curses.init_pair(3, curses.COLOR_GREEN, -1)
                curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
                curses.init_pair(5, curses.COLOR_YELLOW, -1)
                use_colors = True
                color_header = curses.color_pair(1) | curses.A_BOLD
                color_help = curses.color_pair(2) | curses.A_DIM
                color_row = curses.color_pair(2)
                color_marked = curses.color_pair(3) | curses.A_BOLD
                color_selected = curses.color_pair(4) | curses.A_BOLD
                color_status = curses.color_pair(5) | curses.A_BOLD
                color_summary = curses.color_pair(2) | curses.A_DIM
            except curses.error:
                pass

        idx = 0
        top = 0
        changed = False

        def render(status: str = "") -> None:
            nonlocal top
            h, w = stdscr.getmaxyx()
            stdscr.erase()
            stdscr.addnstr(0, 0, f"{heading} | root={browse_root} | runs={len(runs)}".ljust(max(0, w - 1)), w - 1, color_header)
            stdscr.addnstr(1, 0, "Up/Down: move  Space: toggle keep  u: keep-until  s: save  q: quit".ljust(max(0, w - 1)), w - 1, color_help)
            list_top = 4
            list_h = max(1, h - 6)
            owner_col = column_width(owner_values, "Owner", min_width=5, max_width=16)
            set_by_col = column_width([set_by_map.get(run_id, "-") for run_id in runs], "Set By", min_width=6, max_width=20)
            project_col = column_width(project_values, "Project ID", min_width=10, max_width=36) if show_project_id else 0
            fixed_non_run = 3 + owner_col + project_col + 10 + set_by_col + (5 if show_project_id else 4)
            run_col = min(column_width(runs, "Run ID", min_width=12), max(12, w - fixed_non_run - 1))
            if show_project_id:
                row_fmt = f"{{sel:<3}} {{run:<{run_col}}} {{owner:<{owner_col}}} {{project:<{project_col}}} {{ku:<10}} {{set_by:<{set_by_col}}}"
                header = row_fmt.format(sel="Sel", run="Run ID", owner="Owner", project="Project ID", ku="Keep Until", set_by="Set By")
            else:
                row_fmt = f"{{sel:<3}} {{run:<{run_col}}} {{owner:<{owner_col}}} {{ku:<10}} {{set_by:<{set_by_col}}}"
                header = row_fmt.format(sel="Sel", run="Run ID", owner="Owner", ku="Keep Until", set_by="Set By")
            stdscr.addnstr(3, 0, header.ljust(max(0, w - 1)), w - 1, color_help | curses.A_BOLD)
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
                owner = clip_text(discovered[run_id].owner, owner_col)
                project_id = clip_text(discovered[run_id].project_id or "-", project_col) if show_project_id else "-"
                ku = keep_until.get(run_id) or "-"
                set_by = clip_text(set_by_map.get(run_id, "-"), set_by_col)
                if show_project_id:
                    line = row_fmt.format(sel="[x]" if marked.get(run_id, False) else "[ ]", run=clip_text(run_id, run_col), owner=owner, project=project_id, ku=ku, set_by=set_by)
                else:
                    line = row_fmt.format(sel="[x]" if marked.get(run_id, False) else "[ ]", run=clip_text(run_id, run_col), owner=owner, ku=ku, set_by=set_by)
                attr = color_selected if pos == idx else (color_marked if marked.get(run_id, False) else color_row)
                stdscr.addnstr(y, 0, line.ljust(max(0, w - 1)), w - 1, attr)
            stdscr.addnstr(h - 2, 0, f"Marked: {sum(1 for v in marked.values() if v)}  Changed: {'yes' if changed else 'no'}".ljust(max(0, w - 1)), w - 1, color_summary)
            stdscr.addnstr(h - 1, 0, status.ljust(max(0, w - 1)), w - 1, color_status if status else color_row)
            stdscr.refresh()

        def prompt_keep_until(current: str | None) -> str | None:
            h, w = stdscr.getmaxyx()
            prompt = "keep_until for selected run (YYYY-MM-DD, empty clears)"
            while True:
                curses.curs_set(1)
                stdscr.move(h - 2, 0)
                stdscr.clrtoeol()
                stdscr.addnstr(h - 2, 0, prompt, w - 1)
                stdscr.move(h - 1, 0)
                stdscr.clrtoeol()
                prefix = f"current={current} -> " if current else ""
                if prefix:
                    stdscr.addnstr(h - 1, 0, prefix, w - 1)
                stdscr.refresh()
                curses.echo()
                raw = stdscr.getstr(h - 1, min(len(prefix), max(0, w - 2)), max(1, w - len(prefix) - 1))
                curses.noecho()
                try:
                    return validate_keep_until(raw.decode("utf-8", errors="ignore").strip())
                except SystemExit:
                    stdscr.move(h - 1, 0)
                    stdscr.clrtoeol()
                    stdscr.addnstr(h - 1, 0, "Invalid date. Use YYYY-MM-DD.", w - 1, curses.A_BOLD)
                    stdscr.refresh()
                    curses.napms(900)
                finally:
                    curses.curs_set(0)

        render()
        while True:
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                idx = max(0, idx - 1)
                render()
            elif key in (curses.KEY_DOWN, ord("j")):
                idx = min(len(runs) - 1, idx + 1)
                render()
            elif key == ord(" "):
                marked[runs[idx]] = not marked.get(runs[idx], False)
                changed = True
                render()
            elif key == ord("u"):
                run_id = runs[idx]
                keep_until[run_id] = prompt_keep_until(keep_until.get(run_id))
                if keep_until[run_id] is not None:
                    marked[run_id] = True
                changed = True
                render("keep_until updated")
            elif key == ord("s"):
                add_count, remove_count = apply_changes()
                render(f"Saved: {add_count} added/updated, {remove_count} removed")
                curses.napms(900)
                return True, add_count, remove_count
            elif key == ord("q"):
                if changed:
                    render("Unsaved changes. Press q again to discard.")
                    if stdscr.getch() == ord("q"):
                        return False, 0, 0
                    render()
                    continue
                return False, 0, 0

    saved, add_count, remove_count = curses.wrapper(curses_main)
    print_section(heading)
    print(f"Rules file: {rules_path}")
    if saved:
        print(ok(f"Saved keep rules: {add_count} added/updated, {remove_count} removed"))
    else:
        print(warn("No changes saved."))
    return saved, add_count, remove_count
