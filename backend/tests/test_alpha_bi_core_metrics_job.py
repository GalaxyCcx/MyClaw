from __future__ import annotations

import unittest

from api.alpha_bi_core_metrics_job import (
    find_query_ref,
    month_range_ymd,
    text_hash,
)


class TestAlphaBiCoreMetricsJobHelpers(unittest.TestCase):
    def test_month_range_ymd(self):
        start, end = month_range_ymd(2026, 2)
        self.assertEqual(start, "2026-02-01")
        self.assertEqual(end, "2026-02-28")

    def test_find_query_ref_prefers_query_button(self):
        elements = [
            {"ref": "e1", "tag": "button", "role": "button", "label": "导出"},
            {"ref": "e2", "tag": "button", "role": "button", "label": "查询"},
            {"ref": "e3", "tag": "div", "role": "", "label": "对比期"},
        ]
        self.assertEqual(find_query_ref(elements), "e2")

    def test_text_hash_stable(self):
        a = text_hash("hello world")
        b = text_hash("hello world")
        c = text_hash("hello world 2")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()
