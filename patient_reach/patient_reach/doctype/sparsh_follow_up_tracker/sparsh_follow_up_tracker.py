# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""Sai Sparsh follow-up of one caregiver, over up to three calls.

The counselling team's "Follow-up version 1" change request, approved by Dr
Nayanjeet Chaudhury on 06-Oct-2026: a list of the caregivers to follow up in
place of an "Add Follow Up" button, and a short form of three calls. The full
`Sparsh Follow Up` form (Follow-Up Tool v3, one record per call attempt) is
left exactly as it was and only taken off the workspace, so it can return.

One record per caregiver (`caregiver_id` is unique). It is created by the
visit's save hook (`doc_events.ticket_sync_follow_up_tracker`), never by hand:
counsellors have no create permission, which is also what removes the list's
Add button. The Baseline State fields are `fetch_from` the visit, and Frappe
re-fetches them on every save of this record.

The rules below are module-level functions with no `frappe`, so they are
pinned by unit tests without a bench.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from patient_reach import drl_v14 as drl

CALLS = (1, 2, 3)

# "May be" counts as going on, as the change request says for both the next
# call's section and the editable Next Follow-up Date.
GOING_ON = ("Yes", "May be")

# Statuses that end the follow-up: no call is due after any of them. "Not
# Interested" and "No Response" were added on 09-Oct-2026 at the counselling
# team's request, from their experience of the calls made so far.
FINISHED = ("Not Interested", "No Response", "Closed")

REVIEWER_ROLE = "Sparsh Clinical Reviewer"

# What a counsellor enters in a call. The Scheduled Date is not here: the
# system sets it.
CALL_ENTRY_FIELDS = ("actual_date", "duration", "outcome", "by", "interest", "next_date", "notes")


def is_eligible(caregiver_interested, ready_to_change, referral_priority=None):
	"""A visit puts its caregiver on the follow-up list when the caregiver is
	interested in the programme OR ready to make a change ("those that are
	interested in the program and those that are interested in making a
	change" -- both groups). Under DRL v1.4 a visit that needs a physician
	referral does too, whatever the caregiver's interest: the referral has to
	be followed through (Dr Nayanjeet, 13-Oct-2026, C)."""
	return (
		caregiver_interested == "Yes"
		or ready_to_change in GOING_ON
		or referral_priority in drl.REFERRAL_PRIORITIES
	)


def latest_eligible_visit(visits):
	"""The name of the first eligible visit in `visits` (newest first), or None.

	Each visit carries `name`, `caregiver_interested` and
	`are_you_ready_to_make_a_change_for_a_healthy_you`, and may carry
	`referral_priority`."""
	for v in visits:
		if is_eligible(
			v.get("caregiver_interested"),
			v.get("are_you_ready_to_make_a_change_for_a_healthy_you"),
			v.get("referral_priority"),
		):
			return v["name"]
	return None


def call_has_entry(values, n):
	"""True when anything has been entered for call `n`."""
	return any(values.get(f"call_{n}_{field}") for field in CALL_ENTRY_FIELDS)


def any_call_entry(values):
	return any(call_has_entry(values, n) for n in CALLS)


def previous_going_on(values, n):
	"""The caregiver said Yes or May be on call `n - 1`."""
	return values.get(f"call_{n - 1}_interest") in GOING_ON


def call_is_open(values, n):
	"""Call 1 always; call 2 or 3 only when the previous call's interest is
	Yes or May be and it was not a call that failed to connect (change request
	of 29-Oct-2026). None of the calls is open when the caregiver's acceptance
	to change is No (23-Oct-2026). The same test as the sections' `depends_on`.

	A call already entered stays open: on 30-Oct-2026 three caregivers on care
	had a call 2 after a call 1 that did not connect, and hiding it would hide
	what the counsellor recorded."""
	if values.get("acceptance_to_change") == "No":
		return False
	if n == 1:
		return True
	outcome = values.get(f"call_{n - 1}_outcome")
	connected = outcome in (None, "", "Connected")
	return previous_going_on(values, n) and (connected or call_has_entry(values, n))


# What a counsellor must fill in a call that was not connected, or where the
# caregiver said No. Interest is only on calls 1 and 2; call 3 has no interest.
NOT_CONNECTED_FIELDS = ("prevention_level", "actual_date", "duration", "by", "interest", "notes")


def is_not_connected(values, n):
	"""True when call `n` has an outcome other than Connected, or the caregiver
	said No. A blank outcome is not yet entered, so it does not count."""
	outcome = values.get(f"call_{n}_outcome")
	interest = values.get(f"call_{n}_interest") if n < 3 else None
	return bool((outcome and outcome != "Connected") or interest == "No")


def missing_when_not_connected(values):
	"""The errors for an open call that was not connected, or where the caregiver
	said No, with a field left blank. Everything in the call is required except
	the Next Follow-up Date. `mandatory_depends_on` is client-side only, so an
	API save or an import would get past it without this."""
	errors = []
	for n in CALLS:
		if not call_is_open(values, n) or not is_not_connected(values, n):
			continue
		fields = NOT_CONNECTED_FIELDS if n < 3 else tuple(f for f in NOT_CONNECTED_FIELDS if f != "interest")
		missing = [f for f in fields if not values.get(f"call_{n}_{f}")]
		if missing:
			errors.append(
				f"Call {n}: fill in {', '.join(missing)}, because the call was not connected or the caregiver said No."
			)
	return errors


