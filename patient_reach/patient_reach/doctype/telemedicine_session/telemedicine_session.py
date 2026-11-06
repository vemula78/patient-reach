# Copyright (c) 2026, Frugal Scientific and contributors
# For license information, please see license.txt

"""One telemedicine session (Microsoft Teams) held with a hospital patient.

Separate from Visit (Ticket) and everything Sparsh. The patient is identified by
a WS number, held as text: on care the Patient doctype is the caregiver list, so
a hospital patient is not linked to it.
"""

import re

import frappe
from frappe.model.document import Document
from frappe.utils import strip_html_tags

# WS, then two or four zeros (not three), then six digits.
WS_NUMBER = re.compile(r"WS(?:00|0000)[0-9]{6}")
FIRST_STATE = "Scheduled"


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


class TelemedicineSession(Document):
	def before_insert(self):
		if not self.workflow_state:
			self.workflow_state = FIRST_STATE

	def validate(self):
		self.patient_ws_number = normalize_ws_number(self.patient_ws_number)
		self.patient_name = (self.patient_name or "").strip()
		if not 0 <= (self.age or 0) <= 120:
			frappe.throw("Age must be between 0 and 120 years.")
		if (self.call_duration or 0) < 0:
			frappe.throw("Call duration cannot be negative.")
		if self.workflow_state == "Completed" and not strip_html_tags(self.advice or "").strip():
			frappe.throw("Please record the advice given before completing the session.")
