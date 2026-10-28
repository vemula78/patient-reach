# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""The clinical reviewer's removal of a Level 4 entered in error (Dr Nayanjeet
Chaudhury, Q11 of 13-Oct-2026).

Only the Sparsh Clinical Reviewer role may make one. The visit or follow-up row
that holds the Level 4 is not changed: this record keeps the original
classification, the date, the reviewer and the reason beside it, and once
submitted the caregiver's later visits are no longer held at Level 4 by that
record (doc_events._level_4_reasons). Cancelling it puts the Level 4 back.
Clinical recovery is never a reason.
"""

import frappe
from frappe import _
from frappe.model.document import Document

REVIEWER_ROLE = "Sparsh Clinical Reviewer"


class SparshLevel4Correction(Document):
	def validate(self):
		if REVIEWER_ROLE not in frappe.get_roles():
			frappe.throw(_("Only the clinical reviewer can remove a Level 4."), frappe.PermissionError)
		if "recover" in (self.explanation or "").lower():
			frappe.throw(
				_(
					"Clinical recovery is not a valid reason: Level 4 is permanent after a qualifying event (DRL A8)."
				)
			)
		owner_field = "patient_id" if self.source_doctype == "Ticket" else "caregiver_id"
		if frappe.db.get_value(self.source_doctype, self.source_name, owner_field) != self.caregiver:
			frappe.throw(_("{0} is not a record of caregiver {1}.").format(self.source_name, self.caregiver))
		if self.is_new() or not self.reviewer:
			self.reviewer = frappe.session.user
		self.original_classification = _classification(self.source_doctype, self.source_name)

	def on_submit(self):
		self.db_set("corrected_on", frappe.utils.now_datetime())


def _classification(doctype, name):
	"""What the source record says, as it stands when the correction is made."""
	lines = []
	if doctype == "Ticket":
		level = frappe.db.get_value("Ticket", name, "prevention_level")
		lines.append(f"Prevention Level: {level or 'not recorded'}")
	for row in frappe.get_all(
		"Sparsh Health Event",
		filters={"parenttype": doctype, "parent": name},
		fields=["event_type", "source", "level_4_status"],
		order_by="idx",
	):
		lines.append(f"{row.event_type} ({row.source or 'source not recorded'}): {row.level_4_status or ''}")
	return "\n".join(lines)
