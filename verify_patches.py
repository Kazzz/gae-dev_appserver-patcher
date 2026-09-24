#!/usr/bin/env python3
"""dev_appserver互換パッチがすべて適用済みか検証します。"""

from __future__ import annotations

import sys

from apply_patches import main


if __name__ == "__main__":
    raise SystemExit(main([*sys.argv[1:], "--check"]))
