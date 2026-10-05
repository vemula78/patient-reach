# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Ticket form connections: the "Sparsh Follow Up" calls made against this
intake Ticket, so a counsellor open on the Ticket can see and open them
without a separate report.

Frappe loads this file itself, as Ticket's standard dashboard (it finds
`<doctype>_dashboard.py` by name). It must therefore **not** also be listed in
`override_doctype_dashboards`: it was from d99161d until 05-Oct-2026, which ran
it twice and showed the Follow-up group twice. It does not touch Patient's
dashboard (`patient_reach.api.get_data`).
"""

import frappe


def get_data(data=None):
	if not data:
		data = {"fieldname": "baseline_ticket", "transactions": [], "non_standard_fieldnames": {}}

	data.setdefault("non_standard_fieldnames", {})
	# Sparsh Follow Up links to Ticket via baseline_ticket, not ticket -- the
	# same reason api.get_data maps Ticket -> Patient via patient_id rather
	# than assuming the field is called "patient".
	data["non_standard_fieldnames"]["Sparsh Follow Up"] = "baseline_ticket"

	data.setdefault("transactions", [])
	data["transactions"].append({"label": frappe._("Follow-up"), "items": ["Sparsh Follow Up"]})

	return data