def check_acceptance(values):
	"""No call may be entered when the caregiver's acceptance to change is No."""
	if values.get("acceptance_to_change") == "No" and any_call_entry(values):
		return ["The caregiver's acceptance to change is No, so no follow-up call can be entered."]
	return []


def prepopulate_prevention_levels(values):
	"""Each open call's Current Prevention Level: the one entered, else the level
	before it (the intake level for call 1). Only the calls shown on the form."""
	fill = {}
	previous = values.get("prevention_level")
	for n in CALLS:
		if not call_is_open(values, n):
			continue
		level = values.get(f"call_{n}_prevention_level") or previous
		fill[f"call_{n}_prevention_level"] = level
		previous = level
	return fill


def check_calls(values):
	"""Return the errors the form's own `depends_on` would hide but an API save
	or an import would not: a Next Follow-up Date without a Yes/May be, and a
	call entered after a previous call's interest went No or blank."""
	errors = []
	for n in (1, 2):
		if values.get(f"call_{n}_next_date") and values.get(f"call_{n}_interest") not in GOING_ON:
			errors.append(
				f"Call {n}: a Next Follow-up Date needs the caregiver's interest to be Yes or May be."
			)
	for n in (2, 3):
		not_refused = values.get("acceptance_to_change") != "No"
		if call_has_entry(values, n) and not call_is_open(values, n) and not_refused:
			errors.append(
				f"Call {n} has entries, but call {n - 1}'s interest is not Yes or May be. "
				f"Change call {n - 1}'s interest back, or clear call {n}."
			)
	return errors


def chained_schedule(values):
	"""Calls 2 and 3 are scheduled for the previous call's Next Follow-up Date."""
	return {
		"call_2_scheduled_date": values.get("call_1_next_date") or None,
		"call_3_scheduled_date": values.get("call_2_next_date") or None,
	}


def next_call_due(values):
	"""The Scheduled Date of the first open call not yet made, for the list.

	None once the follow-up is finished (FINISHED), once every open call has an Actual Call Date, or when the
	next call has no Scheduled Date (a visit without a Follow-up Date).

	Call 1 of a referral that gets the day-3 call (`referral_call_date`) is due
	on day 3 when that comes before its Scheduled Date, or when it has none.
	The counsellor's Follow-up Date is kept as it was entered.
	"""
	if values.get("follow_up_status") in FINISHED:
		return None
	for n in CALLS:
		if not call_is_open(values, n):
			return None
		if not values.get(f"call_{n}_actual_date"):
			dates = [str(values.get(f"call_{n}_scheduled_date") or "")[:10]]
			if n == 1:
				dates.append(str(values.get("referral_call_date") or "")[:10])
			return min((d for d in dates if d), default=None)
	return None


def review_reasons(values, events, baseline_level):
	"""Why a follow-up row goes to the clinical reviewer, or []: a red flag on
	a call, an event reported on a call, and a qualifying event the baseline
	visit's Prevention Level does not show (a Level 4 discrepancy)."""
	reasons = []
	if values.get("call_red_flag"):
		reasons.append("Red-flag symptom reported on a follow-up call")
	for row in events:
		if row.get("event_type"):
			reasons.append(f"{row['event_type']} reported on follow-up: {drl.event_level_4(row)}")
	qualifying = any(drl.event_qualifies(row) for row in events)
	if qualifying and not str(baseline_level or "").startswith("Level 4"):
		reasons.append(f"Level 4 event on the follow-up list; the visit shows {baseline_level or 'no Level'}")
	return reasons


class SparshFollowupTracker(Document):
	def validate(self):
		from patient_reach.doc_events import _event_rows, level_4_reasons

		self.update(prepopulate_prevention_levels(self.as_dict()))
		values = self.as_dict()
		errors = check_calls(values) + drl.disposition_errors(values, REVIEWER_ROLE in frappe.get_roles())
		# The 23-Oct-2026 rules apply when a counsellor saves the calls. A visit's
		# save also re-saves its tracker (doc_events), and a tracker entered before
		# these rules must not stop that visit from saving.
		if not self.flags.get("synced_from_visit"):
			errors += check_acceptance(values) + missing_when_not_connected(values)
		if errors:
			frappe.throw("<br>".join(_(e) for e in errors))
		self.update(chained_schedule(values))
		self.referral_call_date = drl.referral_call_date(self.referral_priority, self.referral_date)
		self.next_call_date = next_call_due(self.as_dict())
		for row in self.get("health_events") or []:
			row.level_4_status = drl.event_level_4(row)
		self.level_4_lock = drl.level_4_note(
			level_4_reasons(self.caregiver_id, self.doctype, self.name, self.get("health_events"))
		)
		events = _event_rows(self.get("health_events"))
		self.review_reasons = "\n".join(review_reasons(self.as_dict(), events, self.prevention_level)) or None

	def on_update(self):
		from patient_reach.doc_events import assign_for_review

		assign_for_review(self)
