# Copyright (c) 2026, Frugal Scientific and Contributors
# See license.txt

"""Sai Sparsh caregiver follow-up call.

One record per **call attempt** against an intake `Ticket`, including attempts
that never connected (decision 1 of 18-Sep-2026). Not the post-discharge
`Patient Follow-Up` of `sssihms_patient_followup`, and not the orphan child
table `Ticket Follow up`.

The derivations below are a port of the recovered `Sparsh Follow Up - Derive
Fields` **Server Script** from the decommissioned site. They are deliberately
not reinstated as a Server Script: those live only in the site database, are
absent from `bench backup`, require `server_script_enabled` (which grants any
Script Manager arbitrary server-side Python), and cannot be reviewed. Four of
the recovered script's outputs are gone on clinical instruction:

* `pledge_progress_ordinal` -- the 4/3/2/1 progress score (decision 3). The four
  progress categories stay descriptive; nothing ranks them.
* `*_traffic_numeric` -- the three numeric traffic fields (decision 8). Movement
  is described, never scored.
* `call_success_binary` and `coach_pivot_used` -- restatements of a Select the
  record already holds.
* `confidence_adequacy_binary` -- a threshold better applied in a report than
  frozen into a row.

Everything that a report or a test needs is a **pure module-level function**
below: no `frappe`, no database, no `Document`. That is what lets decision 5
(blank is missing, never zero) and the sunset-rule polarity be pinned by unit
tests in an environment with no bench.
"""

import frappe
from frappe import _
from frappe.model.document import Document

# --------------------------------------------------------------------------
# Pure logic -- no frappe, no database, no document
# --------------------------------------------------------------------------

# Decision 4: on the FOLLOW-UP the question is "heaviest meal BEFORE 8 PM?", so
# "Yes" is the compliant answer.
#
# The intake Ticket's `sunset_rule` asks "Does the caregiver have dinner AFTER
# 8 PM ?", where "Yes" is the NON-compliant answer. Same concept, opposite
# polarity. These two must never share a mapping, and the intake report must not
# import this one. `test_sparsh_follow_up.py` pins both polarities.
HABIT_MAPS = {
	"sunset_rule_binary": {"Yes": 1, "No": 0},
	"builder_habit_binary": {"Yes": 1, "No": 0},
	"stress_check_binary": {"Mostly Calm": 1, "Overwhelmed": 0},
	"sleep_check_binary": {"Yes": 1, "No": 0},
}

HABIT_FIELDS = ("sunset_rule_binary", "builder_habit_binary", "stress_check_binary", "sleep_check_binary")

TRAFFIC_ORDER = ("Red", "Yellow", "Green")

# The eight fields a *connected* call must carry. PLAN.md names the count but not
# the list; these are the six the approved form marks required inside the
# connected part of the call, plus the two that only a connected call can have.
# Not-connected attempts may leave every one of them blank.
CONNECTED_ONLY_MANDATORY = (
	"actual_call_date",
	"call_duration_mins",
	"pledge_progress_raw",
	"pledge_category",
	"new_target_pledge_text",
	"confidence_score",
	"current_traffic_light",
	"next_call_date",
)

CONFIDENCE_MIN = 1
CONFIDENCE_MAX = 10


def habit_summary(sunset, builder, stress, sleep):
	"""Return `(healthy, answered, display)` for the four lifestyle questions.

	Decision 5: **a blank answer is missing, never zero.** Frappe's `Int` cannot
	be NULL, so a stored `habit_score` of 0 is ambiguous on its own -- it is the
	same value for "four unhealthy answers" and for "nothing was asked". The
	denominator therefore travels with the score everywhere, which is what
	`answered` and `display` are for, and why `habit_score` is never in a list
	view or a report column without `habit_answered` beside it.

	A value that is neither blank nor an option the form offers raises rather
	than counting as zero; the parity test asserts the maps cover every option,
	so the form cannot produce one.
	"""
	healthy = 0
	answered = 0
	for fieldname, value in zip(HABIT_FIELDS, (sunset, builder, stress, sleep), strict=True):
		if value in (None, ""):
			continue
		mapping = HABIT_MAPS[fieldname]
		if value not in mapping:
			raise ValueError(f"{fieldname}: {value!r} is not an answer this form offers")
		answered += 1
		healthy += mapping[value]
	not_answered = len(HABIT_FIELDS) - answered
	display = f"{healthy} healthy of {answered} answered; {not_answered} not answered"
	return healthy, answered, display


