# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Boundary and scenario tests for drl_v14, the cases Dr Nayanjeet listed under
F on 13-Oct-2026: every BP threshold and mixed reading, normal BP with stroke
symptoms, a severe reading followed by a lower repeat, symptomatic low BP,
missing measurements, new stroke reports and unresolved referrals.

Plain unittest, no frappe: `python3 -m unittest patient_reach.test_drl_v14`
from the repository root.
"""

import json
import unittest
from datetime import date
from pathlib import Path

from patient_reach import drl_v14 as r


def bp(first, repeat=None, red_flags=None, low_symptoms=None):
	return r.assess_bp(first, repeat, red_flags, low_symptoms)


class TestThresholds(unittest.TestCase):
	def test_every_tier_edge(self):
		cases = [
			# reading, status, priority with no repeat and red flags asked (none)
			("119/79", r.NORMAL, r.P_NONE),
			("120/79", r.ELEVATED, r.P_NONE),
			("119/80", r.ELEVATED, r.P_NONE),
			("139/89", r.ELEVATED, r.P_NONE),
			("140/89", r.HIGH, r.P_REPEAT),
			("139/90", r.HIGH, r.P_REPEAT),
			("159/99", r.HIGH, r.P_REPEAT),
			("160/88", r.HIGH_PRIORITY, r.P_HIGH),
			("150/100", r.HIGH_PRIORITY, r.P_HIGH),
			("179/119", r.HIGH_PRIORITY, r.P_HIGH),
			("180/90", r.SEVERE, r.P_IMMEDIATE),
			("140/120", r.SEVERE, r.P_IMMEDIATE),
			("90/60", r.NORMAL, r.P_NONE),
			("89/60", r.LOW, r.P_REPEAT),
			("90/59", r.LOW, r.P_REPEAT),
			("88/70", r.LOW, r.P_REPEAT),
		]
		for reading, status, priority in cases:
			with self.subTest(reading=reading):
				got = bp(reading, red_flags=r.RF_NONE)
				self.assertEqual((got["status"], got["priority"]), (status, priority))

	def test_draft_worked_examples(self):
		"""Section 1's table of Draft 0.1, no symptoms."""
		self.assertEqual(bp("158/98")["alerts"], ["High BP"])
		self.assertEqual(bp("160/88")["alerts"], ["High Priority BP"])
		self.assertEqual(bp("150/100")["alerts"], ["High Priority BP"])
		self.assertEqual(bp("179/119")["alerts"], ["High Priority BP"])
		self.assertEqual(bp("180/90")["alerts"], ["Severe BP"])
		self.assertEqual(bp("140/122")["alerts"], ["Severe BP"])
		self.assertEqual(bp("88/70")["alerts"], ["Low Systolic BP"])
		self.assertEqual(bp("124/78")["alerts"], [])

	def test_separators_and_prose(self):
		self.assertEqual(bp("165 / 95")["status"], r.HIGH_PRIORITY)
		self.assertEqual(bp("165-95")["status"], r.HIGH_PRIORITY)
		self.assertEqual(bp("BP 165\\95 left arm")["status"], r.HIGH_PRIORITY)


class TestMixedReadings(unittest.TestCase):
	def test_his_example_170_55_shows_both(self):
		got = bp("170/55")
		self.assertEqual(got["alerts"], ["High Priority BP", "Low Diastolic BP"])
		self.assertEqual(got["status"], r.HIGH_PRIORITY)
		self.assertEqual(got["priority"], r.P_HIGH)
		self.assertEqual(len(got["actions"]), 2)
		self.assertTrue(got["actions"][0].startswith("High-priority BP"))

	def test_low_never_overrides_high(self):
		for reading, alerts in (
			("150/55", ["High BP", "Low Diastolic BP"]),
			("185/55", ["Severe BP", "Low Diastolic BP"]),
			# 85/95 was here: diastolic above systolic is now an invalid reading (27-Oct, a).
		):
			with self.subTest(reading=reading):
				self.assertEqual(bp(reading)["alerts"], alerts)

	def test_more_urgent_action_leads(self):
		got = bp("185/55", low_symptoms="No")
		self.assertTrue(got["actions"][0].startswith("Severe BP"))
		self.assertEqual(got["priority"], r.P_IMMEDIATE)


