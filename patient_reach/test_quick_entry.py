# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""The Add Caregiver popup and the Caregiver form list only the districts of the
chosen State (change request of 07-Nov-2026, item 4).

The behaviour was checked on the live popup, where a `get_query` on the field
definition and an `onchange` set after rendering were both ignored. There is no
browser test here, so these pin what the fix depends on: the filter and the
clearing are attached to the controls after the popup is built, and the Patient
District DocType still carries the `state` field the filter names.
"""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

APP = Path(__file__).parent
JS = (APP / "public" / "js" / "patient_quick_entry.js").read_text()


class TestDistrictFilter(UnitTestCase):
	def test_the_popup_filter_is_on_the_control_not_the_field_definition(self):
		self.assertIn("district_control.get_query", JS)
		self.assertNotIn("get_query: () => ({ filters: { state: this.dialog", JS)

	def test_the_filter_is_attached_after_the_popup_is_rendered(self):
		self.assertLess(JS.index("super.render_dialog();"), JS.index("district_control.get_query"))

	def test_a_district_is_cleared_when_the_state_changes(self):
		self.assertIn("clear_if_state_changed", JS)
		self.assertIn('state.$input.on("change blur awesomplete-selectcomplete"', JS)
		self.assertNotIn("state.df.onchange", JS)

	def test_the_full_form_filters_from_the_moment_it_opens(self):
		self.assertIn('frm.set_query("custom_district"', JS)

	def test_the_filter_names_a_field_the_district_doctype_has(self):
		meta = json.loads((APP / "patient_reach" / "doctype" / "patient_district" / "patient_district.json").read_text())
		state = next(f for f in meta["fields"] if f["fieldname"] == "state")
		self.assertEqual((state["fieldtype"], state["options"]), ("Link", "Patient State"))


class TestShortcutLabels(UnitTestCase):
	"""Item 1 of 07-Nov-2026: a shortcut's label is shown in full."""

	def test_the_label_wraps_instead_of_being_cut_with_an_ellipsis(self):
		css = (APP / "public" / "css" / "patient_reach.css").read_text()
		block = css[css.index(".shortcut-widget-box .widget-title .ellipsis") :]
		self.assertIn("white-space: normal", block)
		self.assertIn("overflow: visible", block)
		self.assertIn("text-overflow: clip", block)
