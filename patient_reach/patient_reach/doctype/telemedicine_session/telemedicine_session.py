# Copyright (c) 2026, Frugal Scientific and contributors
# For license information, please see license.txt

"""One telemedicine session (Microsoft Teams) held with a patient.

Separate from Visit (Ticket) and everything Sparsh. The patient is picked from the
Patient list, like a Visit's caregiver; name, mobile and Nodal Centre come forward
from the profile. The WS (hospital) number is typed on the session and checked here,
because the Patient profile holds no such number.
"""

import re

import frappe
from frappe.model.document import Document
from frappe.utils import strip_html_tags

# WS, then two or four zeros (not three), then six digits.
WS_NUMBER = re.compile(r"WS(?:00|0000)[0-9]{6}")
BP_READING = re.compile(r"([0-9]{2,3})\s*/\s*([0-9]{2,3})")
FIRST_STATE = "Scheduled"
DOCTOR_ROLE = "Doctor"


def normalize_ws_number(value):
	"""Trim spaces, upper-case, and refuse anything that is not a WS number.

	The message does not repeat the value: it is a patient identifier.
	"""
	ws = re.sub(r"\s+", "", value or "").upper()
	if not WS_NUMBER.fullmatch(ws):
		frappe.throw(
			"The WS number must be WS, then 00 or 0000, then six digits (for example WS00123456).",
			frappe.ValidationError,
		)
	return ws


@frappe.whitelist()
def doctor_users(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field search for Consulting Doctor: enabled care users holding the Doctor role."""
	like = f"%{txt}%"
	return frappe.db.sql(
		"""select u.name, u.full_name from `tabUser` u
		join `tabHas Role` r on r.parent = u.name and r.parenttype = 'User'
		where r.role = %(role)s and u.enabled = 1 and u.user_type = 'System User'
			and (u.name like %(like)s or u.full_name like %(like)s)
		order by u.full_name limit %(start)s, %(len)s""",
		{"role": DOCTOR_ROLE, "like": like, "start": int(start), "len": int(page_len)},
	)


class TelemedicineSession(Document):
	def before_validate(self):
		# Company is read-only on the form and is filled in by the form's script; this covers a
		# session saved any other way. (A ":Company" field default does not mean "the default
		# company" to Frappe: it copies the field from a Company record and fails.)
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")

	def before_insert(self):
		if not self.workflow_state:
			self.workflow_state = FIRST_STATE

	def validate(self):
		self.patient_ws_number = normalize_ws_number(self.patient_ws_number)
		if (self.call_duration or 0) < 0:
			frappe.throw("Call duration cannot be negative.")
		for field, label in (("height_cm", "Height"), ("weight", "Weight")):
			if self.get(field) is not None and self.get(field) < 0:
				frappe.throw(f"{label} cannot be negative.")
		if self.bp_reading:
			m = BP_READING.fullmatch(self.bp_reading.strip())
			if not m or int(m.group(1)) <= int(m.group(2)):
				frappe.throw("Enter the blood pressure as systolic/diastolic, for example 120/80.")
			self.bp_reading = f"{int(m.group(1))}/{int(m.group(2))}"
		if self.consulting_doctor and DOCTOR_ROLE not in frappe.get_roles(self.consulting_doctor):
			frappe.throw("The Consulting Doctor must be a user with the Doctor role.")
		if self.workflow_state == "Completed" and not strip_html_tags(self.advice or "").strip():
			frappe.throw("Please record the advice given before completing the session.")