class TestRepeatReadings(unittest.TestCase):
	def test_severe_then_lower_repeat_stays_severe(self):
		got = bp("190/100", "150/90", red_flags=r.RF_NONE)
		self.assertEqual(got["status"], r.SEVERE)
		self.assertEqual(got["alerts"], ["Severe BP"])
		self.assertEqual(got["priority"], r.P_IMMEDIATE)
		self.assertIn("does not lift", got["actions"][0])

	def test_severe_without_repeat_asks_for_one_but_never_waits(self):
		action = bp("190/100", red_flags=r.RF_NONE)["actions"][0]
		self.assertIn("Repeat the BP", action)
		self.assertIn("Do not delay the assessment", action)

	def test_severe_prompts_red_flags_when_not_asked(self):
		self.assertIn("Ask the red-flag questions", bp("190/100")["actions"][0])
		self.assertNotIn("Ask the red-flag questions", bp("190/100", red_flags=r.RF_NONE)["actions"][0])

	def test_higher_repeat_raises_the_tier(self):
		self.assertEqual(bp("150/95", "185/100")["status"], r.SEVERE)

	def test_high_band_needs_the_repeat_to_refer(self):
		self.assertEqual(bp("150/95")["priority"], r.P_REPEAT)
		self.assertEqual(bp("150/95", "148/92")["priority"], r.P_ROUTINE)
		self.assertEqual(bp("150/95", "138/88")["priority"], r.P_NONE)
		self.assertEqual(bp("150/95", "138/88")["status"], r.HIGH)

	def test_high_priority_with_lower_repeat_keeps_its_priority(self):
		got = bp("165/95", "150/90")
		self.assertEqual((got["status"], got["priority"]), (r.HIGH_PRIORITY, r.P_HIGH))

	def test_unreadable_repeat_is_no_repeat(self):
		self.assertEqual(bp("150/95", "not done")["priority"], r.P_REPEAT)


class TestLowBP(unittest.TestCase):
	def test_symptomatic_low_is_immediate(self):
		got = bp("85/55", low_symptoms="Yes")
		self.assertEqual(got["priority"], r.P_IMMEDIATE)
		self.assertEqual(got["alerts"], ["Low BP (systolic and diastolic)"])

	def test_symptoms_not_recorded_is_asked_not_assumed(self):
		action = bp("85/55")["actions"][0]
		self.assertIn("record the answer", action)
		self.assertNotIn("record the answer", bp("85/55", low_symptoms="No")["actions"][0])

	def test_persistently_low_gets_clinical_review(self):
		self.assertEqual(bp("85/55", "88/58", low_symptoms="No")["priority"], r.P_REVIEW)

	def test_low_on_one_reading_only(self):
		got = bp("85/65", "100/66", low_symptoms="No")
		self.assertEqual(got["priority"], r.P_NONE)
		self.assertEqual(got["alerts"], ["Low Systolic BP"])

	def test_symptomatic_low_with_red_flag_is_emergency(self):
		self.assertEqual(bp("85/55", red_flags=r.RF_PRESENT, low_symptoms="Yes")["priority"], r.P_EMERGENCY)


