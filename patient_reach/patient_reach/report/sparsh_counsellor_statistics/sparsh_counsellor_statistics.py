# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sparsh Counsellor Statistics -- "Counsellor/Coach wise Statistics" on the
Healthcare page (the counselling team's change request of 29-Oct-2026).

One row per counsellor: how many caregivers they registered, visits they
recorded and follow-ups still running. Opened only by the Sparsh Statistics
Viewer role (fixtures/role.json), which the team asked to give to Sandhya
Uchil, Dr Nayanjeet, Deepa Rajesh and Praveen; who holds it is set on care.
The report grid sorts and filters every column, which is the "sortable and
searchable" name and email they asked for.

The counts are the ones the Healthcare page's "My ..." shortcuts show each
counsellor, so the two cannot disagree:

- caregivers: Patient.custom_counsellor_name (the registering counsellor);
- visits: Ticket.counsellor_name, cancelled visits left out;
- follow-ups: Sparsh Follow-up Tracker.counsellor, leaving out the statuses
  that end a follow-up (Not Interested, No Response, Closed).
"""

from __future__ import annotations

import frappe
from frappe import _

from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import FINISHED

NO_COUNSELLOR = "(no counsellor recorded)"


def build_rows(users, caregivers, visits, follow_ups):
	"""One row per counsellor, by name. `users` maps a login to its full name
	(every enabled Volunteer); the three count maps are keyed by login. A login
	with a count but not in `users` (a disabled account, say) is listed too,
	and records with no counsellor (1 draft visit on 30-Oct-2026) get a row of
	their own, so no record goes uncounted and the columns add up to the
	page's totals."""
	caregivers, visits, follow_ups = (_blank_as_one(m) for m in (caregivers, visits, follow_ups))
	logins = set(users) | set(caregivers) | set(visits) | set(follow_ups)
	rows = [
		{
			"counsellor_name": users.get(login) or login or NO_COUNSELLOR,
			"counsellor_email": login,
			"caregivers": caregivers.get(login, 0),
			"visits": visits.get(login, 0),
			"follow_ups": follow_ups.get(login, 0),
		}
		for login in logins
	]
	return sorted(rows, key=lambda r: (not r["counsellor_email"], r["counsellor_name"].lower(), r["counsellor_email"]))


def _blank_as_one(counts):
	"""None and "" are both "no counsellor": one key, their counts added."""
	out = {}
	for login, n in counts.items():
		out[login or ""] = out.get(login or "", 0) + n
	return out


def _counts(doctype, field, filters):
	rows = frappe.get_all(doctype, filters=filters, fields=[field, {"COUNT": "*", "as": "n"}], group_by=field)
	return {r[field]: r["n"] for r in rows}


def execute(filters=None):
	users = dict(
		frappe.db.sql(
			"""select u.name, u.full_name from `tabUser` u
			where u.enabled = 1
				and exists (select 1 from `tabHas Role` r
					where r.parent = u.name and r.parenttype = 'User' and r.role = 'Volunteer')"""
		)
	)
	rows = build_rows(
		users,
		_counts("Patient", "custom_counsellor_name", {}),
		_counts("Ticket", "counsellor_name", {"docstatus": ["<", 2]}),
		_counts("Sparsh Follow-up Tracker", "counsellor", {"follow_up_status": ["not in", FINISHED]}),
	)
	return _columns(), rows


def _columns():
	return [
		{"fieldname": "counsellor_name", "label": _("Counsellor Name"), "fieldtype": "Data", "width": 220},
		{
			"fieldname": "counsellor_email",
			"label": _("Counsellor Email Id"),
			"fieldtype": "Data",
			"width": 260,
		},
		{"fieldname": "caregivers", "label": _("Total Caregivers"), "fieldtype": "Int", "width": 140},
		{"fieldname": "visits", "label": _("Total Visits"), "fieldtype": "Int", "width": 120},
		{"fieldname": "follow_ups", "label": _("Total Follow-ups"), "fieldtype": "Int", "width": 140},
	]
