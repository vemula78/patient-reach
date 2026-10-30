# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""Tests for the Sparsh Follow-up Tracker rules.

`UnitTestCase` and nothing written to the database, for the reason given in
`test_ticket.py`. What is pinned:

1. **Who is on the list**: interested OR ready to change (Yes or May be).
2. **Calls 2 and 3 open only on Yes / May be**, and a Next Follow-up Date needs
   one. `depends_on` and `read_only_depends_on` are client-side only, so an API
   save or an import would otherwise get past both.
3. **The chained Scheduled Dates and the list's Next Call Due.**
4. **The JSON agrees with the code**: the interest options are what GOING_ON
   assumes, the call sections' conditions name the right field, and Call
   Outcome carries the renamed option.
5. **The Ticket hooks are registered** under document methods that exist: a
   `doc_events` key naming no method is ignored in silence.
6. **A visit whose caregiver is changed releases the previous caregiver's
   tracker** (SFT-00085, 09-Oct-2026), with the database calls patched out.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from frappe.tests import UnitTestCase

from patient_reach import drl_v14 as drl
from patient_reach import hooks
from patient_reach.doc_events import _release_previous_caregivers_tracker, ticket_sync_follow_up_tracker
from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
	FINISHED,
	GOING_ON,
	NOT_CONNECTED_FIELDS,
	any_call_entry,
	call_is_open,
	chained_schedule,
	check_acceptance,
	check_calls,
	is_eligible,
	latest_eligible_visit,
	missing_when_not_connected,
	next_call_due,
	prepopulate_prevention_levels,
	review_reasons,
)

META = json.loads((Path(__file__).parent / "sparsh_follow_up_tracker.json").read_text())
FIELDS = {f["fieldname"]: f for f in META["fields"]}


class TestEligibility(UnitTestCase):
	def test_either_answer_puts_the_caregiver_on_the_list(self):
		self.assertTrue(is_eligible("Yes", "No"))
		self.assertTrue(is_eligible("No", "Yes"))
		self.assertTrue(is_eligible("", "May be"))
		self.assertTrue(is_eligible("Yes", "Yes"))

	def test_neither_keeps_them_off(self):
		self.assertFalse(is_eligible("No", "No"))
		self.assertFalse(is_eligible("", ""))
		self.assertFalse(is_eligible(None, None))

	def test_a_referral_puts_the_caregiver_on_the_list_whatever_their_interest(self):
		"""DRL v1.4: a referral is followed through (Dr Nayanjeet, 13-Oct-2026, C)."""
		for priority in drl.REFERRAL_PRIORITIES:
			with self.subTest(priority=priority):
				self.assertTrue(is_eligible("No", "No", priority))
		self.assertFalse(is_eligible("No", "No", drl.P_REPEAT))
		self.assertFalse(is_eligible("No", "No", drl.P_NONE))
		self.assertTrue(
			latest_eligible_visit([dict(_visit("TKT-3", "No", "No"), referral_priority=drl.P_HIGH)])
		)

	def test_finished_statuses_agree_with_the_rules(self):
		self.assertEqual(FINISHED, drl.FINISHED_STATUSES)


class TestDay3Call(UnitTestCase):
	def test_day_3_comes_first_when_earlier(self):
		values = {"call_1_scheduled_date": "2026-11-20", "referral_call_date": "2026-11-04"}
		self.assertEqual(next_call_due(values), "2026-11-04")

	def test_scheduled_date_when_earlier(self):
		values = {"call_1_scheduled_date": "2026-11-02", "referral_call_date": "2026-11-04"}
		self.assertEqual(next_call_due(values), "2026-11-02")

	def test_day_3_without_a_follow_up_date(self):
		self.assertEqual(next_call_due({"referral_call_date": "2026-11-04"}), "2026-11-04")

	def test_only_call_1(self):
		values = {
			"call_1_actual_date": "2026-11-04",
			"call_1_interest": "Yes",
			"call_2_scheduled_date": "2026-11-30",
			"referral_call_date": "2026-11-04",
		}
		self.assertEqual(next_call_due(values), "2026-11-30")


STROKE = {"event_type": drl.EV_STROKE, "source": drl.SRC_REPORTED}