class TestRedFlags(unittest.TestCase):
	def test_thirteen_items(self):
		self.assertEqual(len(r.RED_FLAGS), 13)
		self.assertEqual(len({f for f, _l in r.RED_FLAGS}), 13)

	def test_normal_bp_with_stroke_symptoms_is_emergency(self):
		status = r.red_flag_status({"rf_face": 1})
		got = bp("118/76", red_flags=status)
		self.assertEqual(got["priority"], r.P_EMERGENCY)
		self.assertEqual(got["actions"][0], r.EMERGENCY_ACTION)
		self.assertEqual(got["status"], r.NORMAL)

	def test_red_flag_with_no_bp_at_all_is_still_emergency(self):
		got = bp("", red_flags=r.RF_PRESENT)
		self.assertEqual((got["status"], got["priority"]), (None, r.P_EMERGENCY))

	def test_emergency_is_never_a_repeat_prompt_first(self):
		got = bp("190/100", red_flags=r.RF_PRESENT)
		self.assertEqual(got["actions"][0], r.EMERGENCY_ACTION)

	def test_unticked_boxes_are_not_a_no(self):
		self.assertIsNone(r.red_flag_status({}))
		self.assertEqual(r.red_flag_status({"rf_none_asked": 1}), r.RF_NONE)

	def test_none_with_a_symptom_is_refused(self):
		self.assertTrue(r.red_flag_errors({"rf_none_asked": 1, "rf_seizure": 1}))
		self.assertTrue(r.red_flag_errors({"rf_other": 1}))
		self.assertFalse(r.red_flag_errors({"rf_other": 1, "rf_other_detail": "sudden collapse"}))


class TestMissingMeasurements(unittest.TestCase):
	def test_blank_bp_is_not_normal(self):
		got = bp("")
		self.assertEqual(got, {"status": None, "alerts": [], "actions": [], "priority": None})
		self.assertIsNone(bp(None)["priority"])

	def test_prose_is_needs_reference_with_no_priority(self):
		got = bp("BP machine not working")
		self.assertEqual((got["status"], got["priority"]), (r.NEEDS_REFERENCE, None))

	def test_implausible_numbers_are_not_graded(self):
		self.assertEqual(bp("400/90")["status"], r.NEEDS_REFERENCE)


class TestEvents(unittest.TestCase):
	def test_documented_or_reported_stroke_qualifies(self):
		for source in (r.SRC_DOCUMENTED, r.SRC_REPORTED):
			with self.subTest(source=source):
				self.assertEqual(r.event_level_4({"event_type": r.EV_STROKE, "source": source}), r.QUALIFIES)

	def test_every_a8_event_qualifies_not_only_stroke(self):
		for kind in (r.EV_HEART_ATTACK, r.EV_ANGIOPLASTY, r.EV_BYPASS):
			with self.subTest(kind=kind):
				self.assertTrue(r.event_qualifies({"event_type": kind, "source": r.SRC_REPORTED}))

	def test_no_source_paralysis_and_other_stay_pending(self):
		self.assertEqual(r.event_level_4({"event_type": r.EV_STROKE}), r.PENDING)
		self.assertEqual(r.event_level_4({"event_type": r.EV_UNCLEAR, "source": r.SRC_REPORTED}), r.PENDING)
		self.assertEqual(r.event_level_4({"event_type": r.EV_OTHER, "source": r.SRC_DOCUMENTED}), r.PENDING)

	def test_tia(self):
		diagnosed = {"event_type": r.EV_TIA, "source": r.SRC_REPORTED, "tia_diagnosis": r.TIA_DIAGNOSED}
		self.assertEqual(r.event_level_4(diagnosed), r.QUALIFIES_TIA)
		self.assertTrue(r.event_qualifies(diagnosed))
		unverified = dict(diagnosed, tia_diagnosis=r.TIA_UNVERIFIED)
		self.assertEqual(r.event_level_4(unverified), r.PENDING)
		self.assertEqual(r.event_level_4(dict(diagnosed, tia_diagnosis=None)), r.PENDING)

	def test_suspected_recent_tia_is_an_emergency(self):
		# 27-Oct (d): whatever the Prevention Level, and also for resolved
		# weakness not yet clarified.
		for kind in (r.EV_TIA, r.EV_UNCLEAR):
			actions = r.event_actions({"event_type": kind, "timing": r.RECENT})
			self.assertEqual(actions[0][0], r.P_EMERGENCY)
			self.assertIn("Do not change the Prevention Level", actions[0][1])

	def test_symptoms_happening_now_are_an_emergency(self):
		actions = r.event_actions({"event_type": r.EV_STROKE, "timing": r.NOW, "source": r.SRC_REPORTED})
		self.assertEqual(actions, [(r.P_EMERGENCY, r.EMERGENCY_ACTION)])

	def test_paralysis_prompts_questions(self):
		actions = r.event_actions({"event_type": r.EV_UNCLEAR})
		self.assertIn("Do not record a stroke", actions[0][1])


