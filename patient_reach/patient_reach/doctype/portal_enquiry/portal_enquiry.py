# Copyright (c) 2026, Frugal Scientific and contributors
# For license information, please see license.txt

"""A patient's enquiry raised through the public portal.

Deliberately separate from Visit (Ticket) and the Sparsh follow-up doctypes:
it has its own workflow, its own roles' permissions and no link to a Patient
record. Staff turn one into a Visit by hand when it warrants one.
"""

import frappe
from frappe.model.document import Document

PORTAL_ROLE = "Patient Portal User"
FIRST_STATE = "Draft"  # shown to the patient as "Received"


class PortalEnquiry(Document):
	def before_insert(self):
		if not self.enquirer:
			self.enquirer = frappe.session.user
		if not self.workflow_state:
			self.workflow_state = FIRST_STATE
		# Staff reading the desk form need to know who wrote in; the portal
		# page only ever sends a subject and details.
		user = frappe.db.get_value("User", self.enquirer, ["full_name", "mobile_no"], as_dict=True)
		if user:
			self.enquirer_name = self.enquirer_name or user.full_name
			self.mobile_no = self.mobile_no or user.mobile_no

	def validate(self):
		if PORTAL_ROLE in frappe.get_roles() and self.enquirer != frappe.session.user:
			frappe.throw("Invalid enquirer")
		for row in self.get("responses"):
			row.responding_date = row.responding_date or frappe.utils.today()
			row.responder = row.responder or frappe.session.user
