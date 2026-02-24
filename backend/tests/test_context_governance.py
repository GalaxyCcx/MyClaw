from __future__ import annotations

import unittest

from agent.auto_compactor import compact_history
from agent.context_budget import compute_thresholds, estimate_messages_tokens
from agent.history_pruner import prune_history
from agent.overflow_recovery import is_context_overflow


def _build_history(turns: int, tool_chars: int = 1200) -> list[dict]:
    history: list[dict] = []
    for i in range(turns):
        history.append({"role": "user", "content": f"用户问题 {i} " + "x" * 100})
        history.append({"role": "assistant", "content": f"助手回答 {i} " + "y" * 200})
        history.append({"role": "tool", "content": "z" * tool_chars})
    return history


class ContextGovernanceTests(unittest.TestCase):
    def test_compute_thresholds_has_safe_boundaries(self):
        thresholds = compute_thresholds(131072, 20000, 4000)
        self.assertGreater(thresholds["preflight_limit"], 0)
        self.assertGreater(thresholds["target_tokens"], thresholds["preflight_limit"])

    def test_prune_history_preserves_recent_turns(self):
        history = _build_history(turns=8, tool_chars=3000)
        pruned, stats = prune_history(
            history,
            target_tokens=1200,
            preserve_recent_turns=3,
            model_name="qwen-plus",
            max_tool_result_chars=500,
        )
        self.assertLess(len(pruned), len(history))
        self.assertGreater(stats["before_tokens"], stats["after_tokens"])
        user_count = sum(1 for m in pruned if m.get("role") == "user")
        self.assertGreaterEqual(user_count, 3)

    def test_compact_history_adds_summary_message(self):
        history = _build_history(turns=6, tool_chars=500)
        compacted, stats = compact_history(history, preserve_recent_turns=2, model_name="qwen-plus")
        self.assertTrue(compacted)
        self.assertEqual(compacted[0].get("role"), "system")
        self.assertIn("[Context Compact Summary]", compacted[0].get("content", ""))
        self.assertGreater(stats["summary_chars"], 0)
        self.assertGreater(stats["compacted_turns"], 0)

    def test_overflow_detection_keywords(self):
        self.assertTrue(is_context_overflow(Exception("maximum context length exceeded")))
        self.assertTrue(is_context_overflow(Exception("上下文长度超出限制")))
        self.assertFalse(is_context_overflow(Exception("network timeout")))

    def test_estimate_messages_tokens_returns_positive(self):
        tokens = estimate_messages_tokens(_build_history(turns=2))
        self.assertGreater(tokens, 0)


if __name__ == "__main__":
    unittest.main()