class TestTrackerReviewReasons(UnitTestCase):

	def test_event_on_a_call_and_a_level_4_discrepancy(self):
		self.assertEqual(
			review_reasons({}, [STROKE], "Level 2"),
			[
				f"Stroke reported on follow-up: {drl.QUALIFIES}",
				"Level 4 event on the follow-up list; the visit shows Level 2",
			],
		)

	def test_no_discrepancy_when_the_visit_is_level_4(self):
		self.assertEqual(
			review_reasons({}, [STROKE], "Level 4s"), [f"Stroke reported on follow-up: {drl.QUALIFIES}"]
		)

	def test_red_flag_on_a_call(self):
		self.assertEqual(
			review_reasons({"call_red_flag": 1}, [], "Level 1"),
			["Red-flag symptom reported on a follow-up call"],
		)

	def test_nothing(self):
		self.assertEqual(review_reasons({}, [], None), [])


class TestCallRules(UnitTestCase):
	def test_next_date_needs_yes_or_may_be(self):
		self.assertEqual(check_calls({"call_1_interest": "Yes", "call_1_next_date": "2026-10-20"}), [])
		self.assertEqual(check_calls({"call_1_interest": "May be", "call_1_next_date": "2026-10-20"}), [])
		self.assertEqual(len(check_calls({"call_1_interest": "No", "call_1_next_date": "2026-10-20"})), 1)
		self.assertEqual(len(check_calls({"call_1_interest": "Yes", "call_2_next_date": "2026-10-20"})), 1)

	def test_call_two_needs_call_one_going_on(self):
		self.assertEqual(len(check_calls({"call_1_interest": "No", "call_2_notes": "spoke"})), 1)
		self.assertEqual(check_calls({"call_1_interest": "May be", "call_2_notes": "spoke"}), [])

	def test_call_three_needs_call_two_going_on(self):
		values = {"call_1_interest": "Yes", "call_2_interest": "", "call_3_actual_date": "2026-11-01"}
		self.assertEqual(len(check_calls(values)), 1)

	def test_scheduled_dates_chain(self):
		self.assertEqual(
			chained_schedule({"call_1_next_date": "2026-10-20", "call_2_next_date": None}),
			{"call_2_scheduled_date": "2026-10-20", "call_3_scheduled_date": None},
		)

	def test_any_call_entry_ignores_the_system_dates(self):
		self.assertFalse(any_call_entry({"call_1_scheduled_date": "2026-10-20", "follow_up_status": "Follow-up 1"}))
		self.assertTrue(any_call_entry({"call_2_duration": 300}))


