# Copyright (c) 2026, Frugal Scientific and Contributors
# See license.txt

"""Tests for Telemedicine Session: the WS number rule, what is and is not
required, the workflow, the dashboard patch, and that Visit lost its
"Telemedicine" Ticket Type.

`UnitTestCase`, as in test_portal_enquiry.py: IntegrationTestCase would build
Branch test records, whose Branch Code is mandatory here.
"""

import json
from pathlib import Path

import frappe
from frappe.model.workflow import WorkflowTransitionError, apply_workflow
from frappe.tests import UnitTestCase

from patient_reach.patches.v1_15 import create_telemedicine_dashboard as dash
from patient_reach.patches.v1_15 import create_telemedicine_workflow as wf
from patient_reach.patient_reach.doctype.telemedicine_session.telemedicine_session import normalize_ws_number

DOCTYPES = Path(__file__).resolve().parents[1]
REQUIRED = {
	"patient_ws_number",
	"patient_name",
	"session_datetime",
	"doctor",
	"age",
	"gender",
	"patient_mobile_no",
	"nodal_centre",
	"department",
}


def _fields():
	return {f["fieldname"]: f for f in json.loads((DOCTYPES / "telemedicine_session/telemedicine_session.json").read_text())["fields"]}


class TestWsNumber(UnitTestCase):
	def test_two_or_four_zeros_then_six_digits_pass(self):
		self.assertEqual(normalize_ws_number("WS00123456"), "WS00123456")
		self.assertEqual(normalize_ws_number("WS0000123456"), "WS0000123456")

	def test_spaces_and_lower_case_are_corrected(self):
		self.assertEqual(normalize_ws_number(" ws 00123456 "), "WS00123456")

	def test_three_zeros_and_everything_else_is_refused(self):
		for bad in (
			"WS000123456",  # three zeros: not allowed
			"WS0123456",  # one zero
			"WS00000123456",  # five zeros
			"WS0012345",  # five digits
			"WS001234567",  # seven digits after two zeros
			"PN00123456",  # Puttaparthi
			"PS00123456",
			"00123456",
			"WS00ABCDEF",
			"",
			None,
		):
			with self.assertRaises(frappe.ValidationError, msg=bad):
				normalize_ws_number(bad)

	def test_the_error_does_not_repeat_the_number(self):
		try:
			normalize_ws_number("WS99999999")
		except frappe.ValidationError as e:
			self.assertNotIn("99999999", str(e))


class TestForm(UnitTestCase):
	def test_exactly_the_agreed_fields_are_required(self):
		self.assertEqual({n for n, f in _fields().items() if f.get("reqd")}, REQUIRED)

	def test_consent_is_not_asked_and_duration_is_minutes_that_may_be_zero(self):
		fields = _fields()
		self.assertFalse([n for n in fields if "consent" in n])
		self.assertEqual(fields["call_duration"]["fieldtype"], "Int")  # a Duration field cannot hold 0
		for n in ("call_duration", "outcome", "next_session_date", "follow_up_by", "cancel_reason"):
			self.assertFalse(fields[n].get("reqd"), n)

	def test_visit_no_longer_offers_telemedicine(self):
		ticket = json.loads((DOCTYPES / "ticket/ticket.json").read_text())
		options = next(f["options"] for f in ticket["fields"] if f["fieldname"] == "ticket_type")
		self.assertNotIn("Telemedicine", options)
		self.assertEqual(options.split("\n"), ["", "Patient Enquiry", "Preventive Cardiology"])

	def test_workflow_uses_only_its_own_states_and_volunteers_can_run_it(self):
		states = {s for s, _style, _role in wf.STATES}
		self.assertTrue({x for f, _a, t, _r in wf.TRANSITIONS for x in (f, t)} <= states)
		roles = {r for f, a, t, r in wf.TRANSITIONS if a == "Start Session"}
		self.assertEqual(roles, {"Volunteer", "Staff", "Doctor"})
		self.assertEqual({r for f, a, t, r in wf.TRANSITIONS if a == "Reopen Session"}, {"Staff"})


class TestSession(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		wf.execute()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Telemedicine Session")

	def _make(self, **over):
		doc = frappe.get_doc(
			{
				"doctype": "Telemedicine Session",
				"patient_ws_number": "ws00123456",
				"patient_name": "Test Patient",
				"age": 54,
				"gender": "Male",
				"patient_mobile_no": "+919876500001",
				"nodal_centre": "Test Centre",
				"department": "Test Department",
				"doctor": "Administrator",
				"session_datetime": "2026-11-10 11:00:00",
				**over,
			}
		)
		doc.flags.ignore_links = True
		doc.flags.ignore_permissions = True
		return doc

	def test_it_saves_as_scheduled_with_a_clean_ws_number(self):
		doc = self._make().insert()
		self.assertEqual(doc.workflow_state, "Scheduled")
		self.assertEqual(doc.patient_ws_number, "WS00123456")

	def test_a_bad_ws_number_or_missing_mobile_cannot_be_saved(self):
		with self.assertRaises(frappe.ValidationError):
			self._make(patient_ws_number="WS000123456").insert()
		with self.assertRaises(frappe.MandatoryError):
			self._make(patient_mobile_no=None).insert()

	def test_completing_needs_advice_and_nothing_else(self):
		doc = self._make().insert()
		doc = apply_workflow(doc, "Start Session")
		self.assertEqual(doc.workflow_state, "In Progress")
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Complete Session")
		doc.reload()
		doc.advice = "<div><p>Continue the medicines and review in two weeks.</p></div>"
		doc.save()
		doc = apply_workflow(doc, "Complete Session")
		self.assertEqual(doc.workflow_state, "Completed")
		self.assertIsNone(doc.outcome)  # outcome and duration stay optional

	def test_a_completed_session_cannot_skip_back_to_scheduled(self):
		doc = self._make(advice="Done").insert()
		doc = apply_workflow(apply_workflow(doc, "Start Session"), "Complete Session")
		with self.assertRaises(WorkflowTransitionError):
			apply_workflow(doc, "Start Session")


class TestDashboard(UnitTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_patch_builds_the_dashboard_once_and_only_counts_telemedicine(self):
		dash.execute()
		dash.execute()  # idempotent
		self.assertTrue(frappe.db.exists("Dashboard", "Telemedicine"))
		self.assertTrue(frappe.db.exists("Workspace", "Telemedicine"))
		for card in dash.NUMBER_CARDS:
			self.assertEqual(frappe.db.get_value("Number Card", card, "document_type"), "Telemedicine Session")
		for chart in dash.CHARTS:
			self.assertEqual(frappe.db.get_value("Dashboard Chart", chart, "document_type"), "Telemedicine Session")
		self.assertEqual(frappe.db.count("Workspace", {"label": "Telemedicine"}), 1)
