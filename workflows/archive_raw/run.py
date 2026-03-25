#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEGACY_DIR = HERE.parent / "archive_rawdata"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from run import main

if __name__ == "__main__":
    main()
