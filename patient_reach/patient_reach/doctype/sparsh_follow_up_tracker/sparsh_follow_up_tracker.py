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

CALLS = (1, 2, 3)

# "May be" counts as going on, as the change request says for both the next
# call's section and the editable Next Follow-up Date.
GOING_ON = ("Yes", "May be")

# Statuses that end the follow-up: no call is due after any of them. "Not
# Interested" and "No Response" were added on 09-Oct-2026 at the counselling
# team's request, from their experience of the calls made so far.
FINISHED = ("Not Interested", "No Response", "Closed")

# What a counsellor enters in a call. The Scheduled Date is not here: the
# system sets it.
CALL_ENTRY_FIELDS = ("actual_date", "duration", "outcome", "by", "interest", "next_date", "notes")


def is_eligible(caregiver_interested, ready_to_change):
	"""A visit puts its caregiver on the follow-up list when the caregiver is
	interested in the programme OR ready to make a change ("those that are
	interested in the program and those that are interested in making a
	change" -- both groups)."""
	return caregiver_interested == "Yes" or ready_to_change in GOING_ON


def latest_eligible_visit(visits):
	"""The name of the first eligible visit in `visits` (newest first), or None.

	Each visit carries `name`, `caregiver_interested` and
	`are_you_ready_to_make_a_change_for_a_healthy_you`."""
	for v in visits:
		if is_eligible(v.get("caregiver_interested"), v.get("are_you_ready_to_make_a_change_for_a_healthy_you")):
			return v["name"]
	return None


def call_has_entry(values, n):
	"""True when anything has been entered for call `n`."""
	return any(values.get(f"call_{n}_{field}") for field in CALL_ENTRY_FIELDS)


def any_call_entry(values):
	return any(call_has_entry(values, n) for n in CALLS)


def call_is_open(values, n):
	"""Call 1 always; call 2 or 3 only when the previous call's interest is
	Yes or May be. None of the calls is open when the caregiver's acceptance to
	change is No (the change request, 23-Oct-2026). The same test as the
	sections' `depends_on`."""
	if values.get("acceptance_to_change") == "No":
		return False
	return n == 1 or values.get(f"call_{n - 1}_interest") in GOING_ON


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
	"""
	if values.get("follow_up_status") in FINISHED:
		return None
	for n in CALLS:
		if not call_is_open(values, n):
			return None
		if not values.get(f"call_{n}_actual_date"):
			return values.get(f"call_{n}_scheduled_date") or None
	return None


class SparshFollowupTracker(Document):
	def validate(self):
		self.update(prepopulate_prevention_levels(self.as_dict()))
		values = self.as_dict()
		errors = check_calls(values)
		# The 23-Oct-2026 rules apply when a counsellor saves the calls. A visit's
		# save also re-saves its tracker (doc_events), and a tracker entered before
		# these rules must not stop that visit from saving.
		if not self.flags.get("synced_from_visit"):
			errors += check_acceptance(values) + missing_when_not_connected(values)
		if errors:
			frappe.throw("<br>".join(_(e) for e in errors))
		self.update(chained_schedule(values))
		self.next_call_date = next_call_due(self.as_dict())
