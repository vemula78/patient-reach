# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Tests for the pure helpers behind the clinical safety review list. No
`frappe.db` access -- they take plain dicts, as in `sparsh_overdue_calls`."""

import datetime
import unittest

from patient_reach.patient_reach.report.sparsh_clinical_safety_review.sparsh_clinical_safety_review import (
	HIGH_PRIORITY,
	SEVERE,
	STROKE,
	bp_band,
	referral_recorded,
	review_rows,
	stroke_word,
)


class TestBpBand(unittest.TestCase):
	def test_boundaries(self):
		for reading, band in (
			("180/80", SEVERE),
			("120/120", SEVERE),
			("179/119", HIGH_PRIORITY),
			("160/80", HIGH_PRIORITY),
			("120/100", HIGH_PRIORITY),
			("159/99", None),
			("170/55", HIGH_PRIORITY),
			("BP machine not working", None),
			("", None),
			(None, None),
		):
			self.assertEqual(bp_band(reading), band, reading)


class TestStrokeWord(unittest.TestCase):
	def test_words(self):
		self.assertEqual(stroke_word("Had a Stroke in 2019"), "stroke")
		self.assertEqual(stroke_word("left side paralysis"), "paraly")
		self.assertEqual(stroke_word("TIA last year"), "tia")
		self.assertIsNone(stroke_word("dementia"))
		self.assertIsNone(stroke_word(None))


class TestReferral(unittest.TestCase):
	def test_blank_is_not_a_no(self):
		self.assertEqual(referral_recorded({}), "Not recorded")
		self.assertEqual(referral_recorded({"none": 1}), "None (ticked)")
		self.assertEqual(
			referral_recorded({"cardiology": 1, "general_medicine_high_bp": 1}),
			"Cardiology, General Medicine (High BP)",
		)


class TestReviewRows(unittest.TestCase):
	def test_selection_order_and_follow_up(self):
		visits = [
			{"name": "V1", "patient_id": "C1", "bp_reading": "150/90", "docstatus": 0},
			{"name": "V2", "patient_id": "C2", "bp_reading": "165/95", "docstatus": 1},
			{"name": "V3", "patient_id": "C3", "bp_reading": "185/100", "bp_repeat_reading": "150/90"},
			{
				"name": "V4",
				"patient_id": "C4",
				"bp_reading": "130/80",
				"any_other_medical_condition": "stroke",
			},
			{
				"name": "V5",
				"patient_id": "C5",
				"bp_reading": "200/110",
				"any_other_medical_condition": "paralysed",
			},
		]
		trackers = {
			"C2": {
				"follow_up_status": "Follow-up 2",
				"call_1_actual_date": datetime.date(2026, 10, 1),
				"call_1_outcome": "Connected",
			}
		}
		rows = review_rows(visits, trackers)
		self.assertEqual([r["name"] for r in rows], ["V3", "V5", "V2", "V4"])
		self.assertEqual(rows[1]["reason"], f"{SEVERE}; {STROKE}")
		# A lower repeat keeps the severe visit on the list, both readings shown.
		self.assertEqual((rows[0]["bp_reading"], rows[0]["bp_repeat_reading"]), ("185/100", "150/90"))
		self.assertEqual(rows[2]["last_call_outcome"], "Connected")
		self.assertEqual(rows[3]["follow_up_status"], "No follow-up record")
		self.assertEqual(rows[3]["prevention_level"], "Not recorded")
		self.assertEqual(rows[3]["symptoms"], "Not ticked")