class TestVisit(unittest.TestCase):
	def test_events_add_their_actions_and_priority(self):
		values = {"bp_reading": "118/76", "rf_none_asked": 1}
		got = r.assess_visit(values, [{"event_type": r.EV_TIA, "timing": r.RECENT}])
		self.assertEqual(got["priority"], r.P_EMERGENCY)
		self.assertEqual(got["status"], r.NORMAL)
		self.assertTrue(got["actions"][0].startswith("Suspected recent TIA"))
		self.assertEqual(got["red_flag_status"], r.RF_NONE)

	def test_emergency_is_listed_once(self):
		values = {"bp_reading": "190/100", "rf_face": 1}
		got = r.assess_visit(values, [{"event_type": r.EV_STROKE, "timing": r.NOW, "source": r.SRC_REPORTED}])
		self.assertEqual(got["actions"].count(r.EMERGENCY_ACTION), 1)
		self.assertEqual(got["actions"][0], r.EMERGENCY_ACTION)

	def test_nothing_recorded(self):
		self.assertEqual(
			r.assess_visit({}, []),
			{"status": None, "alerts": [], "actions": [], "priority": None, "red_flag_status": None},
		)


class TestLevel4(unittest.TestCase):
	def test_new_stroke_report_locks_level_4(self):
		visits = [
			{
				"name": "TKT-1",
				"prevention_level": "Level 2",
				"events": [{"event_type": r.EV_STROKE, "source": r.SRC_REPORTED}],
			}
		]
		self.assertEqual(r.level_4_sources(visits, [], set()), ["Stroke recorded on TKT-1"])

	def test_earlier_level_4_stays(self):
		visits = [{"name": "TKT-1", "prevention_level": "Level 4s", "events": []}]
		self.assertEqual(r.level_4_sources(visits, [], set()), ["Level 4 recorded on TKT-1"])

	def test_event_reported_on_a_follow_up_call(self):
		events = [{"parent": "SFT-00001", "event_type": r.EV_HEART_ATTACK, "source": r.SRC_REPORTED}]
		self.assertEqual(
			r.level_4_sources([], events, set()),
			["Heart attack (myocardial infarction) recorded on SFT-00001"],
		)

	def test_pending_events_do_not_lock(self):
		visits = [
			{
				"name": "TKT-1",
				"prevention_level": "Level 2",
				"events": [{"event_type": r.EV_UNCLEAR, "source": r.SRC_REPORTED}],
			}
		]
		self.assertEqual(r.level_4_sources(visits, [], set()), [])

	def test_only_a_reviewer_correction_lifts_it(self):
		visits = [{"name": "TKT-1", "prevention_level": "Level 4", "events": []}]
		self.assertEqual(r.level_4_sources(visits, [], {"TKT-1"}), [])

	def test_level_and_s_are_separate(self):
		self.assertEqual(r.prevention_code("Level 2", "Yes"), "Level 2s")
		self.assertEqual(r.prevention_code("Level 2", "No"), "Level 2")
		self.assertEqual(r.prevention_code("Level 2", None), "Level 2")
		self.assertIsNone(r.prevention_code(None, "Yes"))

	def test_note_names_the_reviewer(self):
		self.assertIn("Sparsh Clinical Reviewer role", r.level_4_note(["Stroke recorded on TKT-1"]))
		self.assertIsNone(r.level_4_note([]))


