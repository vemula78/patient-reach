# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sparsh Clinical Safety Review -- the one-time review list Dr Nayanjeet
Chaudhury asked for on 13-Oct-2026 (his answer to Q12 of the BP and stroke rules
proposal), before any new rule is built:

- every visit whose first BP reading is 160/100 or above (Severe: 180/120 or
  above, as in his 07-Oct rule's Urgent band; High-priority: the rest);
- every visit whose "Any other medical conditions?" text mentions a stroke or
  paralysis. The form has no Stroke condition, so free text is the only record.

Read-only: it changes no visit, and grades nothing by the new rules -- he asked
that the original entries be kept as they are. Opened only by the Sparsh
Clinical Reviewer role (fixtures/role.json). Frappe also requires report access
to Ticket, which he has through Doctor; a reviewer added later needs both.

Blank is never shown as a negative answer (his instruction D): a referral with
no tick is "Not recorded", not "No referral", and the concerning-symptoms tick
can only say "Ticked" or "Not ticked", because the form cannot tell an
unasked question from a No.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import strip_html

from patient_reach.doc_events import _bp_pair

SEVERE = "Severe BP (180/120 or above)"
HIGH_PRIORITY = "High-priority BP (160/100 to 179/119)"
STROKE = "Stroke or paralysis mentioned"

# Word-bounded so "dementia" is not a TIA. "paraly" catches paralysis/paralysed:
# he asked for a vague "paralysis" to be clarified, not taken as a stroke, so
# the matched word is shown beside the text.
_STROKE_WORDS = re.compile(r"stroke|\bcva\b|paraly|hemipleg|brain attack|\btia\b", re.I)

REFERRALS = (
	("cardiology", "Cardiology"),
	("general_medicine_high_bp", "General Medicine (High BP)"),
	("physiotherapy", "Physiotherapy"),
	("dietician", "Dietician"),
	("counselling", "Counselling"),
	("other", "Other"),
)


def bp_band(bp_reading) -> str | None:
	"""SEVERE, HIGH_PRIORITY or None, from the first reading only: a lower
	repeat does not take a visit off the list (his answer to Q3)."""
	pair = _bp_pair(bp_reading)
	if not pair:
		return None
	systolic, diastolic = pair
	if systolic >= 180 or diastolic >= 120:
		return SEVERE
	if systolic >= 160 or diastolic >= 100:
		return HIGH_PRIORITY
	return None


def stroke_word(text) -> str | None:
	"""The word that put the visit on the list, lower-cased, or None."""
	m = _STROKE_WORDS.search(str(text or ""))
	return m.group(0).lower() if m else None


def referral_recorded(row: dict) -> str:
	ticked = [label for field, label in REFERRALS if row.get(field)]
	if ticked:
		return ", ".join(ticked)
	if row.get("none"):
		return "None (ticked)"
	return "Not recorded"


def notes_recorded(row: dict) -> str:
	"""Whether the forwarded doctor wrote anything on the visit."""
	for field in ("examination", "advice", "close_remarks"):
		if strip_html(str(row.get(field) or "")).strip():
			return "Recorded"
	return "Not recorded"


def last_call(tracker: dict | None) -> tuple:
	"""(date, outcome) of the latest call entered on the follow-up tracker."""
	if not tracker:
		return None, None
	for n in (3, 2, 1):
		if tracker.get(f"call_{n}_actual_date"):
			return tracker[f"call_{n}_actual_date"], tracker.get(f"call_{n}_outcome") or "Not recorded"
	return None, None


_ORDER = {SEVERE: 0, HIGH_PRIORITY: 1}


def review_rows(visits: list[dict], trackers: dict[str, dict]) -> list[dict]:
	result = []
	for v in visits:
		band = bp_band(v.get("bp_reading"))
		word = stroke_word(v.get("any_other_medical_condition"))
		if not band and not word:
			continue
		tracker = trackers.get(v.get("patient_id"))
		call_date, call_outcome = last_call(tracker)
		result.append(
			{
				"reason": "; ".join(r for r in (band, word and STROKE) if r),
				"name": v["name"],
				"patient_id": v.get("patient_id"),
				"counselled_date": v.get("counselled_date"),
				"visit_state": {0: "Draft", 1: "Submitted"}.get(v.get("docstatus")),
				"bp_reading": v.get("bp_reading"),
				"bp_repeat_reading": v.get("bp_repeat_reading") or "Not recorded",
				"symptoms": "Ticked" if v.get("bp_concerning_symptoms") else "Not ticked",
				"bp_status": v.get("bp_status"),
				"bp_action": v.get("bp_action"),
				"prevention_level": v.get("prevention_level") or "Not recorded",
				"stroke_word": word,
				"any_other_medical_condition": v.get("any_other_medical_condition"),
				"referral": referral_recorded(v),
				"red_flag_other_reason": v.get("red_flag_other_reason"),
				"forward_to": v.get("forward_to"),
				"doctor_notes": notes_recorded(v),
				"follow_up_status": (tracker or {}).get("follow_up_status") or "No follow-up record",
				"last_call_date": call_date,
				"last_call_outcome": call_outcome,
				"_band": band,
			}
		)
	result.sort(key=lambda r: (_ORDER.get(r["_band"], 2), str(r["counselled_date"] or ""), r["name"]))
	return result


def execute(filters: dict | None = None):
	visits = frappe.get_all(
		"Ticket",
		filters={"docstatus": ["<", 2], "ticket_type": "Preventive Cardiology"},
		fields=[
			"name",
			"patient_id",
			"counselled_date",
			"docstatus",
			"bp_reading",
			"bp_repeat_reading",
			"bp_concerning_symptoms",
			"bp_status",
			"bp_action",
			"prevention_level",
			"any_other_medical_condition",
			*(field for field, _label in REFERRALS),
			"none",
			"red_flag_other_reason",
			"forward_to",
			"examination",
			"advice",
			"close_remarks",
		],
	)
	trackers = {
		t.caregiver_id: t
		for t in frappe.get_all(
			"Sparsh Follow-up Tracker",
			fields=[
				"caregiver_id",
				"follow_up_status",
				*(f"call_{n}_{f}" for n in (1, 2, 3) for f in ("actual_date", "outcome")),
			],
		)
	}
	rows = review_rows(visits, trackers)
	return _columns(), rows, _message(rows), None


def _message(rows: list[dict]) -> str:
	severe = sum(1 for r in rows if r["_band"] == SEVERE)
	high = sum(1 for r in rows if r["_band"] == HIGH_PRIORITY)
	stroke = [r for r in rows if r["stroke_word"]]
	below_4 = sum(1 for r in stroke if not str(r["prevention_level"]).startswith("Level 4"))
	return _(
		"{0} visits with a first BP of 160/100 or above ({1} severe, {2} high-priority); "
		"{3} visits mentioning stroke or paralysis, {4} of them below Level 4. "
		"Entries are shown as recorded. Not recorded means the form holds no entry, "
		"not that nothing was done."
	).format(severe + high, severe, high, len(stroke), below_4)


def _columns() -> list[dict]:
	return [
		{"fieldname": "reason", "label": _("Why listed"), "fieldtype": "Data", "width": 220},
		{"fieldname": "name", "label": _("Visit"), "fieldtype": "Link", "options": "Ticket", "width": 110},
		{
			"fieldname": "patient_id",
			"label": _("Caregiver"),
			"fieldtype": "Link",
			"options": "Patient",
			"width": 140,
		},
		{"fieldname": "counselled_date", "label": _("Visit Date"), "fieldtype": "Date", "width": 95},
		{"fieldname": "visit_state", "label": _("Visit State"), "fieldtype": "Data", "width": 85},
		{"fieldname": "bp_reading", "label": _("BP Recorded"), "fieldtype": "Data", "width": 95},
		{"fieldname": "bp_repeat_reading", "label": _("Repeat BP"), "fieldtype": "Data", "width": 95},
		{"fieldname": "symptoms", "label": _("Concerning Symptoms"), "fieldtype": "Data", "width": 100},
		{"fieldname": "bp_status", "label": _("BP Status (as recorded)"), "fieldtype": "Data", "width": 100},
		{"fieldname": "bp_action", "label": _("BP Action (as recorded)"), "fieldtype": "Data", "width": 200},
		{"fieldname": "prevention_level", "label": _("Prevention Level"), "fieldtype": "Data", "width": 95},
		{"fieldname": "stroke_word", "label": _("Stroke Wording"), "fieldtype": "Data", "width": 90},
		{
			"fieldname": "any_other_medical_condition",
			"label": _("Other Medical Conditions"),
			"fieldtype": "Small Text",
			"width": 200,
		},
		{"fieldname": "referral", "label": _("Referral Ticked"), "fieldtype": "Data", "width": 170},
		{
			"fieldname": "red_flag_other_reason",
			"label": _("Other Referral Reason"),
			"fieldtype": "Small Text",
			"width": 150,
		},
		{
			"fieldname": "forward_to",
			"label": _("Forwarded To"),
			"fieldtype": "Link",
			"options": "User",
			"width": 150,
		},
		{
			"fieldname": "doctor_notes",
			"label": _("Doctor's Notes on Visit"),
			"fieldtype": "Data",
			"width": 100,
		},
		{"fieldname": "follow_up_status", "label": _("Follow-up Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "last_call_date", "label": _("Last Call"), "fieldtype": "Date", "width": 95},
		{
			"fieldname": "last_call_outcome",
			"label": _("Last Call Outcome"),
			"fieldtype": "Data",
			"width": 140,
		},
	]
