# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sparsh Clinical Review Queue -- the clinical reviewer's standing list under
DRL v1.4, what Dr Nayanjeet Chaudhury asked to review in Q9 of 13-Oct-2026:
red-flag escalations, severe and high-priority BP, heart and brain events,
referral completion and unresolved follow-up, and Level 4 discrepancies.

Visits graded before DRL v1.4 are not here: their one-time review is the
Sparsh Clinical Safety Review.

Read-only, opened only by the Sparsh Clinical Reviewer role. The referral flags
are worked out on the day the report is run (drl_v14.referral_flags). A blank
is shown as "Not recorded", never as a No.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _

from patient_reach import drl_v14 as drl

NOT_RECORDED = "Not recorded"

VISIT_FIELDS = (
	"name",
	"patient_id",
	"counselled_date",
	"docstatus",
	"red_flag_status",
	"emergency_action",
	"bp_reading",
	"bp_repeat_reading",
	"bp_status",
	"bp_alerts",
	"referral_priority",
	"referral_advised",
	"referral_date",
	"forward_to",
	"prevention_level",
	"level_4_lock",
	"review_reasons",
)
TRACKER_FIELDS = (
	"name",
	"caregiver_id",
	"baseline_ticket",
	"follow_up_status",
	"referral_priority",
	"referral_date",
	"consultation_status",
	"treatment_status",
	"referral_disposition",
	"call_1_actual_date",
	"call_2_actual_date",
	"call_3_actual_date",
	"review_reasons",
)


def _lines(text) -> list[str]:
	return [line for line in str(text or "").splitlines() if line.strip()]


def _last_call(tracker: dict) -> str | None:
	return next(
		(tracker.get(f"call_{n}_actual_date") for n in (3, 2, 1) if tracker.get(f"call_{n}_actual_date")),
		None,
	)


def queue_rows(visits: list[dict], trackers: list[dict], today: date) -> list[dict]:
	"""One row per DRL v1.4 visit that has a reason for review or a referral
	not yet closed, and one per follow-up row with a reason of its own (a red
	flag or event on a call) whose visit is not already listed.

	The follow-up fields are the caregiver's row when that row is on this
	visit; otherwise the visit's referral is shown with no follow-up record,
	and flagged as such."""
	by_caregiver = {t["caregiver_id"]: t for t in trackers}
	rows, listed = [], set()
	for v in visits:
		tracker = by_caregiver.get(v.get("patient_id"))
		own = tracker if tracker and tracker.get("baseline_ticket") == v["name"] else None
		reasons = _lines(v.get("review_reasons")) + _lines((own or {}).get("review_reasons"))
		referral = v.get("referral_priority") in drl.REFERRAL_PRIORITIES
		closed = bool((own or {}).get("referral_disposition"))
		if not reasons and not (referral and not closed):
			continue
		flags = []
		if referral:
			if own:
				flags = drl.referral_flags(own, today)
			else:
				flags = [
					"No follow-up record on this visit",
					*drl.referral_flags(
						{
							"referral_priority": v.get("referral_priority"),
							"referral_date": v.get("referral_date"),
						},
						today,
					),
				]
			if not v.get("referral_advised"):
				flags.insert(0, "Referral advice not recorded")
		if own:
			listed.add(own["name"])
		rows.append(_row(v, own, reasons, flags))
	for t in trackers:
		if t["name"] in listed or not t.get("review_reasons"):
			continue
		rows.append(
			_row(
				{"name": t.get("baseline_ticket"), "patient_id": t.get("caregiver_id")},
				t,
				_lines(t.get("review_reasons")),
				drl.referral_flags(t, today),
			)
		)
	rank = {p: i for i, p in enumerate(drl.PRIORITIES)}
	rows.sort(
		key=lambda r: (
			rank.get(r["referral_priority"], len(rank)),
			str(r["counselled_date"] or ""),
			r["name"] or "",
		)
	)
	return rows


