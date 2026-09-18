# Copyright (c) 2026, Frugal Scientific and Contributors
# See license.txt

"""Tests for the Sparsh Follow Up rules that a wrong answer would hide.

`UnitTestCase`, not `FrappeTestCase`/`IntegrationTestCase`, and nothing here
writes to the database -- the same reasoning as `test_ticket.py`:
`IntegrationTestCase.setUpClass` calls `make_test_records`, which walks the Link
fields to Patient and imports the health app's test module, which cannot build a
Patient while this app's fixtures make six Patient custom fields mandatory. Every
rule worth pinning is a pure function, so the test-record machinery is pure cost.

What is pinned, and why each one matters:

1. **The habit score's denominator** (decision 5). A Frappe `Int` cannot be NULL,
   so `habit_score = 0` means both "four unhealthy answers" and "nothing asked".
   A blank and a `No` must produce a different `answered` for the same `healthy`.
2. **The sunset-rule polarity.** The intake Ticket asks "dinner AFTER 8 PM?"
   (Yes = non-compliant); this form asks "heaviest meal BEFORE 8 PM?" (Yes =
   compliant). Same concept, opposite sign, and the two mappings must stay apart.
3. **Parity between the Select options in the JSON and the mappings.** A Select
   holding a value it does not offer renders blank without raising, so nothing
   would report it.
4. **Conditional mandatory** (decision 1). `mandatory_depends_on` is evaluated by
   the client only, so an API save or a data import bypasses it entirely.
5. **The Ticket `before_cancel` registration.** A `doc_events` key naming no
   document method is ignored in silence; that is what made this app's
   forwarding handler run never for two days in September 2026.
"""

import frappe
from frappe.tests import UnitTestCase

from patient_reach.patient_reach.doctype.sparsh_follow_up.sparsh_follow_up import (
	CONNECTED_ONLY_MANDATORY,
	HABIT_MAPS,
	check_confidence_score,
	check_red_flag_disposition,
	habit_summary,
	missing_when_connected,
	split_prevention_level,
	traffic_movement,
)


def _options(doctype, fieldname):
	"""The Select options a form actually offers, minus the blank."""
	raw = frappe.get_meta(doctype).get_field(fieldname).options or ""
	return [o for o in raw.split("\n") if o]


class TestHabitSummary(UnitTestCase):
	"""Decision 5: a blank answer is missing, never zero."""

	def test_mixed_answers_report_their_denominator(self):
		self.assertEqual(
			habit_summary("Yes", "No", None, "Yes"),
			(2, 3, "2 healthy of 3 answered; 1 not answered"),
		)

	def test_nothing_asked_is_not_four_unhealthy_answers(self):
		"""A not-connected call. `habit_score` alone cannot say this."""
		self.assertEqual(
			habit_summary(None, None, None, None),
			(0, 0, "0 healthy of 0 answered; 4 not answered"),
		)

	def test_blank_and_no_differ_in_the_denominator_not_the_score(self):
		blank_healthy, blank_answered, _blank = habit_summary(None, None, None, None)
		no_healthy, no_answered, _no = habit_summary("No", "No", "Overwhelmed", "No")
		self.assertEqual(blank_healthy, no_healthy)
		self.assertNotEqual(blank_answered, no_answered)

	def test_all_four_healthy(self):
		self.assertEqual(
			habit_summary("Yes", "Yes", "Mostly Calm", "Yes"),
			(4, 4, "4 healthy of 4 answered; 0 not answered"),
		)

	def test_empty_string_counts_as_unanswered(self):
		"""Frappe hands back "" for an untouched Select, not None."""
		self.assertEqual(habit_summary("", "", "", ""), (0, 0, "0 healthy of 0 answered; 4 not answered"))

	def test_healthy_never_exceeds_answered(self):
		"""The deploy invariant, as a unit test."""
		for answers in (
			("Yes", "Yes", "Mostly Calm", "Yes"),
			("Yes", None, None, None),
			(None, None, None, None),
			("No", "Yes", "Overwhelmed", None),
		):
			with self.subTest(answers=answers):
				healthy, answered, _display = habit_summary(*answers)
				self.assertLessEqual(healthy, answered)

	def test_a_value_the_form_does_not_offer_raises(self):
		"""Never counted as zero -- that would be a silent unhealthy answer."""
		with self.assertRaises(ValueError):
			habit_summary("Sometimes", None, None, None)