class TestReviewReasons(unittest.TestCase):
	def test_reasons(self):
		values = {"red_flag_status": r.RF_PRESENT, "bp_status": r.SEVERE}
		self.assertEqual(r.review_reasons(values, [], []), ["Red-flag emergency", "Severe BP"])

	def test_symptomatic_low(self):
		values = {"bp_status": r.LOW, "bp_alerts": ["Low Systolic BP"], "low_bp_symptoms": "Yes"}
		self.assertEqual(r.review_reasons(values, [], []), ["Symptomatic low BP"])

	def test_stroke_in_free_text_without_an_event(self):
		values = {"any_other_medical_condition": "Had a stroke in 2021"}
		self.assertEqual(
			r.review_reasons(values, [], []), ["Stroke or paralysis mentioned, but no event recorded"]
		)
		events = [{"event_type": r.EV_STROKE, "source": r.SRC_REPORTED}]
		self.assertEqual(r.review_reasons(values, events, []), [f"Stroke: {r.QUALIFIES}"])

	def test_dementia_is_not_a_tia(self):
		self.assertEqual(r.review_reasons({"any_other_medical_condition": "dementia"}, [], []), [])

	def test_heart_attack_ticked_without_an_event(self):
		conditions = [{"condition": "Heart Attack", "has_disease": 1}]
		self.assertEqual(
			r.review_reasons({}, [], conditions),
			["Heart Attack ticked under Medical Condition, but no event recorded"],
		)

	def test_nothing_to_review(self):
		self.assertEqual(r.review_reasons({"bp_status": r.HIGH}, [], []), [])


class TestReferralFollowThrough(unittest.TestCase):
	TODAY = date(2026, 11, 20)

	def row(self, **values):
		base = {"referral_priority": r.P_HIGH, "referral_date": "2026-11-01"}
		base.update(values)
		return base

	def test_unresolved_high_priority_referral(self):
		self.assertEqual(
			r.referral_flags(self.row(), self.TODAY),
			[
				"Consultation not recorded 19 days after referral",
				"Day-3 call not made",
				"Treatment not recorded as started after 14 days",
			],
		)

	def test_no_answer_does_not_close_it(self):
		flags = r.referral_flags(
			self.row(follow_up_status="No Response", call_1_actual_date="2026-11-04"), self.TODAY
		)
		self.assertIn("Follow-up ended (No Response) with the referral still open", flags)

	def test_consulted_and_taking(self):
		row = self.row(
			consultation_status=r.CONSULTED, treatment_status=r.T_TAKING, call_1_actual_date="2026-11-04"
		)
		self.assertEqual(r.referral_flags(row, self.TODAY), [])

	def test_not_known_is_not_started(self):
		row = self.row(
			consultation_status=r.CONSULTED, treatment_status=r.T_NOT_KNOWN, call_1_actual_date="2026-11-04"
		)
		self.assertEqual(
			r.referral_flags(row, self.TODAY), ["Treatment not recorded as started after 14 days"]
		)

	def test_not_prescribed_is_not_flagged(self):
		row = self.row(
			consultation_status=r.CONSULTED,
			treatment_status=r.T_NOT_PRESCRIBED,
			call_1_actual_date="2026-11-04",
		)
		self.assertEqual(r.referral_flags(row, self.TODAY), [])

	def test_only_a_disposition_closes_it(self):
		self.assertEqual(r.referral_flags(self.row(referral_disposition=r.D_DECLINED), self.TODAY), [])

	def test_within_the_window_nothing_is_flagged(self):
		self.assertEqual(r.referral_flags(self.row(referral_date="2026-11-19"), self.TODAY), [])
		self.assertEqual(r.referral_flags(self.row(referral_date="2026-11-18"), self.TODAY), [])
		self.assertEqual(
			r.referral_flags(self.row(referral_date="2026-11-17"), self.TODAY),
			["Consultation not recorded 3 days after referral"],
		)

	def test_routine_referral_has_four_weeks(self):
		row = self.row(referral_priority=r.P_ROUTINE)
		self.assertEqual(r.referral_flags(row, self.TODAY), [])
		self.assertEqual(
			r.referral_flags(row, date(2026, 11, 30)), ["Consultation not recorded 29 days after referral"]
		)

	def test_missing_referral_date_is_said(self):
		self.assertEqual(
			r.referral_flags(self.row(referral_date=None), self.TODAY), ["Referral date not recorded"]
		)

	def test_no_referral_no_flags(self):
		self.assertEqual(r.referral_flags({"referral_priority": r.P_NONE}, self.TODAY), [])
		self.assertEqual(r.referral_flags({}, self.TODAY), [])

	def test_day_3_call_date(self):
		self.assertEqual(r.referral_call_date(r.P_HIGH, "2026-11-01"), date(2026, 11, 4))
		self.assertIsNone(r.referral_call_date(r.P_ROUTINE, "2026-11-01"))
		self.assertIsNone(r.referral_call_date(r.P_HIGH, None))

	def test_dispositions(self):
		self.assertTrue(r.disposition_errors({"referral_disposition": r.D_COMPLETED}, False))
		self.assertFalse(
			r.disposition_errors(
				{"referral_disposition": r.D_COMPLETED, "consultation_status": r.CONSULTED}, False
			)
		)
		self.assertTrue(r.disposition_errors({"referral_disposition": r.D_REVIEWER}, False))
		self.assertFalse(r.disposition_errors({"referral_disposition": r.D_REVIEWER}, True))


