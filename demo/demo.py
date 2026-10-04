"""promptdiff demo: compares two versions of a coding-assistant system prompt.

Run:  python demo/demo.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

OLD_PROMPT = """You are an expert pair programmer.

Follow the user's instructions exactly.
Write clean, idiomatic code with type hints.
Keep responses short; do not over-explain.
Never mention that you are an AI model.
"""

NEW_PROMPT = """You are an expert pair programmer.

Follow the user's instructions exactly. Ask one clarifying question when the request is ambiguous.
Write clean, idiomatic code with type hints and docstrings.
Prefer small, focused functions.
Keep responses short; do not over-explain.
Never mention that you are an AI model.
If you are unsure about an API, say so instead of guessing.
"""

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old = Path(tmp) / "v1.txt"
        new = Path(tmp) / "v2.txt"
        old.write_text(OLD_PROMPT)
        new.write_text(NEW_PROMPT)

        print("=== text report ===")
        r = subprocess.run(
            [sys.executable, "-m", "promptdiff", str(old), str(new), "--rate", "5.00"],
            cwd=str(ROOT),
        )
        r.check_returncode()

        print("\n=== JSON report (first 400 chars) ===")
        r2 = subprocess.run(
            [sys.executable, "-m", "promptdiff", str(old), str(new), "--json", "--no-diff"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        r2.check_returncode()
        print(r2.stdout[:400] + "...")


if __name__ == "__main__":
    main()
