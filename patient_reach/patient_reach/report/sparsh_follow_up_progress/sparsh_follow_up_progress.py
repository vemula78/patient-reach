# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sparsh Follow-Up Progress -- one row per call, plus a breakdown of pledge
progress and traffic-light movement.

Follows the trust_compliance Script Report shape: `execute()` returns
(columns, data, message, chart); pure aggregation lives in module-level
functions with no `frappe` import so they can be unit tested without a bench
(tests/... in this app has no local bench -- see CLAUDE.md).

Decision 5 (PLAN.md): a blank lifestyle answer is missing, never zero. This
report never shows `habit_score` without `habit_answered` beside it --
`habit_score_display` (already "N healthy of M answered; K not answered",
computed server-side in sparsh_follow_up.py) is the only habit column here.
"""

from __future__ import annotations

import frappe
from frappe import _

PROGRESS_OPTIONS = ["Achieved", "Partially Achieved", "Self-Modified", "Not Yet Achieved"]
NOT_RECORDED = "Not Recorded"


def execute(filters: dict | None = None):
	filters = filters or {}
	rows = _fetch(filters)
	return _columns(), rows, _message(rows), _chart(rows)


def _fetch(filters: dict) -> list[dict]:
	conditions = {"docstatus": ["!=", 2]}
	if filters.get("coach_id"):
		conditions["coach_id"] = filters["coach_id"]
	if filters.get("call_disposition"):
		conditions["call_disposition"] = filters["call_disposition"]
	if filters.get("from_date") and filters.get("to_date"):
		conditions["scheduled_date"] = ["between", [filters["from_date"], filters["to_date"]]]

	return frappe.get_all(
		"Sparsh Follow Up",
		filters=conditions,
		fields=[
			"name",
			"caregiver_id",
			"baseline_ticket",
			"coach_id",
			"follow_up_week",
			"scheduled_date",
			"actual_call_date",
			"call_disposition",
			"pledge_progress_raw",
			"habit_score_display",
			"current_traffic_light",
			"traffic_light_transition",
			"traffic_light_change_category",
			"next_call_date",
			"safety_red_flag",
			"clinical_review_status",
			"docstatus",
		],
		order_by="scheduled_date desc, name desc",
	)


def progress_breakdown(rows: list[dict]) -> list[dict]:
	"""Count of `pledge_progress_raw` across the given rows, with an explicit
	"Not Recorded" bucket for blanks (Decision 5's rule applied to a Select
	breakdown, not just the habit score) -- a blank must be its own row, never
	folded into any option or silently dropped."""
	counts = {option: 0 for option in PROGRESS_OPTIONS}
	counts[NOT_RECORDED] = 0
	for row in rows:
		value = row.get("pledge_progress_raw")
		counts[value if value in counts else NOT_RECORDED] += 1
	return [{"pledge_progress_raw": key, "count": value} for key, value in counts.items()]


def _message(rows: list[dict]) -> str:
	total = len(rows)
	connected = sum(1 for r in rows if r.get("call_disposition") == "Connected")
	pending_review = sum(
		1 for r in rows if r.get("safety_red_flag") and r.get("clinical_review_status") == "Pending"
	)
	breakdown = progress_breakdown(rows)
	achieved = sum(
		r["count"] for r in breakdown if r["pledge_progress_raw"] in ("Achieved", "Partially Achieved")
	)

	lines = [
		_("{0} calls, {1} connected.").format(total, connected),
		_("{0} pledges achieved or partially achieved.").format(achieved),
	]
	if pending_review:
		lines.append("<b>" + _("{0} red flags awaiting clinical review.").format(pending_review) + "</b>")
	return "<br>".join(lines)


def _chart(rows: list[dict]) -> dict:
	breakdown = progress_breakdown(rows)
	return {
		"data": {
			"labels": [_(row["pledge_progress_raw"]) for row in breakdown],
			"datasets": [{"name": _("Calls"), "values": [row["count"] for row in breakdown]}],
		},
		"type": "bar",
	}


def _columns() -> list[dict]:
	return [
		{
			"fieldname": "name",
			"label": _("Follow Up"),
			"fieldtype": "Link",
			"options": "Sparsh Follow Up",
			"width": 110,
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
		{"fieldname": "follow_up_week", "label": _("Week"), "fieldtype": "Int", "width": 60},
		{"fieldname": "scheduled_date", "label": _("Scheduled"), "fieldtype": "Date", "width": 95},
		{"fieldname": "call_disposition", "label": _("Outcome"), "fieldtype": "Data", "width": 110},
		{"fieldname": "pledge_progress_raw", "label": _("Progress"), "fieldtype": "Data", "width": 140},
		{"fieldname": "habit_score_display", "label": _("Habits"), "fieldtype": "Data", "width": 220},
		{"fieldname": "current_traffic_light", "label": _("Traffic Light"), "fieldtype": "Data", "width": 90},
		{"fieldname": "traffic_light_transition", "label": _("Movement"), "fieldtype": "Data", "width": 110},
		{
			"fieldname": "traffic_light_change_category",
			"label": _("Direction"),
			"fieldtype": "Data",
			"width": 100,
		},
		{"fieldname": "next_call_date", "label": _("Next Call"), "fieldtype": "Date", "width": 95},
		{"fieldname": "coach_id", "label": _("Coach"), "fieldtype": "Link", "options": "User", "width": 140},
	]
