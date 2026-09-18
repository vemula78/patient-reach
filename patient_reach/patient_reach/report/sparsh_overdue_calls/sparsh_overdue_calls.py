# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sparsh Overdue Calls -- the latest not-cancelled Sparsh Follow Up per
`baseline_ticket` whose `next_call_date` has passed and no later call has been
recorded against that ticket.

"Latest" is by `follow_up_week` (the counselling programme's own sequence),
tie-broken by `actual_call_date` then `creation`, matching PLAN.md's rule for
the previous-call lookup ("order by actual_call_date desc") -- this report
picks the same "latest" record a counsellor opening the caregiver would see.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today


def execute(filters: dict | None = None):
	filters = filters or {}
	rows = _fetch(filters)
	overdue = overdue_calls(rows, getdate(today()))
	return _columns(), overdue, _message(overdue), None


def _fetch(filters: dict) -> list[dict]:
	conditions = {"docstatus": ["!=", 2]}
	if filters.get("coach_id"):
		conditions["coach_id"] = filters["coach_id"]

	return frappe.get_all(
		"Sparsh Follow Up",
		filters=conditions,
		fields=[
			"name",
			"caregiver_id",
			"call_disposition",
			"baseline_ticket",
			"coach_id",
			"follow_up_week",
			"actual_call_date",
			"next_call_date",
			"current_traffic_light",
			"creation",
		],
	)


def latest_per_ticket(rows: list[dict]) -> dict[str, dict]:
	"""One row per `baseline_ticket`: the most recent **connected** call.

	Only a connected call sets `next_call_date`, so only a connected call can
	move the schedule. Unanswered attempts are deliberately ignored here --
	they are recorded (decision 1) but they neither reschedule the caregiver
	nor clear them from this list. Selecting the latest row of *any*
	disposition made a week-6 "No Answer" supersede the week-2 connected call
	that scheduled week 6, so the caregiver vanished from the working list at
	exactly the moment a call had failed.

	Ordered by `actual_call_date`, then `creation` -- real call chronology, not
	programme week, so a backfilled or corrected week cannot win over a later
	call. A row with no `baseline_ticket` is skipped: it cannot be grouped, and
	the form's `reqd` means it should not exist outside a corrupt import.
	"""
	best: dict[str, dict] = {}
	for row in rows:
		ticket = row.get("baseline_ticket")
		if not ticket or row.get("call_disposition") != "Connected":
			continue
		current = best.get(ticket)
		if current is None or _sort_key(row) > _sort_key(current):
			best[ticket] = row
	return best


def _sort_key(row: dict):
	"""Sortable key with no mixed types.

	`actual_call_date` arrives as a `datetime.date` when set and `None` when
	not. Substituting `""` for the missing case made Python compare `str` with
	`date` and raise `TypeError` as soon as one ticket had both -- a connected
	call and a same-week unanswered retry, which decision 1 makes routine.
	Every element is coerced to `str` so the ordering is total and ISO dates
	still sort correctly.
	"""
	return (
		str(row.get("actual_call_date") or ""),
		str(row.get("creation") or ""),
	)


def overdue_calls(rows: list[dict], as_of) -> list[dict]:
	"""The latest record per ticket, filtered to `next_call_date < as_of`.
	A latest record with no `next_call_date` (e.g. a not-connected call, where
	the field is not asked) is not overdue -- there is nothing to be overdue
	against -- so it is excluded rather than treated as always-due."""
	latest = latest_per_ticket(rows)
	result = []
	for row in latest.values():
		next_call = row.get("next_call_date")
		if not next_call:
			continue
		if getdate(next_call) < as_of:
			result.append(row)
	result.sort(key=lambda r: r.get("next_call_date"))
	return result


def _message(rows: list[dict]) -> str:
	return _("{0} caregivers have a follow-up call overdue.").format(len(rows))


def _columns() -> list[dict]:
	return [
		{
			"fieldname": "name",
			"label": _("Latest Follow Up"),
			"fieldtype": "Link",
			"options": "Sparsh Follow Up",
			"width": 120,
		},
		{
			"fieldname": "caregiver_id",
			"label": _("Caregiver"),
			"fieldtype": "Link",
			"options": "Patient",
			"width": 140,
		},
		{
			"fieldname": "baseline_ticket",
			"label": _("Baseline Ticket"),
			"fieldtype": "Link",
			"options": "Ticket",
			"width": 110,
		},
		{"fieldname": "follow_up_week", "label": _("Last Week"), "fieldtype": "Int", "width": 80},
		{"fieldname": "next_call_date", "label": _("Was Due"), "fieldtype": "Date", "width": 95},
		{
			"fieldname": "current_traffic_light",
			"label": _("Last Traffic Light"),
			"fieldtype": "Data",
			"width": 110,
		},
		{"fieldname": "coach_id", "label": _("Coach"), "fieldtype": "Link", "options": "User", "width": 140},
	]