class TestChangeRequest2026_10_23(UnitTestCase):
	"""The counselling team's change request of 23-Oct-2026 for the follow-up
	sections: acceptance No closes them, each call carries a Current Prevention
	Level, and a call not connected (or a No) needs every field but the Next
	Follow-up Date."""

	def test_acceptance_no_closes_every_call(self):
		values = {"acceptance_to_change": "No", "call_1_scheduled_date": "2026-10-20"}
		self.assertIsNone(next_call_due(values))
		self.assertEqual(check_acceptance(values), [])
		values["call_1_notes"] = "spoke"
		self.assertEqual(len(check_acceptance(values)), 1)
		self.assertEqual(check_calls(values), [], "no second, misleading interest message")
		self.assertEqual(check_acceptance({"acceptance_to_change": "May be", "call_1_notes": "spoke"}), [])

	def test_prevention_level_carries_forward(self):
		values = {"prevention_level": "Level 2", "call_1_interest": "Yes", "call_2_prevention_level": "Level 3"}
		self.assertEqual(
			prepopulate_prevention_levels(values),
			{"call_1_prevention_level": "Level 2", "call_2_prevention_level": "Level 3"},
		)
		values["call_2_interest"] = "May be"
		self.assertEqual(prepopulate_prevention_levels(values)["call_3_prevention_level"], "Level 3")
		self.assertEqual(prepopulate_prevention_levels({"acceptance_to_change": "No", "prevention_level": "Level 1"}), {})

	def test_connected_and_interested_needs_nothing_more(self):
		self.assertEqual(missing_when_not_connected({"call_1_outcome": "Connected", "call_1_interest": "Yes"}), [])
		self.assertEqual(missing_when_not_connected({}), [], "a blank outcome is not yet entered")

	def test_not_connected_needs_every_field_but_the_next_date(self):
		errors = missing_when_not_connected({"call_1_outcome": "Wrong Number"})
		self.assertEqual(len(errors), 1)
		for field in NOT_CONNECTED_FIELDS:
			self.assertIn(field, errors[0])
		self.assertNotIn("next_date", errors[0])
		full = {f"call_1_{f}": "x" for f in NOT_CONNECTED_FIELDS}
		self.assertEqual(missing_when_not_connected({**full, "call_1_outcome": "Wrong Number"}), [])

	def test_a_no_needs_every_field_even_when_connected(self):
		self.assertEqual(len(missing_when_not_connected({"call_1_outcome": "Connected", "call_1_interest": "No"})), 1)

	def test_call_three_has_no_interest_to_require(self):
		values = {"call_1_interest": "Yes", "call_2_interest": "Yes", "call_3_outcome": "Caregiver Declined"}
		errors = missing_when_not_connected(values)
		self.assertEqual(len(errors), 1)
		self.assertNotIn("interest", errors[0])

	def test_closed_calls_are_not_checked(self):
		full = {f"call_1_{f}": "x" for f in NOT_CONNECTED_FIELDS}
		values = {**full, "call_1_interest": "No", "call_2_outcome": "Wrong Number"}
		self.assertEqual(missing_when_not_connected(values), [])

	def test_json_requires_the_same_fields(self):
		for n in (1, 2, 3):
			self.assertEqual(FIELDS[f"call_{n}_prevention_level"]["label"], "Current Prevention Level")
			for f in NOT_CONNECTED_FIELDS:
				if n == 3 and f == "interest":
					continue
				self.assertIn(f"doc.call_{n}_outcome != 'Connected'", FIELDS[f"call_{n}_{f}"]["mandatory_depends_on"])
			self.assertNotIn("mandatory_depends_on", FIELDS.get(f"call_{n}_next_date", {}))


class TestChangeRequest2026_10_29(UnitTestCase):
	"""The change request of 29-Oct-2026: a call that did not connect opens no
	further call, even with a Yes or May be; the list shows Status once."""

	def test_a_call_that_did_not_connect_opens_no_further_call(self):
		values = {"call_1_outcome": "No Answer After 3 Attempts", "call_1_interest": "May be"}
		self.assertFalse(call_is_open(values, 2))
		self.assertIsNone(next_call_due({**values, "call_1_actual_date": "2026-10-10", "call_2_scheduled_date": "2026-10-24"}))
		self.assertEqual(prepopulate_prevention_levels({**values, "prevention_level": "Level 2"}), {"call_1_prevention_level": "Level 2"})
		values = {"call_1_interest": "Yes", "call_2_outcome": "Wrong Number", "call_2_interest": "Yes"}
		self.assertTrue(call_is_open(values, 2))
		self.assertFalse(call_is_open(values, 3))

	def test_connected_or_not_yet_entered_opens_the_next_call(self):
		self.assertTrue(call_is_open({"call_1_outcome": "Connected", "call_1_interest": "Yes"}, 2))
		self.assertTrue(call_is_open({"call_1_interest": "May be"}, 2))
		self.assertFalse(call_is_open({"call_1_outcome": "Connected", "call_1_interest": "No"}, 2))

	def test_a_call_already_entered_stays_open(self):
		"""SFT-00616, -00652, -00955 on care, 30-Oct-2026."""
		values = {"call_1_outcome": "No Answer After 3 Attempts", "call_1_interest": "Yes", "call_2_notes": "spoke"}
		self.assertTrue(call_is_open(values, 2))
		self.assertEqual(check_calls(values), [])

	def test_json_sections_follow_the_outcome(self):
		for n in (2, 3):
			depends_on = FIELDS[f"call_{n}_section"]["depends_on"]
			self.assertIn(f"doc.call_{n - 1}_outcome == 'Connected'", depends_on)
			for f in ("actual_date", "duration", "outcome", "by", "notes"):
				self.assertIn(f"'{f}'", depends_on)
			self.assertIn(f"doc['call_{n}_' + f]", depends_on)

	def test_status_is_shown_once_on_the_list(self):
		"""The coloured Status column stays; the Follow-up Status column goes, and
		the field is filtered and sorted as Status."""
		self.assertEqual(FIELDS["follow_up_status"]["label"], "Status")
		self.assertFalse(FIELDS["follow_up_status"].get("in_list_view"))
		self.assertEqual(FIELDS["follow_up_status"].get("in_standard_filter"), 1)
		self.assertEqual(FIELDS["follow_up_status"].get("reqd"), 1, "a reqd field is offered by the sort selector")


