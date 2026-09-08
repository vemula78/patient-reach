# Copyright (c) 2026, Frugal Scientific and Contributors
# See license.txt

"""Tests for the two Ticket behaviours that have actually caused incidents.

1. `_bp_status` must classify the band between normal and high as
   "Needs Reference". The field has no "Elevated" option, and calling that band
   "Normal" would understate a reading a counsellor should act on.

2. `ticket_before_validate` recomputes `string_test_result` and `bp_status` on
   every save. During the caregiver backlog import on 07-Sep-2026 this silently
   rewrote 44 of 138 recorded assessments while the import reported success.
   The behaviour is wanted -- the counselling team asked for those two fields to
   be derived rather than chosen -- so the test pins it down instead of removing
   it. (An earlier version of this docstring also claimed to pin down the
   `db_set` escape hatch a bulk write must use. Nothing here calls `db_set`, so
   that claim was removed rather than left to mislead; the test needs a persisted
   Ticket and is still to be written.)

3. The doc_events registration itself. `after_save` is not an event Frappe
   dispatches, and a doc_events key matching no document method is ignored
   silently, so this app's forwarding handler ran never between 06- and
   08-Sep-2026.

There is also a parity test between the strings these functions return and the
Select options in ticket.json. A mismatch there does not raise: the Select just
holds a value it will not offer and the grid renders blank, so nothing would
tell us it had happened.

These use `UnitTestCase`, not `FrappeTestCase`/`IntegrationTestCase`, and that
is deliberate. IntegrationTestCase.setUpClass calls make_test_records(cls.doctype),
which walks Ticket's Link fields to Patient and imports the health app's
test_patient module; that module creates Patients at import time and cannot,
because this app's fixtures make six Patient custom fields mandatory. Nothing
here writes to the database -- the hook is exercised on an unsaved document --
so the test-record machinery is pure cost. Note this is why the vendor's empty
stubs passed: with no test methods, unittest never calls setUpClass.
"""

import frappe
from frappe.tests import UnitTestCase

from patient_reach.doc_events import _bp_status, _string_test_result, ticket_before_validate

NEEDS_REFERENCE = "Needs Reference"
PASS_RESULT = "PASS (Ends touch/ W:H < 0.5)"
FAIL_RESULT = "FAIL (Gap exists - Central Obesity)"


def _options(fieldname):
	"""The Select options actually offered by the Ticket form, minus the blank."""
	raw = frappe.get_meta("Ticket").get_field(fieldname).options or ""
	return [o for o in raw.split("\n") if o]


class TestBPStatus(UnitTestCase):
	def test_borderline_band_is_needs_reference(self):
		"""Systolic 120-139 or diastolic 80-89 must not be called Normal."""
		for reading in ("120/70", "128/84", "139/89", "110/80", "118/85"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), NEEDS_REFERENCE)

	def test_normal_is_strictly_under_120_and_80(self):
		for reading in ("119/79", "110/70", "90/60"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), "Normal")

	def test_high_starts_at_140_or_90(self):
		for reading in ("140/80", "130/90", "180/110"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), "High")

	def test_low_is_under_90_or_60(self):
		for reading in ("85/70", "110/55", "80/50"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), "Low")

	def test_free_text_is_never_guessed(self):
		"""This field genuinely contains prose in live data."""
		for reading in ("BP machine not working", "not recorded", "refused", "-"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), NEEDS_REFERENCE)

	def test_implausible_numbers_are_not_classified(self):
		for reading in ("400/250", "10/5", "999/999"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), NEEDS_REFERENCE)

	def test_absent_reading_returns_none_not_a_verdict(self):
		"""None means "no opinion" and is what stops the hook overwriting."""
		for reading in (None, "", 0):
			with self.subTest(reading=reading):
				self.assertIsNone(_bp_status(reading))

	def test_separators_used_by_counsellors(self):
		for reading in ("128 / 84", "128-84", "128\\84"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), NEEDS_REFERENCE)

	def test_every_verdict_is_an_option_the_form_offers(self):
		offered = _options("bp_status")
		produced = {_bp_status(r) for r in ("119/79", "128/84", "140/90", "85/55", "BP machine not working")}
		self.assertTrue(produced)
		for verdict in produced:
			with self.subTest(verdict=verdict):
				self.assertIn(verdict, offered)


class TestStringTestResult(UnitTestCase):
	def test_pass_when_waist_under_half_of_height(self):
		self.assertEqual(_string_test_result(70, 160), PASS_RESULT)

	def test_fail_when_waist_is_half_or_more(self):
		# Exactly half fails: the comparison is strict.
		self.assertEqual(_string_test_result(80, 160), FAIL_RESULT)
		self.assertEqual(_string_test_result(95, 160), FAIL_RESULT)

	def test_zero_means_not_recorded_not_zero_centimetres(self):
		"""A Frappe Float column cannot be null, so 0.0 is "not measured"."""
		for waist, height in ((0, 160), (70, 0), (0, 0), (None, None)):
			with self.subTest(waist=waist, height=height):
				self.assertIsNone(_string_test_result(waist, height))

	def test_non_numeric_returns_none(self):
		self.assertIsNone(_string_test_result("VF 8.5", 160))

	def test_both_verdicts_are_options_the_form_offers(self):
		offered = _options("string_test_result")
		self.assertIn(PASS_RESULT, offered)
		self.assertIn(FAIL_RESULT, offered)


