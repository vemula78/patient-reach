# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Tests for `latest_per_ticket` and `overdue_calls`, the pure grouping and
filtering helpers behind the report. No `frappe.db` access -- both take plain
dicts, same pattern as `sparsh_follow_up_progress`'s tests.

Only a Connected call counts, and the latest is by `actual_call_date` then
`creation`, not by programme week; rows here say so explicitly.
"""

import datetime
import unittest

from patient_reach.patient_reach.report.sparsh_overdue_calls.sparsh_overdue_calls import (
	latest_per_ticket,
	overdue_calls,
)

D = datetime.date


class TestLatestPerTicket(unittest.TestCase):
	def test_picks_the_latest_call_not_the_highest_week(self):
		rows = [
			{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 6, "actual_call_date": D(2026, 9, 1), "name": "SFU-1"},
			{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 2, "actual_call_date": D(2026, 9, 10), "name": "SFU-2"},
		]
		self.assertEqual(latest_per_ticket(rows)["TKT-1"]["name"], "SFU-2")

	def test_unanswered_attempts_do_not_supersede_a_connected_call(self):
		rows = [
			{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 2, "actual_call_date": D(2026, 9, 1), "name": "SFU-1"},
			{"baseline_ticket": "TKT-1", "call_disposition": "No Answer", "follow_up_week": 6, "actual_call_date": D(2026, 9, 10), "name": "SFU-2"},
		]
		self.assertEqual(latest_per_ticket(rows)["TKT-1"]["name"], "SFU-1")

	def test_tie_broken_by_actual_call_date(self):
		rows = [
			{
				"baseline_ticket": "TKT-1",
				"call_disposition": "Connected",
				"follow_up_week": 6,
				"actual_call_date": D(2026, 9, 1),
				"name": "SFU-1",
			},
			{
				"baseline_ticket": "TKT-1",
				"call_disposition": "Connected",
				"follow_up_week": 6,
				"actual_call_date": D(2026, 9, 10),
				"name": "SFU-2",
			},
		]
		self.assertEqual(latest_per_ticket(rows)["TKT-1"]["name"], "SFU-2")

	def test_rows_with_no_baseline_ticket_are_skipped_not_grouped_together(self):
		rows = [{"baseline_ticket": None, "follow_up_week": 2, "name": "SFU-orphan"}]
		self.assertEqual(latest_per_ticket(rows), {})

	def test_separate_tickets_stay_separate(self):
		rows = [
			{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 2, "name": "SFU-1"},
			{"baseline_ticket": "TKT-2", "call_disposition": "Connected", "follow_up_week": 2, "name": "SFU-2"},
		]
		latest = latest_per_ticket(rows)
		self.assertEqual(set(latest), {"TKT-1", "TKT-2"})


class TestOverdueCalls(unittest.TestCase):
	def test_next_call_date_in_the_past_is_overdue(self):
		rows = [{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 2, "next_call_date": D(2026, 9, 1)}]
		self.assertEqual(len(overdue_calls(rows, D(2026, 9, 18))), 1)

	def test_next_call_date_today_or_future_is_not_overdue(self):
		rows = [
			{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 2, "next_call_date": D(2026, 9, 18)},
			{"baseline_ticket": "TKT-2", "call_disposition": "Connected", "follow_up_week": 2, "next_call_date": D(2026, 9, 19)},
		]
		self.assertEqual(overdue_calls(rows, D(2026, 9, 18)), [])

	def test_no_next_call_date_is_excluded_not_treated_as_always_due(self):
		rows = [{"baseline_ticket": "TKT-1", "call_disposition": "Connected", "follow_up_week": 2, "next_call_date": None}]
		self.assertEqual(overdue_calls(rows, D(2026, 9, 18)), [])

	def test_only_the_latest_record_per_ticket_is_considered(self):
		rows = [
			{
				"baseline_ticket": "TKT-1",
				"call_disposition": "Connected",
				"follow_up_week": 2,
				"actual_call_date": D(2026, 8, 1),
				"next_call_date": D(2026, 8, 1),
				"name": "SFU-old",
			},
			{
				"baseline_ticket": "TKT-1",
				"call_disposition": "Connected",
				"follow_up_week": 6,
				"actual_call_date": D(2026, 9, 15),
				"next_call_date": D(2026, 9, 30),
				"name": "SFU-new",
			},
		]
		result = overdue_calls(rows, D(2026, 9, 18))
		self.assertEqual(result, [])  # the latest record's next_call_date is in the future


if __name__ == "__main__":
	unittest.main()