def traffic_movement(previous, current):
	"""Return `(transition, category)`, e.g. `("Yellow → Green", "Improvement")`.

	Decision 8: descriptive only. No numeric traffic value is stored, so nothing
	invites a mean of a colour. Either side missing yields `(None, None)` --
	there is no movement to describe on a first call.
	"""
	if previous not in TRAFFIC_ORDER or current not in TRAFFIC_ORDER:
		return None, None
	before, after = TRAFFIC_ORDER.index(previous), TRAFFIC_ORDER.index(current)
	if after > before:
		category = "Improvement"
	elif after < before:
		category = "Relapse"
	else:
		category = "Maintenance"
	return f"{previous} → {current}", category


def split_prevention_level(prevention_level):
	"""Split an intake `prevention_level` code into `(level, s_status)`.

	Decision 10: `Level 2s` is two facts -- prevention level 2, and an active "s"
	modifier (past surgeries / structural illness). Reported together they cannot
	be counted apart, so the follow-up stores them apart. The Ticket's own
	storage is untouched; this only reads it.

	Blank gives `(None, None)`. Anything else that is not one of the eight codes
	raises, rather than being guessed at.
	"""
	if prevention_level in (None, ""):
		return None, None
	code = str(prevention_level).strip()
	s_status = "Inactive"
	if code.endswith("s"):
		code, s_status = code[:-1].strip(), "Active"
	if code not in ("Level 1", "Level 2", "Level 3", "Level 4"):
		raise ValueError(f"not a prevention level code: {prevention_level!r}")
	return code, s_status


def missing_when_connected(doc):
	"""The connected-only mandatory fields this document has left blank.

	Decision 1: a No Answer / Wrong Number / Caregiver Declined attempt is a real
	record and may leave all eight blank, so this returns `[]` for one.

	This exists because **`mandatory_depends_on` is client-side only.** Frappe's
	`_get_missing_mandatory_fields` iterates `reqd == 1` and never evaluates it,
	so the JSON attribute buys the red asterisk in the form and nothing at all
	for an API call, a data import or a `bench` script.
	"""
	if doc.get("call_disposition") != "Connected":
		return []
	# A Frappe Int/Float column cannot be null, so 0 here means "not entered" --
	# the same rule the intake form's waist_cm and height_cm already live under.
	return [fieldname for fieldname in CONNECTED_ONLY_MANDATORY if not doc.get(fieldname)]


def check_confidence_score(confidence_score):
	"""Confidence is a 1-10 scale; 0 is the Int column's "not entered"."""
	if confidence_score in (None, "", 0):
		return
	value = int(confidence_score)
	if not (CONFIDENCE_MIN <= value <= CONFIDENCE_MAX):
		raise ValueError(f"Confidence must be between {CONFIDENCE_MIN} and {CONFIDENCE_MAX}, not {value}")


def check_red_flag_disposition(safety_red_flag, call_disposition):
	"""A red flag can only come from a caregiver who was actually spoken to."""
	if safety_red_flag and call_disposition != "Connected":
		raise ValueError(
			"A safety red flag cannot be recorded on a call with outcome "
			f"{call_disposition or '(none)'}: nobody was spoken to."
		)


# --------------------------------------------------------------------------
# Controller
# --------------------------------------------------------------------------


