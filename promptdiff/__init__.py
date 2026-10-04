"""promptdiff: diff two LLM system prompts like code.

Compare versions of a system prompt: character/line diffs, token and
estimated-cost deltas, sentence-level change summaries, and an overlap
score — all offline, zero API keys.
"""

from .core import (
    PromptStats,
    analyze,
    cost_estimate,
    jaccard_similarity,
    load_prompt,
    sentence_changes,
    stats,
    token_estimate,
    unified_diff,
)

__all__ = [
    "PromptStats",
    "analyze",
    "cost_estimate",
    "jaccard_similarity",
    "load_prompt",
    "sentence_changes",
    "stats",
    "token_estimate",
    "unified_diff",
]

__version__ = "0.1.0"
