# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Tests for queue_rows, the clinical reviewer's DRL v1.4 list. Plain dicts,
no database."""

import unittest
from datetime import date

from patient_reach import drl_v14 as drl
from patient_reach.patient_reach.report.sparsh_clinical_review_queue.sparsh_clinical_review_queue import (
	NOT_RECORDED,
	queue_rows,
)

TODAY = date(2026, 11, 20)


def visit(name, **values):
	return {
		"name": name,
		"patient_id": "CG-" + name,
		"counselled_date": "2026-11-01",
		"docstatus": 0,
		**values,
	}


def tracker(name, visit_name, **values):
	return {"name": name, "caregiver_id": "CG-" + visit_name, "baseline_ticket": visit_name, **values}


class TestQueueRows(unittest.TestCase):
	def test_routine_visits_are_not_listed(self):
		self.assertEqual(queue_rows([visit("T1", referral_priority=drl.P_NONE)], [], TODAY), [])
		self.assertEqual(queue_rows([visit("T1")], [], TODAY), [])

	def test_emergency_first(self):
		rows = queue_rows(
			[
				visit("T1", referral_priority=drl.P_HIGH, review_reasons="High-priority BP"),
				visit(
					"T2",
					referral_priority=drl.P_EMERGENCY,
					review_reasons="Red-flag emergency",
					red_flag_status=drl.RF_PRESENT,
				),
			],
			[],
			TODAY,
		)
		self.assertEqual([r["name"] for r in rows], ["T2", "T1"])
		self.assertEqual(rows[0]["emergency_action"], NOT_RECORDED)

	def test_open_referral_is_followed_through(self):
		rows = queue_rows(
			[visit("T1", referral_priority=drl.P_HIGH, referral_advised="Yes", referral_date="2026-11-01")],
			[
				tracker(
					"SFT-1",
					"T1",
					referral_priority=drl.P_HIGH,
					referral_date="2026-11-01",
					follow_up_status="No Response",
				)
			],
			TODAY,
		)
		self.assertEqual(len(rows), 1)
		self.assertIn("Follow-up ended (No Response) with the referral still open", rows[0]["why"])
		self.assertEqual(rows[0]["consultation_status"], NOT_RECORDED)
		self.assertEqual(rows[0]["referral_disposition"], "Open")

	def test_closed_referral_without_a_reason_drops_off(self):
		rows = queue_rows(
			[visit("T1", referral_priority=drl.P_ROUTINE, referral_advised="Yes")],
			[tracker("SFT-1", "T1", referral_priority=drl.P_ROUTINE, referral_disposition=drl.D_DECLINED)],
			TODAY,
		)
		self.assertEqual(rows, [])

	def test_a_reason_keeps_a_closed_referral_listed(self):
		rows = queue_rows(
			[
				visit(
					"T1",
					referral_priority=drl.P_IMMEDIATE,
					referral_advised="Yes",
					review_reasons="Severe BP",
				)
			],
			[tracker("SFT-1", "T1", referral_priority=drl.P_IMMEDIATE, referral_disposition=drl.D_COMPLETED)],
			TODAY,
		)
		self.assertEqual(rows[0]["why"], "Severe BP")

	def test_referral_without_advice_or_follow_up_record(self):
		rows = queue_rows(
			[visit("T1", referral_priority=drl.P_ROUTINE, referral_date="2026-11-01")], [], TODAY
		)
		self.assertEqual(rows[0]["why"], "Referral advice not recorded; No follow-up record on this visit")
		self.assertEqual(rows[0]["follow_up_status"], "No follow-up record")

	def test_follow_up_row_on_another_visit_is_not_used(self):
		rows = queue_rows(
			[visit("T1", referral_priority=drl.P_HIGH, referral_advised="Yes", referral_date="2026-11-19")],
			[tracker("SFT-1", "T9", caregiver_id="CG-T1", consultation_status=drl.CONSULTED)],
			TODAY,
		)
		self.assertIn("No follow-up record on this visit", rows[0]["why"])
		self.assertIsNone(rows[0]["tracker"])

	def test_event_on_a_call_is_listed_on_its_own(self):
		rows = queue_rows(
			[],
			[tracker("SFT-1", "T1", review_reasons="Stroke reported on follow-up: " + drl.QUALIFIES)],
			TODAY,
		)
		self.assertEqual(rows[0]["tracker"], "SFT-1")
		self.assertTrue(rows[0]["why"].startswith("Stroke reported on follow-up"))

	def test_a_listed_visit_carries_its_rows_reasons_once(self):
		rows = queue_rows(
			[
				visit(
					"T1",
					review_reasons="Severe BP",
					referral_priority=drl.P_IMMEDIATE,
					referral_advised="Yes",
				)
			],
			[
				tracker(
					"SFT-1",
					"T1",
					referral_priority=drl.P_IMMEDIATE,
					review_reasons="Red-flag symptom reported on a follow-up call",
					referral_date="2026-11-19",
				)
			],
			TODAY,
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["why"], "Severe BP; Red-flag symptom reported on a follow-up call")


if __name__ == "__main__":
	unittest.main()