class TestSunsetRulePolarity(UnitTestCase):
	"""The trap: two forms, one concept, opposite signs.

	Intake `Ticket.sunset_rule`  -- "Does the caregiver have dinner AFTER 8 PM ?"
	                                Yes = NON-compliant.
	Follow-up `sunset_rule_binary` -- "Heaviest meal before 8 PM?"
	                                Yes = COMPLIANT (decision 4).

	Nothing may share a mapping between them, and no intake report may import
	`HABIT_MAPS`.
	"""

	def test_follow_up_yes_is_the_healthy_answer(self):
		healthy, answered, _display = habit_summary("Yes", None, None, None)
		self.assertEqual((healthy, answered), (1, 1))

	def test_follow_up_no_is_the_unhealthy_answer(self):
		healthy, answered, _display = habit_summary("No", None, None, None)
		self.assertEqual((healthy, answered), (0, 1))

	def test_the_two_forms_ask_opposite_questions(self):
		"""If either label is ever reworded, this test is the place to look."""
		intake = frappe.get_meta("Ticket").get_field("sunset_rule").label
		follow_up = frappe.get_meta("Sparsh Follow Up").get_field("sunset_rule_binary").label
		self.assertIn("after 8 PM", intake)
		self.assertIn("before 8 PM", follow_up)


class TestSelectParity(UnitTestCase):
	"""Every option the form offers must be a key in the mapping that reads it."""

	def test_every_habit_option_is_mapped(self):
		for fieldname, mapping in HABIT_MAPS.items():
			with self.subTest(fieldname=fieldname):
				self.assertEqual(set(_options("Sparsh Follow Up", fieldname)), set(mapping))

	def test_every_traffic_light_option_is_understood(self):
		offered = _options("Sparsh Follow Up", "current_traffic_light")
		for previous in offered:
			for current in offered:
				with self.subTest(previous=previous, current=current):
					transition, category = traffic_movement(previous, current)
					self.assertIsNotNone(transition)
					self.assertIn(category, _options("Sparsh Follow Up", "traffic_light_change_category"))

	def test_every_intake_prevention_level_splits(self):
		for code in _options("Ticket", "prevention_level"):
			with self.subTest(code=code):
				level, s_status = split_prevention_level(code)
				self.assertIn(level, _options("Sparsh Follow Up", "baseline_prevention_level"))
				self.assertIn(s_status, _options("Sparsh Follow Up", "baseline_s_status"))

	def test_advised_rest_is_no_longer_offered(self):
		"""Decision 7 removed it; the free-text disposition replaces it."""
		offered = _options("Sparsh Follow Up", "clinical_action_taken")
		self.assertNotIn("Advised Rest / Monitor", offered)
		self.assertIn("Reviewed - No Action Needed", offered)
		self.assertTrue(frappe.get_meta("Sparsh Follow Up").get_field("clinical_disposition"))


class TestTrafficMovement(UnitTestCase):
	"""Decision 8: descriptive only. No numeric traffic value is stored."""

	def test_improvement(self):
		self.assertEqual(traffic_movement("Yellow", "Green"), ("Yellow → Green", "Improvement"))

	def test_relapse(self):
		self.assertEqual(traffic_movement("Green", "Red"), ("Green → Red", "Relapse"))

	def test_maintenance(self):
		self.assertEqual(traffic_movement("Red", "Red"), ("Red → Red", "Maintenance"))

	def test_no_previous_call_has_no_movement(self):
		self.assertEqual(traffic_movement(None, "Red"), (None, None))

	def test_no_current_light_has_no_movement(self):
		"""A not-connected call records no traffic light."""
		self.assertEqual(traffic_movement("Green", None), (None, None))

	def test_no_numeric_field_is_stored(self):
		fieldnames = [f.fieldname for f in frappe.get_meta("Sparsh Follow Up").fields]
		self.assertEqual([f for f in fieldnames if "traffic_numeric" in f], [])


