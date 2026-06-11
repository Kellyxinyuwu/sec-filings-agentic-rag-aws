#!/usr/bin/env python3
"""
Smoke-test Bedrock Mantle — run from project root:

    python scripts/test_mantle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Project root on sys.path when run as: python scripts/test_mantle.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.llm_mantle import mantle_chat  # noqa: E402


def main() -> None:
    reply = mantle_chat(
        system="You are a helpful assistant. Reply briefly.",
        user="Say hello in one word.",
        max_tokens=16,
    )
    print("Mantle reply:", reply)


if __name__ == "__main__":
    main()