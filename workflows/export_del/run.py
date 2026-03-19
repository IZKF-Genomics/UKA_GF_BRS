#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _ansi(code: str) -> str:
    return f"\033[{code}m" if _supports_color() else ""


RESET = _ansi("0")
BOLD = _ansi("1")
BLUE = _ansi("34")
CYAN = _ansi("36")
GREEN = _ansi("32")


def _color(text: str, color: str, *, bold: bool = False) -> str:
    prefix = f"{BOLD if bold else ''}{color}"
    return f"{prefix}{text}{RESET}" if prefix else text


def _print_section(title: str, color: str = CYAN) -> None:
    line = "=" * 72
    print(_color(line, color))
    print(_color(title, color, bold=True))
    print(_color(line, color))


def _print_key_value(label: str, value: str, *, color: str = BLUE) -> None:
    print(f"{_color(label + ':', color, bold=True)} {value}")


def load_ctx() -> dict:
    """Load BPM ctx JSON if provided."""
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize_delete_endpoint(base_url: str, project_id: str) -> str:
    api_clean = base_url.rstrip("/")
    root = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    return f"{root}/{project_id}"


def main() -> None:
    ctx = load_ctx()
    params = ctx.get("params") or {}

    project_id = str(params.get("project_id") or "").strip()
    api_url = str(params.get("api_url") or "").strip()
    if not api_url:
        api_url = "http://genomics.rwth-aachen.de:9500/export"

    if not project_id:
        raise SystemExit("No project_id provided.")

    endpoint = normalize_delete_endpoint(api_url, project_id)
    req = Request(endpoint, headers={"Accept": "application/json"}, method="DELETE")

    try:
        with urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise SystemExit(f"Delete API request failed: {exc.code} {detail}")
    except URLError as exc:
        raise SystemExit(f"Delete API request failed: {exc.reason}")

    _print_section("Export Deletion Request", BLUE)
    _print_key_value("Endpoint", endpoint)
    _print_key_value("Project", project_id)

    try:
        parsed = json.loads(resp_body)
    except json.JSONDecodeError:
        _print_section("Deletion Result", GREEN)
        print(resp_body)
        return

    _print_section("Deletion Result", GREEN)
    status = parsed.get("status") or parsed.get("message") or "completed"
    _print_key_value("Status", str(status), color=GREEN)
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    main()
