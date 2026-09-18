# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Tests for `select_breakdown`, `_split_prevention_level` and
`prevention_level_breakdown`. `_split_prevention_level` throws through
`frappe.throw`, so these need `frappe` importable (CI only, per CLAUDE.md --
no local bench in this environment) but touch no database.

Decision 10 (PLAN.md): Prevention Level and S status are separate columns,
and "Level 2s" is not itself a level -- pinned by
`test_2s_is_not_a_level_value`.
"""

import unittest

import frappe

from patient_reach.patient_reach.report.sparsh_intake_overview.sparsh_intake_overview import (
	LEVELS,
	NOT_RECORDED,
	S_STATUSES,
	_split_prevention_level,
	prevention_level_breakdown,
	select_breakdown,
)


class TestSelectBreakdown(unittest.TestCase):
	def test_every_option_present_at_zero(self):
		breakdown = {r["option"]: r["count"] for r in select_breakdown([], "sunset_rule", ["Yes", "No"])}
		self.assertEqual(breakdown, {"Yes": 0, "No": 0, NOT_RECORDED: 0})

	def test_blank_is_not_recorded_not_dropped(self):
		rows = [{"sunset_rule": None}, {"sunset_rule": ""}, {}]
		breakdown = {r["option"]: r["count"] for r in select_breakdown(rows, "sunset_rule", ["Yes", "No"])}
		self.assertEqual(breakdown[NOT_RECORDED], 3)


class TestSplitPreventionLevel(unittest.TestCase):
	def test_s_modifier_means_active(self):
		self.assertEqual(_split_prevention_level("Level 2s"), ("Level 2", "Active"))

	def test_no_modifier_means_inactive(self):
		self.assertEqual(_split_prevention_level("Level 3"), ("Level 3", "Inactive"))

	def test_blank_is_none_none(self):
		self.assertEqual(_split_prevention_level(""), (None, None))
		self.assertEqual(_split_prevention_level(None), (None, None))

	def test_2s_is_not_a_level_value(self):
		with self.assertRaises(frappe.ValidationError):
			_split_prevention_level("2s")

	def test_every_level_round_trips(self):
		for level in LEVELS:
			with self.subTest(level=level):
				self.assertEqual(_split_prevention_level(level), (level, "Inactive"))
				self.assertEqual(_split_prevention_level(level + "s"), (level, "Active"))


class TestPreventionLevelBreakdown(unittest.TestCase):
	def test_level_and_s_status_are_separate_columns(self):
		rows = [{"prevention_level": "Level 2s"}, {"prevention_level": "Level 3"}]
		result = prevention_level_breakdown(rows)
		fields = {r["field"] for r in result}
		self.assertEqual(fields, {"prevention_level", "s_status"})

		levels = {r["option"]: r["count"] for r in result if r["field"] == "prevention_level"}
		statuses = {r["option"]: r["count"] for r in result if r["field"] == "s_status"}
		self.assertEqual(levels["Level 2"], 1)
		self.assertEqual(levels["Level 3"], 1)
		self.assertEqual(statuses["Active"], 1)
		self.assertEqual(statuses["Inactive"], 1)

	def test_blank_prevention_level_is_not_recorded_in_both_columns(self):
		result = prevention_level_breakdown([{"prevention_level": ""}])
		levels = {r["option"]: r["count"] for r in result if r["field"] == "prevention_level"}
		statuses = {r["option"]: r["count"] for r in result if r["field"] == "s_status"}
		self.assertEqual(levels[NOT_RECORDED], 1)
		self.assertEqual(statuses[NOT_RECORDED], 1)

	def test_all_levels_and_statuses_present_at_zero(self):
		result = prevention_level_breakdown([])
		levels = {r["option"] for r in result if r["field"] == "prevention_level"}
		statuses = {r["option"] for r in result if r["field"] == "s_status"}
		self.assertEqual(levels, set(LEVELS) | {NOT_RECORDED})
		self.assertEqual(statuses, set(S_STATUSES) | {NOT_RECORDED})


if __name__ == "__main__":
	unittest.main()
