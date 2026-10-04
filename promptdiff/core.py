"""Core comparison logic for promptdiff.

Everything here is pure-Python with no third-party dependencies, so the
library works offline and the tests run in seconds.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_prompt(path: str | Path) -> str:
    """Read a prompt file and return its text, normalizing line endings."""
    text = Path(path).read_text(encoding="utf-8")
    # Normalize to \n, strip trailing whitespace on each line, drop a single
    # trailing newline so "a\n" and "a" compare as equal.
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token estimate (zero-dependency heuristic)
# ---------------------------------------------------------------------------


def token_estimate(text: str) -> int:
    """Estimate tokens using a whitespace/punctuation heuristic.

    A decent approximation for English prose: split on word boundaries and
    count words plus punctuation runs, then pad slightly. Documented as a
    heuristic — install ``tiktoken`` if you need exact counts.
    """
    if not text:
        return 0
    words = re.findall(r"\w+|[^\w\s]", text)
    # Empirically ~0.75 words/token for English; ceil to be conservative.
    return max(1, int(len(words) / 0.75) + 1)


def cost_estimate(tokens: int, dollars_per_mtok: float = 3.00) -> float:
    """Estimate input cost in USD for ``tokens`` at the given $/M-token rate."""
    return round(tokens / 1_000_000 * dollars_per_mtok, 6)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class PromptStats:
    name: str
    chars: int
    lines: int
    words: int
    tokens: int
    est_input_cost_usd: float = field(default=0.0)


def stats(text: str, name: str = "prompt", dollars_per_mtok: float = 3.00) -> PromptStats:
    tokens = token_estimate(text)
    return PromptStats(
        name=name,
        chars=len(text),
        lines=text.count("\n") + 1 if text else 0,
        words=len(re.findall(r"\w+", text)),
        tokens=tokens,
        est_input_cost_usd=cost_estimate(tokens, dollars_per_mtok),
    )


# ---------------------------------------------------------------------------
# Diffs
# ---------------------------------------------------------------------------


def unified_diff(old: str, new: str, fromname: str = "old", toname: str = "new", n: int = 3) -> str:
    """Unified diff of two prompt texts."""
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=fromname,
            tofile=toname,
            n=n,
        )
    )


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n+")


def _sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def sentence_changes(old: str, new: str) -> dict[str, list[str]]:
    """Summarize changes at sentence granularity.

    Returns {"added": [...], "removed": [...], "rewritten": [...]} where
    rewritten entries are "old  ->  new" pairs for sentences that changed
    but overlap heavily (>= 60% word Jaccard).
    """
    old_sents, new_sents = _sentences(old), _sentences(new)
    matcher = difflib.SequenceMatcher(a=old_sents, b=new_sents, autojunk=False)
    added, removed = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed.extend(old_sents[i1:i2])
        added.extend(new_sents[j1:j2])
    # Pair each removed sentence with its best added match (>= 60% word
    # Jaccard) and report those pairs as rewrites instead of add+remove.
    rewritten: list[str] = []
    remaining_added = list(added)
    kept_removed: list[str] = []
    for old_sent in removed:
        best, best_score = None, 0.0
        for cand in remaining_added:
            score = jaccard_similarity(old_sent, cand)
            if score > best_score:
                best, best_score = cand, score
        if best is not None and best_score >= 0.6:
            rewritten.append(f"{old_sent}  ->  {best}")
            remaining_added.remove(best)
        else:
            kept_removed.append(old_sent)
    return {"added": remaining_added, "removed": kept_removed, "rewritten": rewritten}


def _words(text: str) -> set[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    return set(re.findall(r"\w+", text))


def jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity of word sets; 1.0 for identical/empty-equal texts."""
    wa, wb = _words(a), _words(b)
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ---------------------------------------------------------------------------
# Full analysis report
# ---------------------------------------------------------------------------


def analyze(
    old: str,
    new: str,
    old_name: str = "old",
    new_name: str = "new",
    dollars_per_mtok: float = 3.00,
) -> dict:
    """Compare two prompts and return a full report dict."""
    old_stats = stats(old, old_name, dollars_per_mtok)
    new_stats = stats(new, new_name, dollars_per_mtok)
    changes = sentence_changes(old, new)
    report = {
        "old": old_stats,
        "new": new_stats,
        "delta_tokens": new_stats.tokens - old_stats.tokens,
        "delta_chars": new_stats.chars - old_stats.chars,
        "delta_lines": new_stats.lines - old_stats.lines,
        "delta_est_cost_usd": round(new_stats.est_input_cost_usd - old_stats.est_input_cost_usd, 6),
        "jaccard_similarity": round(jaccard_similarity(old, new), 4),
        "changes": changes,
        "num_added": len(changes["added"]),
        "num_removed": len(changes["removed"]),
        "num_rewritten": len(changes["rewritten"]),
        "unified_diff": unified_diff(old, new, old_name, new_name),
    }
    return report