class TestSplitPreventionLevel(UnitTestCase):
	"""Decision 10: level and S status are two facts, counted separately."""

	def test_s_suffix_means_active(self):
		self.assertEqual(split_prevention_level("Level 2s"), ("Level 2", "Active"))

	def test_no_suffix_means_inactive(self):
		self.assertEqual(split_prevention_level("Level 3"), ("Level 3", "Inactive"))

	def test_blank_is_not_a_level(self):
		self.assertEqual(split_prevention_level(""), (None, None))
		self.assertEqual(split_prevention_level(None), (None, None))

	def test_a_code_the_intake_form_does_not_offer_raises(self):
		with self.assertRaises(ValueError):
			split_prevention_level("2s")


class TestMissingWhenConnected(UnitTestCase):
	"""Decision 1, and the reason `validate()` cannot rely on the JSON.

	`mandatory_depends_on` is evaluated in the browser. Frappe's
	`_get_missing_mandatory_fields` iterates `reqd == 1` and never looks at it,
	so an API save, a data import or a bench script walks straight past it.
	"""

	def _doc(self, **values):
		doc = frappe.new_doc("Sparsh Follow Up")
		doc.update(values)
		return doc

	def test_a_blank_connected_call_is_missing_all_eight(self):
		missing = missing_when_connected(self._doc(call_disposition="Connected"))
		self.assertEqual(len(missing), 8)
		self.assertEqual(set(missing), set(CONNECTED_ONLY_MANDATORY))

	def test_a_blank_no_answer_call_is_complete(self):
		"""An attempt that never connected is a real record with real blanks."""
		self.assertEqual(missing_when_connected(self._doc(call_disposition="No Answer")), [])

	def test_every_not_connected_outcome_is_allowed_to_be_blank(self):
		for disposition in ("No Answer", "Wrong Number", "Caregiver Declined"):
			with self.subTest(disposition=disposition):
				self.assertEqual(missing_when_connected(self._doc(call_disposition=disposition)), [])

	def test_a_filled_connected_call_is_complete(self):
		doc = self._doc(
			call_disposition="Connected",
			actual_call_date="2026-09-18",
			call_duration_mins=12,
			pledge_progress_raw="Achieved",
			pledge_category="Diet",
			new_target_pledge_text="Two servings of dal a day",
			confidence_score=8,
			current_traffic_light="Green",
			next_call_date="2026-10-16",
		)
		self.assertEqual(missing_when_connected(doc), [])

	def test_zero_confidence_counts_as_not_entered(self):
		"""A Frappe Int cannot be null, so 0 is the empty value here."""
		doc = self._doc(call_disposition="Connected", confidence_score=0)
		self.assertIn("confidence_score", missing_when_connected(doc))

	def test_each_connected_only_field_exists_and_carries_the_client_rule(self):
		meta = frappe.get_meta("Sparsh Follow Up")
		for fieldname in CONNECTED_ONLY_MANDATORY:
			with self.subTest(fieldname=fieldname):
				field = meta.get_field(fieldname)
				self.assertIsNotNone(field)
				self.assertEqual(field.mandatory_depends_on, 'eval:doc.call_disposition=="Connected"')
				self.assertFalse(field.reqd)


