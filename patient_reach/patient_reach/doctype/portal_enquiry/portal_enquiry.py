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


def _is_patient():
	"""True for a portal account. Not a role test: Administrator holds every role, Patient Portal
	User included, and must be able to work enquiries."""
	return frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User"


class PortalEnquiry(Document):
	def before_insert(self):
		if _is_patient():
			# A patient can post to the REST API directly: whatever they send for these is replaced,
			# so they cannot start an enquiry as "Responded" or write a reply from the hospital.
			self.enquirer = frappe.session.user
			self.workflow_state = FIRST_STATE
			self.nodal_centre = None
			self.enquirer_name = None
			self.mobile_no = None
			self.set("responses", [])
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
		if _is_patient() and self.enquirer != frappe.session.user:
			frappe.throw("Invalid enquirer")
		for row in self.get("responses"):
			row.responding_date = row.responding_date or frappe.utils.today()
			row.responder = row.responder or frappe.session.user