HERE = Path(__file__).parent
DOCTYPE = HERE / "patient_reach" / "doctype"


class TestClarifications27Oct(unittest.TestCase):
	"""Dr Nayanjeet's test list of 27-Oct-2026 (h), one test per item."""

	TODAY = date(2026, 11, 20)

	def test_independent_or_logic(self):
		self.assertEqual(bp("160/90")["status"], r.HIGH_PRIORITY)
		self.assertEqual(bp("150/100")["status"], r.HIGH_PRIORITY)
		self.assertEqual(bp("180/110")["status"], r.SEVERE)
		self.assertEqual(bp("170/120")["status"], r.SEVERE)

	def test_low_bp(self):
		self.assertEqual((bp("89/70")["status"], bp("89/70")["alerts"]), (r.LOW, ["Low Systolic BP"]))
		got = bp("100/59")
		self.assertEqual((got["status"], got["alerts"]), (r.LOW, ["Low Diastolic BP"]))

	def test_150_50_is_low_headline(self):
		self.assertEqual(bp("150/50")["status"], r.LOW)

	def test_mixed_categories_more_urgent_leads(self):
		got = bp("170/50")
		self.assertEqual((got["status"], got["alerts"]), (r.HIGH_PRIORITY, ["High Priority BP", "Low Diastolic BP"]))
		got = bp("185/50")
		self.assertEqual((got["status"], got["alerts"]), (r.SEVERE, ["Severe BP", "Low Diastolic BP"]))

	def test_diastolic_at_or_above_systolic_is_invalid(self):
		for reading in ("90/100", "100/100"):
			got = bp(reading)
			self.assertEqual(got["status"], r.INVALID)
			self.assertEqual(got["alerts"], ["Invalid reading"])
			self.assertEqual(got["priority"], r.P_REPEAT)
			self.assertIn("Remeasure the BP now", got["actions"][0])

	def test_invalid_first_reading_grades_the_valid_repeat(self):
		got = bp("90/100", "182/100")
		self.assertEqual(got["status"], r.SEVERE)
		self.assertIn("Invalid reading", got["alerts"])

	def test_invalid_repeat_is_not_graded(self):
		got = bp("128/84", "80/95")
		self.assertEqual(got["status"], r.ELEVATED)
		self.assertIn("Invalid reading", got["alerts"])

	def test_invalid_reading_with_red_flag_is_still_emergency(self):
		got = bp("90/100", red_flags=r.RF_PRESENT)
		self.assertEqual((got["status"], got["priority"]), (r.INVALID, r.P_EMERGENCY))

	def test_narrow_pulse_pressure_is_graded(self):
		# No threshold for "narrow" until validated: 110/100 is a valid reading.
		got = bp("110/100")
		self.assertEqual(got["status"], r.HIGH_PRIORITY)
		self.assertNotIn("Invalid reading", got["alerts"])

	def test_red_flag_with_normal_bp(self):
		got = bp("118/76", "116/74", red_flags=r.RF_PRESENT)
		self.assertEqual((got["status"], got["priority"]), (r.NORMAL, r.P_EMERGENCY))
		self.assertEqual(got["actions"][0], r.EMERGENCY_ACTION)

	def test_severe_then_lower_repeat_stays_visible(self):
		got = bp("184/112", "150/92")
		self.assertEqual((got["status"], got["priority"]), (r.SEVERE, r.P_IMMEDIATE))
		self.assertIn("A lower repeat reading does not lift this alert", got["actions"][0])

	def test_confirmed_versus_suspected_tia(self):
		confirmed = {"event_type": r.EV_TIA, "source": r.SRC_DOCUMENTED, "tia_diagnosis": r.TIA_DIAGNOSED}
		self.assertTrue(r.event_qualifies(confirmed))
		self.assertNotIn("pending", r.event_level_4(confirmed).lower())
		suspected = dict(confirmed, tia_diagnosis=r.TIA_UNVERIFIED, timing=r.RECENT)
		self.assertFalse(r.event_qualifies(suspected))
		self.assertEqual(r.level_4_sources([{"name": "TKT-1", "events": [suspected]}], [], set()), [])
		self.assertEqual(r.event_actions(suspected)[0][0], r.P_EMERGENCY)

	def test_level_4_persists_and_authorised_correction_lifts_it(self):
		visits = [{"name": "TKT-1", "prevention_level": "Level 4", "events": []}]
		self.assertEqual(r.level_4_sources(visits, [], set()), ["Level 4 recorded on TKT-1"])
		self.assertEqual(r.level_4_sources(visits, [], {"TKT-1"}), [])

	def test_emergency_and_immediate_consultation_flag_after_24_hours(self):
		for priority in (r.P_EMERGENCY, r.P_IMMEDIATE):
			row = {"referral_priority": priority, "referral_date": "2026-11-20"}
			self.assertEqual(r.referral_flags(row, self.TODAY), [])
			row["referral_date"] = "2026-11-19"
			self.assertEqual(r.referral_flags(row, self.TODAY), ["Consultation not recorded 1 days after referral"])

	def test_low_bp_review_has_no_fixed_deadline(self):
		row = {"referral_priority": r.P_REVIEW, "referral_date": "2026-09-01"}
		self.assertEqual(r.referral_flags(row, self.TODAY), [])
		self.assertEqual(r.referral_flags(dict(row, follow_up_status="Closed"), self.TODAY),
			["Follow-up ended (Closed) with the referral still open"])

	def test_missing_follow_up_documentation(self):
		row = {"referral_priority": r.P_HIGH, "referral_date": "2026-11-01"}
		self.assertEqual(
			r.referral_flags(row, self.TODAY),
			[
				"Consultation not recorded 19 days after referral",
				"Day-3 call not made",
				"Treatment not recorded as started after 14 days",
			],
		)
		self.assertEqual(r.referral_flags(dict(row, referral_date=None), self.TODAY), ["Referral date not recorded"])