class TestNextCallDue(UnitTestCase):
	def test_first_call_not_made(self):
		self.assertEqual(next_call_due({"call_1_scheduled_date": "2026-10-10"}), "2026-10-10")

	def test_moves_to_call_two_when_going_on(self):
		values = {"call_1_actual_date": "2026-10-10", "call_1_interest": "Yes", "call_2_scheduled_date": "2026-10-24"}
		self.assertEqual(next_call_due(values), "2026-10-24")

	def test_stops_when_not_going_on_or_closed(self):
		self.assertIsNone(next_call_due({"call_1_actual_date": "2026-10-10", "call_1_interest": "No"}))
		self.assertIsNone(next_call_due({"call_1_scheduled_date": "2026-10-10", "follow_up_status": "Closed"}))

	def test_no_call_due_once_not_interested_or_no_response(self):
		"""The counselling team's two statuses (09-Oct-2026) end the follow-up as Closed does."""
		for status in ("Not Interested", "No Response"):
			values = {"call_1_scheduled_date": "2026-10-10", "follow_up_status": status}
			self.assertIsNone(next_call_due(values))

	def test_blank_when_the_visit_has_no_follow_up_date(self):
		self.assertIsNone(next_call_due({}))


class TestJsonMatchesCode(UnitTestCase):
	def test_interest_options(self):
		for n in (1, 2):
			options = [o for o in FIELDS[f"call_{n}_interest"]["options"].split("\n") if o]
			self.assertEqual(options, ["Yes", "No", "May be"])
			self.assertTrue(set(GOING_ON) <= set(options))
		self.assertNotIn("call_3_interest", FIELDS)
		self.assertNotIn("call_3_next_date", FIELDS)

	def test_sections_open_on_the_previous_interest(self):
		self.assertEqual(FIELDS["call_1_section"]["depends_on"], "eval:doc.acceptance_to_change != 'No'")
		for n in (2, 3):
			self.assertIn(f"doc.call_{n - 1}_interest", FIELDS[f"call_{n}_section"]["depends_on"])
			self.assertIn("doc.acceptance_to_change != 'No'", FIELDS[f"call_{n}_section"]["depends_on"])
		for n in (1, 2):
			self.assertIn(f"doc.call_{n}_interest", FIELDS[f"call_{n}_next_date"]["read_only_depends_on"])

	def test_call_outcome_option_renamed(self):
		for n in (1, 2, 3):
			options = FIELDS[f"call_{n}_outcome"]["options"].split("\n")
			self.assertIn("No Answer After 3 Attempts", options)
			self.assertNotIn("No Answer", options)

	def test_status_options(self):
		options = FIELDS["follow_up_status"]["options"].split("\n")
		self.assertEqual(
			options, ["Follow-up 1", "Follow-up 2", "Follow-up 3", "Not Interested", "No Response", "Closed"]
		)
		self.assertTrue(set(FINISHED) <= set(options))
		list_js = (Path(__file__).parent / "sparsh_follow_up_tracker_list.js").read_text()
		for status in FINISHED:
			self.assertIn(f'"{status}"', list_js)

	def test_scheduled_dates_are_not_editable(self):
		for n in (1, 2, 3):
			self.assertEqual(FIELDS[f"call_{n}_scheduled_date"].get("read_only"), 1)
		self.assertEqual(FIELDS["call_1_scheduled_date"]["fetch_from"], "baseline_ticket.follow_up_date")

	def test_one_tracker_per_caregiver(self):
		self.assertEqual(FIELDS["caregiver_id"].get("unique"), 1)

	def test_list_shows_the_follow_up_id(self):
		"""Counsellors copy the SFT- ID into the Health4All app (08-Oct-2026)."""
		list_js = (Path(__file__).parent / "sparsh_follow_up_tracker_list.js").read_text()
		self.assertNotIn("hide_name_column", list_js)

	def test_counsellors_cannot_create(self):
		volunteer = next(p for p in META["permissions"] if p["role"] == "Volunteer")
		self.assertFalse(volunteer.get("create"))


