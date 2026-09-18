# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Tests for the pure aggregation helper only -- `progress_breakdown` takes
plain dicts and does not import `frappe`, so it is tested without a bench,
same as `tests/` for the doc_events helpers (see CLAUDE.md: "no local bench
in this environment").

Decision 5 (PLAN.md) applied to a Select breakdown: a blank
`pledge_progress_raw` must land in its own "Not Recorded" row, never folded
into an existing option or silently dropped.
"""

import unittest

from patient_reach.patient_reach.report.sparsh_follow_up_progress.sparsh_follow_up_progress import (
	NOT_RECORDED,
	PROGRESS_OPTIONS,
	progress_breakdown,
)


class TestProgressBreakdown(unittest.TestCase):
	def test_every_option_present_even_at_zero(self):
		breakdown = {row["pledge_progress_raw"]: row["count"] for row in progress_breakdown([])}
		for option in [*PROGRESS_OPTIONS, NOT_RECORDED]:
			with self.subTest(option=option):
				self.assertEqual(breakdown[option], 0)

	def test_counts_each_option(self):
		rows = [
			{"pledge_progress_raw": "Achieved"},
			{"pledge_progress_raw": "Achieved"},
			{"pledge_progress_raw": "Self-Modified"},
		]
		breakdown = {row["pledge_progress_raw"]: row["count"] for row in progress_breakdown(rows)}
		self.assertEqual(breakdown["Achieved"], 2)
		self.assertEqual(breakdown["Self-Modified"], 1)
		self.assertEqual(breakdown["Not Yet Achieved"], 0)

	def test_blank_is_not_recorded_not_dropped_not_zero(self):
		rows = [{"pledge_progress_raw": None}, {"pledge_progress_raw": ""}, {}]
		breakdown = {row["pledge_progress_raw"]: row["count"] for row in progress_breakdown(rows)}
		self.assertEqual(breakdown[NOT_RECORDED], 3)
		self.assertEqual(sum(breakdown.values()), 3)

	def test_unexpected_value_falls_back_to_not_recorded_rather_than_raising(self):
		rows = [{"pledge_progress_raw": "some retired option"}]
		breakdown = {row["pledge_progress_raw"]: row["count"] for row in progress_breakdown(rows)}
		self.assertEqual(breakdown[NOT_RECORDED], 1)


if __name__ == "__main__":
	unittest.main()