class SparshFollowUp(Document):
	def before_validate(self):
		# Drafts are saved mid-call, exactly as the intake Ticket is saved
		# mid-consultation. Note this also suppresses `reqd`, which is why the
		# connected-only check below runs on submit and not here.
		if self.docstatus == 0:
			self.flags.ignore_mandatory = True

	def validate(self):
		self._guard_baseline_ticket()
		self._pull_baseline()
		self._pull_previous_call()
		self._derive()

		for check, args in (
			(check_red_flag_disposition, (self.safety_red_flag, self.call_disposition)),
			(check_confidence_score, (self.confidence_score,)),
		):
			try:
				check(*args)
			except ValueError as e:
				frappe.throw(_(str(e)))

		self._guard_duplicates()

		if self.docstatus == 1:
			missing = missing_when_connected(self)
			if missing:
				labels = [_(self.meta.get_label(fieldname)) for fieldname in missing]
				frappe.throw(
					_("A connected call needs: {0}").format(", ".join(labels)),
					title=_("Missing Call Details"),
				)

	# -- derivation ------------------------------------------------------

	def _derive(self):
		try:
			healthy, answered, display = habit_summary(
				self.sunset_rule_binary,
				self.builder_habit_binary,
				self.stress_check_binary,
				self.sleep_check_binary,
			)
		except ValueError as e:
			frappe.throw(_(str(e)))
		self.habit_score = healthy
		self.habit_answered = answered
		self.habit_score_display = display

		self.traffic_light_transition, self.traffic_light_change_category = traffic_movement(
			self.previous_traffic_light, self.current_traffic_light
		)

		if self.safety_red_flag and not self.clinical_review_status:
			self.clinical_review_status = "Pending"

	def _guard_baseline_ticket(self):
		if not self.baseline_ticket:
			return
		if frappe.db.get_value("Ticket", self.baseline_ticket, "docstatus") == 2:
			frappe.throw(_("Ticket {0} is cancelled and cannot be followed up.").format(self.baseline_ticket))

	def _pull_baseline(self):
		"""Prevention level and S status from the intake Ticket (decision 10)."""
		if not self.baseline_ticket:
			return
		prevention_level = frappe.db.get_value("Ticket", self.baseline_ticket, "prevention_level")
		try:
			self.baseline_prevention_level, self.baseline_s_status = split_prevention_level(prevention_level)
		except ValueError:
			# A code the intake form no longer offers. Say so rather than store a
			# level the Ticket does not claim.
			self.baseline_prevention_level, self.baseline_s_status = None, None
			frappe.msgprint(
				_(
					"Ticket {0} holds prevention level {1}, which is not one of the eight codes; "
					"baseline level and S status left blank."
				).format(self.baseline_ticket, prevention_level),
				indicator="orange",
			)

	def _pull_previous_call(self):
		"""Carry the previous *connected* call forward.

		The recovered Server Script ordered by `actual_call_date` over every
		record, so a No Answer attempt -- which has no pledge and no traffic
		light -- would be picked up as "the last call" and carry a blank pledge
		forward, hiding what the caregiver actually promised. Decision 1 makes
		those attempts common, so the filter is not optional.
		"""
		if not self.baseline_ticket:
			return

		previous = frappe.get_all(
			"Sparsh Follow Up",
			filters={
				"baseline_ticket": self.baseline_ticket,
				"call_disposition": "Connected",
				"docstatus": ["!=", 2],
				"name": ["!=", self.name],
			},
			fields=["current_traffic_light", "new_target_pledge_text", "confidence_score"],
			order_by="actual_call_date desc, creation desc",
			limit_page_length=1,
		)

		if previous:
			self.previous_traffic_light = previous[0].current_traffic_light
			self.previous_pledge_text = previous[0].new_target_pledge_text
			self.previous_confidence_score = previous[0].confidence_score
		else:
			# First connected call for this intake: the pledge to follow up on is
			# the one made on the intake form itself.
			self.previous_traffic_light = None
			self.previous_pledge_text = frappe.db.get_value("Ticket", self.baseline_ticket, "effort_to")
			self.previous_confidence_score = None

		# The baseline traffic light is the first connected call's own result --
		# the intake form records no traffic light.
		first = frappe.get_all(
			"Sparsh Follow Up",
			filters={
				"baseline_ticket": self.baseline_ticket,
				"call_disposition": "Connected",
				"docstatus": ["!=", 2],
				"name": ["!=", self.name],
			},
			fields=["current_traffic_light"],
			order_by="actual_call_date asc, creation asc",
			limit_page_length=1,
		)
		self.baseline_traffic_light = first[0].current_traffic_light if first else self.current_traffic_light

	# -- duplicates ------------------------------------------------------

	def _guard_duplicates(self):
		"""At most one CONNECTED call per (intake, week).

		Uniqueness cannot be per week alone: decision 1 makes repeated No Answer
		attempts in the same week legitimate, and they are the record of the
		effort made.
		"""
		if not self.baseline_ticket:
			return

		if self.call_disposition == "Connected":
			clash = frappe.db.exists(
				"Sparsh Follow Up",
				{
					"baseline_ticket": self.baseline_ticket,
					"follow_up_week": self.follow_up_week,
					"call_disposition": "Connected",
					"docstatus": ["!=", 2],
					"name": ["!=", self.name],
				},
			)
			if clash:
				frappe.throw(
					_("{0} already records a connected call for {1}, week {2}.").format(
						clash, self.baseline_ticket, self.follow_up_week
					)
				)

		if self.actual_call_date:
			same_day = frappe.db.exists(
				"Sparsh Follow Up",
				{
					"baseline_ticket": self.baseline_ticket,
					"actual_call_date": self.actual_call_date,
					"docstatus": ["!=", 2],
					"name": ["!=", self.name],
				},
			)
			if same_day:
				# A second attempt on the same day is ordinary; a duplicated
				# record of one attempt is not. Only the counsellor can tell
				# which this is, so say so and let them decide.
				frappe.msgprint(
					_("{0} also records a call to this caregiver on {1}.").format(
						same_day, frappe.utils.formatdate(self.actual_call_date, "dd-MMM-yyyy")
					),
					indicator="orange",
				)
