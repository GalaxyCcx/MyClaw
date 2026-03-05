from __future__ import annotations

import unittest

from api.alpha_bi_select_dropdown_job import match_dropdown_option


class TestAlphaBiSelectDropdown(unittest.TestCase):
    def test_match_exact(self):
        options = [
            {"handle": "e1", "text": "全品类", "value": ""},
            {"handle": "e2", "text": "品类A", "value": "a"},
        ]
        m = match_dropdown_option(options, "全品类")
        self.assertIsNotNone(m)
        self.assertEqual(m["handle"], "e1")
        self.assertEqual(m["text"], "全品类")

    def test_match_contains(self):
        options = [
            {"handle": "e1", "text": "全品类", "value": ""},
            {"handle": "e2", "text": "品类A-子类", "value": "a"},
        ]
        m = match_dropdown_option(options, "品类A")
        self.assertIsNotNone(m)
        self.assertEqual(m["handle"], "e2")

    def test_match_exact_over_contains(self):
        options = [
            {"handle": "e1", "text": "品类", "value": ""},
            {"handle": "e2", "text": "品类A", "value": "a"},
        ]
        m = match_dropdown_option(options, "品类")
        self.assertIsNotNone(m)
        self.assertEqual(m["handle"], "e1")

    def test_match_none(self):
        options = [
            {"handle": "e1", "text": "全品类", "value": ""},
        ]
        m = match_dropdown_option(options, "不存在的选项")
        self.assertIsNone(m)

    def test_match_empty_target(self):
        options = [{"handle": "e1", "text": "全品类", "value": ""}]
        m = match_dropdown_option(options, "")
        self.assertIsNone(m)

    def test_match_whitespace_normalized(self):
        options = [{"handle": "e1", "text": "全 品 类", "value": ""}]
        m = match_dropdown_option(options, "全品类")
        self.assertIsNotNone(m)
        self.assertEqual(m["handle"], "e1")


if __name__ == "__main__":
    unittest.main()