def _row(v: dict, tracker: dict | None, reasons: list[str], flags: list[str]) -> dict:
	tracker = tracker or {}
	return {
		"why": "; ".join(reasons + flags),
		"referral_priority": v.get("referral_priority"),
		"name": v.get("name"),
		"patient_id": v.get("patient_id"),
		"counselled_date": v.get("counselled_date"),
		"visit_state": {0: "Draft", 1: "Submitted"}.get(v.get("docstatus")),
		"red_flag_status": v.get("red_flag_status") or NOT_RECORDED,
		"emergency_action": v.get("emergency_action")
		or (NOT_RECORDED if v.get("red_flag_status") == drl.RF_PRESENT else None),
		"bp_reading": v.get("bp_reading") or NOT_RECORDED,
		"bp_repeat_reading": v.get("bp_repeat_reading") or NOT_RECORDED,
		"bp_status": v.get("bp_status"),
		"bp_alerts": ", ".join(_lines(v.get("bp_alerts"))),
		"referral_advised": v.get("referral_advised")
		or (NOT_RECORDED if v.get("referral_priority") in drl.REFERRAL_PRIORITIES else None),
		"referral_date": v.get("referral_date"),
		"forward_to": v.get("forward_to"),
		"prevention_level": v.get("prevention_level"),
		"level_4_lock": "Yes" if v.get("level_4_lock") else None,
		"tracker": tracker.get("name"),
		"follow_up_status": tracker.get("follow_up_status")
		or ("No follow-up record" if not tracker else NOT_RECORDED),
		"consultation_status": tracker.get("consultation_status") or (NOT_RECORDED if tracker else None),
		"treatment_status": tracker.get("treatment_status") or (NOT_RECORDED if tracker else None),
		"referral_disposition": tracker.get("referral_disposition")
		or ("Open" if tracker.get("referral_priority") in drl.REFERRAL_PRIORITIES else None),
		"last_call_date": _last_call(tracker),
	}


def execute(filters: dict | None = None):
	visits = frappe.get_all(
		"Ticket",
		filters={"docstatus": ["<", 2], "bp_rule": drl.RULE},
		fields=list(VISIT_FIELDS),
	)
	trackers = frappe.get_all("Sparsh Follow-up Tracker", fields=list(TRACKER_FIELDS))
	rows = queue_rows(visits, trackers, frappe.utils.getdate())
	return _columns(), rows, _message(rows), None


def _message(rows: list[dict]) -> str:
	emergencies = sum(1 for r in rows if r["referral_priority"] == drl.P_EMERGENCY)
	flagged = sum(1 for r in rows if r["why"])
	return _(
		"{0} records: {1} emergency referrals, {2} with a reason or flag. Flags are worked out today. "
		"Not recorded means the form holds no entry, not that nothing was done."
	).format(len(rows), emergencies, flagged)


def _col(fieldname, label, fieldtype="Data", width=110, options=None):
	col = {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "width": width}
	if options:
		col["options"] = options
	return col


def _columns() -> list[dict]:
	return [
		_col("why", "Why listed", width=280),
		_col("referral_priority", "Referral Priority", width=170),
		_col("name", "Visit", "Link", 110, "Ticket"),
		_col("patient_id", "Caregiver", "Link", 140, "Patient"),
		_col("counselled_date", "Visit Date", "Date", 95),
		_col("visit_state", "Visit State", width=85),
		_col("red_flag_status", "Red Flags", width=150),
		_col("emergency_action", "Emergency Action", width=170),
		_col("bp_reading", "BP", width=85),
		_col("bp_repeat_reading", "Repeat BP", width=85),
		_col("bp_status", "BP Status", width=100),
		_col("bp_alerts", "BP Alerts", width=180),
		_col("referral_advised", "Referral Advised", width=130),
		_col("referral_date", "Referral Date", "Date", 95),
		_col("forward_to", "Forwarded To", "Link", 150, "User"),
		_col("prevention_level", "Level", width=75),
		_col("level_4_lock", "Level 4 Lock", width=80),
		_col("tracker", "Follow-up Row", "Link", 110, "Sparsh Follow-up Tracker"),
		_col("follow_up_status", "Follow-up Status", width=120),
		_col("consultation_status", "Consultation", width=150),
		_col("treatment_status", "Treatment", width=140),
		_col("referral_disposition", "Referral Closed As", width=170),
		_col("last_call_date", "Last Call", "Date", 95),
	]