def _fields(doctype):
	folder = doctype.lower().replace(" ", "_").replace("-", "_")
	data = json.loads((DOCTYPE / folder / f"{folder}.json").read_text())
	return data, {f["fieldname"]: f for f in data["fields"]}


def _options(field):
	return [o for o in (field.get("options") or "").split("\n") if o]


class TestFormsAgreeWithTheRules(unittest.TestCase):
	"""A Select holding a value it does not offer raises nothing and shows
	blank, so every string the rules write must be one of its options."""

	def test_ticket_selects(self):
		_data, f = _fields("Ticket")
		for status in (r.SEVERE, r.HIGH_PRIORITY, r.HIGH, r.ELEVATED, r.NORMAL, r.LOW, r.NEEDS_REFERENCE, r.INVALID):
			self.assertIn(status, _options(f["bp_status"]))
		self.assertEqual(_options(f["referral_priority"]), list(r.PRIORITIES))
		self.assertEqual(_options(f["red_flag_status"]), [r.RF_PRESENT, r.RF_NONE])
		self.assertEqual(_options(f["level"]), list(r.LEVELS))
		self.assertEqual(_options(f["s_modifier"]), [r.S_YES, "No"])
		self.assertEqual(
			[k for k, _l in r.RED_FLAGS] + [r.RED_FLAG_NONE],
			[k for k in f if k.startswith("rf_") and k != "rf_other_detail"],
		)
		self.assertEqual(f["bp_rule"]["default"], r.RULE)

	def test_event_selects(self):
		_data, f = _fields("Sparsh Health Event")
		self.assertEqual(_options(f["event_type"]), list(r.EVENT_TYPES))
		self.assertEqual(_options(f["source"]), [r.SRC_DOCUMENTED, r.SRC_REPORTED])
		self.assertEqual(_options(f["tia_diagnosis"]), [r.TIA_DIAGNOSED, r.TIA_UNVERIFIED])
		self.assertEqual(_options(f["timing"]), [r.NOW, r.RECENT, r.PAST])
		self.assertIn(r.EV_TIA, f["tia_diagnosis"]["depends_on"])

	def test_tracker_selects(self):
		_data, f = _fields("Sparsh Follow-up Tracker")
		self.assertEqual(_options(f["consultation_status"]), [r.CONSULTED, r.NOT_YET, r.NOT_KNOWN])
		self.assertEqual(_options(f["treatment_status"]), list(r.TREATMENT_STATES))
		self.assertEqual(_options(f["referral_disposition"]), list(r.DISPOSITIONS))
		self.assertEqual(_options(f["follow_up_status"])[-3:], list(r.FINISHED_STATUSES))
		self.assertEqual(f["referral_priority"]["fetch_from"], "baseline_ticket.referral_priority")

	def test_every_new_ticket_field_is_in_the_live_layout(self):
		"""The Visit layout on care is the Property Setter Ticket-main-field_order;
		a field missing from it is appended at the end of the form."""
		data, _f = _fields("Ticket")
		setters = json.loads((HERE / "fixtures" / "property_setter.json").read_text())
		order = json.loads(next(p for p in setters if p["name"] == "Ticket-main-field_order")["value"])
		missing = [name for name in data["field_order"] if name not in order]
		self.assertEqual(missing, [])
		self.assertLess(order.index("red_flag_section"), order.index("bp_heading"))
		self.assertLess(order.index("custom_measurements"), order.index("red_flag_section"))

	def test_old_rule_fields_hide_under_drl(self):
		_data, f = _fields("Ticket")
		for name in ("bp_concerning_symptoms", "bp_escalation_note", "bp_note", "prevention_level"):
			self.assertIn(f"doc.bp_rule!='{r.RULE}'", f[name]["depends_on"])


if __name__ == "__main__":
	unittest.main()
