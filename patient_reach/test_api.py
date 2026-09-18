# Copyright (c) 2026, Frugal Scientific and Contributors
# See license.txt

"""Tests for `patient_autoname`, which produced a wrong id on live data.

Before 10-Sep-2026 the function interpolated the result of a `get_value` lookup
straight into an f-string. A Patient with no Hospital therefore got the literal
word "None" in its id, and the 138 caregiver records imported on 08-Sep were all
named `SWF-None-####` while the 846 entered through the form were
`SWF-SPARSH-####`. The counselling team spotted the mismatch, not us.

`custom_hospital_id` is mandatory on the Patient form, so only a bulk insert can
reach the naming hook without one. The fix refuses to name such a Patient rather
than inventing a branch code; these tests pin that down.
"""

import frappe
from frappe.tests import UnitTestCase

from patient_reach.api import patient_autoname


class _Doc(frappe.utils.DotDict):
	"""Enough of a Patient for the naming hook: it reads one field, sets `name`."""


class TestPatientAutoname(UnitTestCase):
	def test_no_hospital_is_refused_not_named_none(self):
		"""The regression: no Hospital must raise, never yield "SWF-None-"."""
		doc = _Doc(custom_hospital_id=None)
		with self.assertRaises(frappe.ValidationError):
			patient_autoname(doc, "autoname")
		self.assertIsNone(doc.get("name"))

	def test_empty_string_hospital_is_refused(self):
		"""An empty string is what a bulk insert actually leaves behind."""
		doc = _Doc(custom_hospital_id="")
		with self.assertRaises(frappe.ValidationError):
			patient_autoname(doc, "autoname")
		self.assertIsNone(doc.get("name"))

	def test_hospital_without_a_branch_code_is_refused(self):
		"""A Branch exists but carries no code: still not nameable."""
		branch = frappe.get_doc(doctype="Branch", branch=frappe.generate_hash("nocode", 8)).insert(
			ignore_permissions=True
		)
		self.addCleanup(branch.delete, ignore_permissions=True)

		doc = _Doc(custom_hospital_id=branch.name)
		with self.assertRaises(frappe.ValidationError):
			patient_autoname(doc, "autoname")
		self.assertIsNone(doc.get("name"))

	def test_branch_code_becomes_the_id_prefix(self):
		"""The happy path, so the fix cannot be "throw always"."""
		branch = frappe.get_doc(
			doctype="Branch",
			branch=frappe.generate_hash("withcode", 8),
			custom_branch_code="TEST",
		).insert(ignore_permissions=True)
		self.addCleanup(branch.delete, ignore_permissions=True)

		doc = _Doc(custom_hospital_id=branch.name)
		patient_autoname(doc, "autoname")
		self.assertTrue(doc.name.startswith("SWF-TEST-"), doc.name)
		self.assertNotIn("None", doc.name)