class TestTicketBeforeValidate(UnitTestCase):
	"""The hook is called directly on an unsaved doc.

	A saved Ticket needs Patient, Branch, Company and Department to exist, none
	of which this behaviour depends on. `frappe.new_doc` gives a real Document --
	real `flags`, real fieldnames -- without that setup or any database write.
	"""

	def _draft(self, **values):
		doc = frappe.new_doc("Ticket")
		doc.update(values)
		return doc

	def test_recorded_verdicts_are_overwritten_when_measurements_exist(self):
		"""This is the fault that rewrote 44 assessments. It is intended."""
		doc = self._draft(
			waist_cm=70,
			height_cm=160,
			bp_reading="128/84",
			string_test_result=FAIL_RESULT,
			bp_status="Normal",
		)
		ticket_before_validate(doc)
		self.assertEqual(doc.string_test_result, PASS_RESULT)
		self.assertEqual(doc.bp_status, NEEDS_REFERENCE)

	def test_recorded_verdicts_survive_when_there_is_nothing_to_derive(self):
		"""Without measurements the hook must leave the counsellor's entry alone."""
		doc = self._draft(
			waist_cm=0,
			height_cm=0,
			bp_reading="",
			string_test_result=PASS_RESULT,
			bp_status="High",
		)
		ticket_before_validate(doc)
		self.assertEqual(doc.string_test_result, PASS_RESULT)
		self.assertEqual(doc.bp_status, "High")

	def test_unparseable_bp_still_produces_a_verdict(self):
		"""Prose is classified, not ignored -- so it does overwrite."""
		doc = self._draft(bp_reading="BP machine not working", bp_status="Normal")
		ticket_before_validate(doc)
		self.assertEqual(doc.bp_status, NEEDS_REFERENCE)

	def test_draft_skips_mandatory_so_a_consultation_can_be_saved_part_way(self):
		doc = self._draft()
		self.assertEqual(doc.docstatus, 0)
		ticket_before_validate(doc)
		self.assertTrue(doc.flags.ignore_mandatory)

	def test_submitted_ticket_does_not_skip_mandatory(self):
		doc = self._draft()
		doc.docstatus = 1
		ticket_before_validate(doc)
		self.assertFalse(doc.flags.get("ignore_mandatory"))


class TestBPStatusConflictingReadings(UnitTestCase):
	"""Readings that satisfy both the low and the high test.

	Until 08-Sep-2026 branch order decided these, so a hypertensive caregiver was
	recorded as hypotensive. The field's own policy is to defer rather than guess.
	"""

	def test_systolic_high_with_low_diastolic_is_not_low(self):
		# Isolated systolic hypertension with a wide pulse pressure -- the
		# commonest pattern in older patients, and the one that read as "Low".
		for reading in ("150/50", "160/55", "180/50", "140/59"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), NEEDS_REFERENCE)

	def test_diastolic_high_with_low_systolic_is_not_low(self):
		for reading in ("85/95", "89/90"):
			with self.subTest(reading=reading):
				self.assertEqual(_bp_status(reading), NEEDS_REFERENCE)

	def test_unambiguous_readings_still_classify(self):
		"""The conflict rule must not swallow ordinary readings."""
		self.assertEqual(_bp_status("85/55"), "Low")
		self.assertEqual(_bp_status("150/95"), "High")
		self.assertEqual(_bp_status("110/70"), "Normal")


class TestDocEventRegistration(UnitTestCase):
	"""The regression guard for the fault that made this file necessary.

	`after_save` is a Server Script UI label, not a document method. Frappe
	ignores an unknown doc_events key without error or log, so the only symptom
	was referrals never reaching a doctor.
	"""

	def _ticket_events(self):
		return frappe.get_hooks("doc_events").get("Ticket", {})

	def test_every_hooked_event_is_one_frappe_dispatches(self):
		from frappe.core.doctype.server_script.server_script_utils import EVENT_MAP

		# EVENT_MAP is keyed by the document method Frappe calls, so it is the
		# framework's own list of valid names. autoname/onload are real hooks
		# that predate it.
		dispatched = set(EVENT_MAP) | {"autoname", "onload"}
		for event in self._ticket_events():
			with self.subTest(event=event):
				self.assertIn(event, dispatched)

	def test_forwarding_is_registered_on_on_update(self):
		self.assertIn("on_update", self._ticket_events())

	def test_after_save_is_not_used(self):
		self.assertNotIn("after_save", self._ticket_events())