class TestHooks(UnitTestCase):
	def test_ticket_hooks_registered(self):
		ticket = hooks.doc_events["Ticket"]
		self.assertIn("patient_reach.doc_events.ticket_sync_follow_up_tracker", ticket["on_update"])
		self.assertIn("patient_reach.doc_events.assign_for_review", ticket["on_update"])
		self.assertEqual(ticket["on_trash"], "patient_reach.doc_events.ticket_on_trash")


def _visit(name, interested="", ready=""):
	return {"name": name, "caregiver_interested": interested, "are_you_ready_to_make_a_change_for_a_healthy_you": ready}


def _tracker(calls=None):
	tracker = MagicMock(caregiver_id="CG-A", baseline_ticket="TKT-2")
	tracker.as_dict.return_value = {"caregiver_id": "CG-A", **(calls or {})}
	return tracker


class TestCaregiverChanged(UnitTestCase):
	"""TKT-2 belonged to caregiver CG-A; a volunteer changed it to CG-B."""

	visit = frappe._dict(name="TKT-2", patient_id="CG-B", docstatus=0)

	def release(self, tracker, visits):
		with (
			patch("patient_reach.doc_events.frappe.get_all", side_effect=[["SFT-1"], visits]) as get_all,
			patch("patient_reach.doc_events.frappe.get_doc", return_value=tracker),
			patch("patient_reach.doc_events.frappe.delete_doc") as delete_doc,
		):
			_release_previous_caregivers_tracker(self.visit)
		return get_all, delete_doc

	def test_latest_eligible_visit_newest_first(self):
		visits = [_visit("TKT-9", "No", "No"), _visit("TKT-5", ready="May be"), _visit("TKT-1", "Yes")]
		self.assertEqual(latest_eligible_visit(visits), "TKT-5")
		self.assertIsNone(latest_eligible_visit([_visit("TKT-9", "No", "No")]))
		self.assertIsNone(latest_eligible_visit([]))

	def test_looks_only_for_other_caregivers_trackers_on_this_visit(self):
		get_all, _ = self.release(_tracker(), [_visit("TKT-1", "Yes")])
		filters = get_all.call_args_list[0].kwargs["filters"]
		self.assertEqual(filters, {"baseline_ticket": "TKT-2", "caregiver_id": ["!=", "CG-B"]})
		visit_filters = get_all.call_args_list[1].kwargs["filters"]
		self.assertEqual(visit_filters["patient_id"], "CG-A")
		self.assertEqual(visit_filters["name"], ["!=", "TKT-2"])

	def test_moves_to_the_previous_caregivers_own_visit(self):
		tracker = _tracker()
		_, delete_doc = self.release(tracker, [_visit("TKT-1", "Yes")])
		self.assertEqual(tracker.baseline_ticket, "TKT-1")
		tracker.save.assert_called_once()
		delete_doc.assert_not_called()

	def test_moves_with_its_calls(self):
		tracker = _tracker({"call_1_actual_date": "2026-10-08"})
		self.release(tracker, [_visit("TKT-1", ready="Yes")])
		self.assertEqual(tracker.baseline_ticket, "TKT-1")

	def test_removed_when_no_other_visit_and_no_calls(self):
		tracker = _tracker()
		_, delete_doc = self.release(tracker, [_visit("TKT-1", "No", "No")])
		delete_doc.assert_called_once()
		tracker.save.assert_not_called()

	def test_kept_when_no_other_visit_but_calls_entered(self):
		tracker = _tracker({"call_1_notes": "spoke"})
		_, delete_doc = self.release(tracker, [])
		delete_doc.assert_not_called()
		tracker.save.assert_not_called()

	def test_sync_releases_even_when_the_caregiver_is_cleared(self):
		with patch("patient_reach.doc_events._release_previous_caregivers_tracker") as release:
			ticket_sync_follow_up_tracker(frappe._dict(name="TKT-2", patient_id="", docstatus=0))
		release.assert_called_once()