class TestCallConsistencyChecks(UnitTestCase):
	def test_a_red_flag_needs_someone_to_have_been_spoken_to(self):
		for disposition in ("No Answer", "Wrong Number", "Caregiver Declined", None):
			with self.subTest(disposition=disposition):
				with self.assertRaises(ValueError):
					check_red_flag_disposition(1, disposition)

	def test_a_red_flag_on_a_connected_call_is_fine(self):
		self.assertIsNone(check_red_flag_disposition(1, "Connected"))

	def test_no_red_flag_is_fine_on_any_outcome(self):
		self.assertIsNone(check_red_flag_disposition(0, "No Answer"))

	def test_confidence_outside_the_scale_raises(self):
		for value in (11, 99, -1):
			with self.subTest(value=value):
				with self.assertRaises(ValueError):
					check_confidence_score(value)

	def test_the_whole_scale_is_accepted(self):
		for value in range(1, 11):
			with self.subTest(value=value):
				self.assertIsNone(check_confidence_score(value))

	def test_not_entered_is_not_out_of_range(self):
		for value in (None, "", 0):
			with self.subTest(value=value):
				self.assertIsNone(check_confidence_score(value))


class TestNoOrdinalScore(UnitTestCase):
	"""Decision 3: the four progress categories stay descriptive.

	The recovered original scored them 4/3/2/1 and stored the number. Nothing may
	reintroduce it -- a stored rank gets averaged, and a mean of "Self-Modified"
	and "Not Yet Achieved" is not a clinical statement.
	"""

	def test_no_progress_ordinal_field(self):
		fieldnames = [f.fieldname for f in frappe.get_meta("Sparsh Follow Up").fields]
		self.assertNotIn("pledge_progress_ordinal", fieldnames)

	def test_the_four_categories_are_offered_unranked(self):
		self.assertEqual(
			_options("Sparsh Follow Up", "pledge_progress_raw"),
			["Achieved", "Partially Achieved", "Self-Modified", "Not Yet Achieved"],
		)


class TestDocEventRegistration(UnitTestCase):
	"""A doc_events key matching no document method is ignored in silence."""

	def _ticket_events(self):
		return frappe.get_hooks("doc_events").get("Ticket", {})

	def test_ticket_cancel_is_guarded(self):
		"""Frappe blocks a cancel only on submitted links; Drafts still count."""
		self.assertIn("before_cancel", self._ticket_events())

	def test_before_cancel_is_an_event_frappe_dispatches(self):
		from frappe.core.doctype.server_script.server_script_utils import EVENT_MAP

		self.assertIn("before_cancel", set(EVENT_MAP) | {"autoname", "onload"})


class TestDocTypeShape(UnitTestCase):
	def test_it_is_submittable_and_shows_draft_apart_from_submitted(self):
		"""Decision 2: Drafts keep counting, and must be visibly distinguishable."""
		meta = frappe.get_meta("Sparsh Follow Up")
		self.assertTrue(meta.is_submittable)
		self.assertEqual({s.title for s in meta.states}, {"Draft", "Submitted", "Cancelled"})

	def test_only_the_clinical_roles_may_submit(self):
		"""Decision 2: the review step, without a Workflow document."""
		allowed = {p.role for p in frappe.get_meta("Sparsh Follow Up").permissions if p.submit}
		self.assertEqual(allowed, {"Doctor", "System Manager"})

	def test_the_clinical_fields_are_behind_permlevel_1(self):
		meta = frappe.get_meta("Sparsh Follow Up")
		for fieldname in (
			"clinical_review_status",
			"clinical_review_date",
			"clinical_action_taken",
			"clinical_disposition",
		):
			with self.subTest(fieldname=fieldname):
				self.assertEqual(meta.get_field(fieldname).permlevel, 1)

	def test_habit_score_never_appears_without_its_denominator(self):
		"""Decision 9: the aggregate must not travel alone."""
		meta = frappe.get_meta("Sparsh Follow Up")
		self.assertFalse(meta.get_field("habit_score").in_list_view)
		self.assertTrue(meta.get_field("habit_score_display").in_list_view)

	def test_it_links_to_the_intake_ticket_not_to_sparsh_visit(self):
		"""`Sparsh Visit` died with the old site; the intake is a Ticket."""
		self.assertEqual(frappe.get_meta("Sparsh Follow Up").get_field("baseline_ticket").options, "Ticket")
