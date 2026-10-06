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
"""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

from patient_reach import hooks
from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
	GOING_ON,
	any_call_entry,
	chained_schedule,
	check_calls,
	is_eligible,
	next_call_due,
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


class TestNextCallDue(UnitTestCase):
	def test_first_call_not_made(self):
		self.assertEqual(next_call_due({"call_1_scheduled_date": "2026-10-10"}), "2026-10-10")

	def test_moves_to_call_two_when_going_on(self):
		values = {"call_1_actual_date": "2026-10-10", "call_1_interest": "Yes", "call_2_scheduled_date": "2026-10-24"}
		self.assertEqual(next_call_due(values), "2026-10-24")

	def test_stops_when_not_going_on_or_closed(self):
		self.assertIsNone(next_call_due({"call_1_actual_date": "2026-10-10", "call_1_interest": "No"}))
		self.assertIsNone(next_call_due({"call_1_scheduled_date": "2026-10-10", "follow_up_status": "Closed"}))

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
		self.assertNotIn("depends_on", FIELDS["call_1_section"])
		for n in (2, 3):
			self.assertIn(f"doc.call_{n - 1}_interest", FIELDS[f"call_{n}_section"]["depends_on"])
		for n in (1, 2):
			self.assertIn(f"doc.call_{n}_interest", FIELDS[f"call_{n}_next_date"]["read_only_depends_on"])

	def test_call_outcome_option_renamed(self):
		for n in (1, 2, 3):
			options = FIELDS[f"call_{n}_outcome"]["options"].split("\n")
			self.assertIn("No Answer After 3 Attempts", options)
			self.assertNotIn("No Answer", options)

	def test_scheduled_dates_are_not_editable(self):
		for n in (1, 2, 3):
			self.assertEqual(FIELDS[f"call_{n}_scheduled_date"].get("read_only"), 1)
		self.assertEqual(FIELDS["call_1_scheduled_date"]["fetch_from"], "baseline_ticket.follow_up_date")

	def test_one_tracker_per_caregiver(self):
		self.assertEqual(FIELDS["caregiver_id"].get("unique"), 1)

	def test_counsellors_cannot_create(self):
		volunteer = next(p for p in META["permissions"] if p["role"] == "Volunteer")
		self.assertFalse(volunteer.get("create"))


class TestHooks(UnitTestCase):
	def test_ticket_hooks_registered(self):
		ticket = hooks.doc_events["Ticket"]
		self.assertIn("patient_reach.doc_events.ticket_sync_follow_up_tracker", ticket["on_update"])
		self.assertEqual(ticket["on_trash"], "patient_reach.doc_events.ticket_on_trash")
