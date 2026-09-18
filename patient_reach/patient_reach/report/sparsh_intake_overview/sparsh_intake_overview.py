# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sparsh Intake Overview -- Select-field breakdowns of the Preventive
Cardiology intake (the `Ticket`, not `Sparsh Follow Up`; there is no baseline
to follow up until an intake exists).

Decision 5 applies here too, not only to the follow-up habit score: every
Select breakdown emits an explicit "Not Recorded" row for a blank value
instead of dropping it, so a report reader cannot mistake "nobody asked" for
"nobody said yes".

Decision 10: Prevention Level (`Level 1`..`Level 4`) and S status
(`Active`/`Inactive`) are two separate columns, never a `Level 2s`-shaped
single value, and "Level 2s" is not itself a level.

`_split_prevention_level` delegates to the pure function of the same rule
in PLAN.md's acceptance check (`split_prevention_level`). It is defined here
rather than imported because it belongs to `sparsh_follow_up.py`/
`doc_events.py`, which are owned by the other builder in this release and were
not present in this repo at the time this report was written -- see this
build's report-back for the exact disagreement-or-absence note. If that
function exists by the time this is reconciled, this local copy should be
deleted in favour of importing it, so the two cannot drift.
"""

from __future__ import annotations

import frappe
from frappe import _

NOT_RECORDED = "Not Recorded"

INTAKE_FILTERS = {
	"ticket_type": "Preventive Cardiology",
	"visit_type": "First Visit",
	"docstatus": ["!=", 2],
}

# fieldname -> the Select options offered on Ticket, options text from
# ticket.json verbatim (minus the leading blank).
BREAKDOWN_FIELDS = {
	"green_plate": ["< 25%", "25% - 50%", "≥ 50%"],
	"sunset_rule": ["Yes", "No"],
	"protein_intake": ["Yes", "No"],
	"sedentary": ["Yes", "No"],
	"post_meal_walk": ["Yes", "No"],
	"consume_heavy": ["Yes", "No"],
	"adequate_sleep": ["Yes", "No"],
	"caregiver_stress": ["Yes", "No"],
	"type_of_stress": [
		"Clinical Stress (Medical related )",
		"Non - Clinical Stress (Family, Financial, Social etc.,)",
		"None",
	],
}

LEVELS = ["Level 1", "Level 2", "Level 3", "Level 4"]
S_STATUSES = ["Active", "Inactive"]


def execute(filters: dict | None = None):
	filters = filters or {}
	tickets = _fetch(filters)
	rows = []
	for fieldname in BREAKDOWN_FIELDS:
		rows += select_breakdown(tickets, fieldname, BREAKDOWN_FIELDS[fieldname])
	rows += prevention_level_breakdown(tickets)
	return _columns(), rows, _message(tickets), None


def _fetch(filters: dict) -> list[dict]:
	conditions = dict(INTAKE_FILTERS)
	if filters.get("nodal_centre"):
		conditions["nodal_centre"] = filters["nodal_centre"]
	return frappe.get_all(
		"Ticket",
		filters=conditions,
		fields=["name", "prevention_level", *BREAKDOWN_FIELDS],
	)


def select_breakdown(rows: list[dict], fieldname: str, options: list[str]) -> list[dict]:
	"""Count of `fieldname` across `rows`, with every option present even at
	zero and an explicit "Not Recorded" bucket for blanks -- Decision 5."""
	counts = {option: 0 for option in options}
	counts[NOT_RECORDED] = 0
	for row in rows:
		value = row.get(fieldname)
		counts[value if value in counts else NOT_RECORDED] += 1
	return [{"field": fieldname, "option": option, "count": count} for option, count in counts.items()]


def _split_prevention_level(value: str | None) -> tuple[str | None, str | None]:
	"""`"Level 2s"` -> `("Level 2", "Active")`; `"Level 3"` -> `("Level 3",
	"Inactive")`; blank -> `(None, None)`; anything else throws -- an
	unrecognised code is a data problem this report should surface loudly, not
	silently count as "Not Recorded".

	Decision 10's rule has exactly one implementation, `split_prevention_level`
	in the Sparsh Follow Up controller, and this wraps it. It used to be a
	second copy: the copy did not `strip()`, so `" Level 2s "` was accepted by
	the controller and threw here. One clinical rule, two implementations, is
	how the two drift apart.

	The controller raises `ValueError` (it is pure, so it stays testable with no
	bench); a report wants `frappe.throw` so the user sees the bad value.
	"""
	from patient_reach.patient_reach.doctype.sparsh_follow_up.sparsh_follow_up import (
		split_prevention_level,
	)

	try:
		return split_prevention_level(value)
	except ValueError:
		frappe.throw(_("Ticket has an unrecognised prevention level: {0}").format(value))


def prevention_level_breakdown(rows: list[dict]) -> list[dict]:
	level_counts = {level: 0 for level in LEVELS}
	level_counts[NOT_RECORDED] = 0
	status_counts = {status: 0 for status in S_STATUSES}
	status_counts[NOT_RECORDED] = 0

	for row in rows:
		level, status = _split_prevention_level(row.get("prevention_level"))
		level_counts[level if level in level_counts else NOT_RECORDED] += 1
		status_counts[status if status in status_counts else NOT_RECORDED] += 1

	result = [{"field": "prevention_level", "option": k, "count": v} for k, v in level_counts.items()]
	result += [{"field": "s_status", "option": k, "count": v} for k, v in status_counts.items()]
	return result


def _message(rows: list[dict]) -> str:
	return _("{0} Preventive Cardiology intake Tickets (not cancelled).").format(len(rows))


def _columns() -> list[dict]:
	return [
		{"fieldname": "field", "label": _("Field"), "fieldtype": "Data", "width": 160},
		{"fieldname": "option", "label": _("Answer"), "fieldtype": "Data", "width": 260},
		{"fieldname": "count", "label": _("Count"), "fieldtype": "Int", "width": 90},
	]
