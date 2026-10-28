"""SAI SPARSH rules of DRL v1.4: red flags, BP tiers, referral priority, heart
and brain events (A8), the permanent Level 4 and the referral follow-through.

Built from Dr Nayanjeet Chaudhury's answers of 13-Oct-2026 to the 13 questions
of "BP and Stroke Rules, Draft 0.1" (11-Oct-2026), with his clarifications of
27-Oct-2026 (a-h): invalid readings, same-day assessment after an emergency
referral, no fixed deadline after a low-BP review, role-based Level 4
correction, and a confirmed TIA under A8.

No `import frappe`: the rules are pinned by test_drl_v14.py, which runs with
plain Python. doc_events.py and the follow-up tracker hand plain values in and
write the results back.

Principles that run through every function, from his reply:

- Emergency first. Any red-flag symptom gives an emergency referral whatever
  the BP, blank BP included, and never waits for a repeat reading, a doctor or
  the clinical reviewer (Q5, Q6, A).
- Missing is not negative. A blank answer stays None and is shown as not
  recorded; it never becomes Normal, No, None needed or Non-adherent (D).
- A screening flag, not a diagnosis (B). The words returned say what to do,
  not what the caregiver has.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

RULE = "DRL v1.4"

# ---------------------------------------------------------------------------
# Red flags (Q5, Q6)
# ---------------------------------------------------------------------------

# His 13 items, in his order of 13-Oct, with the stroke signs grouped as
# BE-FAST as he allowed. The labels are the Visit form's check boxes; the
# field names are stable and never shown.
BE_FAST = (
	("rf_balance", "B: Sudden loss of balance or coordination"),
	("rf_vision", "E: Sudden visual disturbance"),
	("rf_face", "F: Sudden facial drooping"),
	("rf_limb", "A: Sudden limb weakness or numbness"),
	("rf_speech", "S: New speech difficulty"),
)
OTHER_EMERGENCIES = (
	("rf_chest_pain", "Acute chest pain or pressure"),
	("rf_breathless", "Severe breathlessness at rest"),
	("rf_unconscious", "Loss of consciousness"),
	("rf_seizure", "Seizure"),
	("rf_confusion", "Severe new confusion"),
	("rf_hypoglycaemia", "Severe hypoglycaemia with unsafe swallowing"),
	("rf_headache", "Sudden severe headache, particularly thunderclap headache"),
	("rf_other", "Any other sudden severe or potentially life-threatening symptom"),
)
RED_FLAGS = BE_FAST + OTHER_EMERGENCIES
RED_FLAG_NONE = "rf_none_asked"

RF_PRESENT = "Red-flag symptom present"
RF_NONE = "Asked: none present"

EMERGENCY_ACTION = (
	"EMERGENCY: call 112, or take the caregiver to the nearest Emergency Department, "
	"or use the hospital's emergency process, now. Stop routine counselling. Do not wait "
	"for a repeat BP, a doctor's review or the clinical reviewer."
)


def red_flag_status(values: dict) -> str | None:
	"""RF_PRESENT, RF_NONE, or None when the questions were not recorded as asked.

	All boxes unticked is not a No: only the "none of these" box says the
	questions were asked (D)."""
	if any(values.get(field) for field, _label in RED_FLAGS):
		return RF_PRESENT
	if values.get(RED_FLAG_NONE):
		return RF_NONE
	return None


def red_flag_errors(values: dict) -> list[str]:
	errors = []
	ticked = [label for field, label in RED_FLAGS if values.get(field)]
	if ticked and values.get(RED_FLAG_NONE):
		errors.append('Red flags: "None of these" cannot be ticked together with a symptom.')
	if values.get("rf_other") and not str(values.get("rf_other_detail") or "").strip():
		errors.append("Red flags: describe the other symptom.")
	return errors


def red_flags_ticked(values: dict) -> list[str]:
	return [label for field, label in RED_FLAGS if values.get(field)]


# ---------------------------------------------------------------------------
# BP (Q1-Q4, B2)
# ---------------------------------------------------------------------------

SEVERE = "Severe"
HIGH_PRIORITY = "High Priority"
HIGH = "High"
ELEVATED = "Elevated"
NORMAL = "Normal"
LOW = "Low"
NEEDS_REFERENCE = "Needs Reference"
INVALID = "Invalid Reading"

# Highest first. Low is not a tier: it is checked separately and shown beside
# whichever tier the reading reaches (Q2).
_TIER_RANK = {NORMAL: 0, ELEVATED: 1, HIGH: 2, HIGH_PRIORITY: 3, SEVERE: 4}

_BP = re.compile(r"(\d{2,3})\s*[/\\-]\s*(\d{2,3})")


def bp_pair(text) -> tuple[int, int] | None:
	"""(systolic, diastolic), or None when the text is not a plausible reading.
	The field is free text and holds prose ("BP machine not working")."""
	m = _BP.search(str(text or ""))
	if not m:
		return None
	systolic, diastolic = int(m.group(1)), int(m.group(2))
	if not (50 <= systolic <= 300 and 30 <= diastolic <= 200):
		return None
	return systolic, diastolic


def is_invalid(pair) -> bool:
	"""Diastolic at or above systolic (90/100) cannot be a true reading: it is
	never graded, and the BP is remeasured at once (27-Oct, a). A narrow but
	valid pulse pressure (110/100) is graded as usual: he set no threshold for
	flagging it, pending clinical validation."""
	return bool(pair) and pair[1] >= pair[0]


INVALID_ACTION = (
	"Invalid reading: the diastolic is at or above the systolic. Remeasure the BP now; "
	"no BP category is given from this reading."
)


def high_tier(pair: tuple[int, int]) -> str:
	"""The highest tier either value reaches (OR logic, as every rule since 07-Oct)."""
	systolic, diastolic = pair
	if systolic >= 180 or diastolic >= 120:
		return SEVERE
	if systolic >= 160 or diastolic >= 100:
		return HIGH_PRIORITY
	if systolic >= 140 or diastolic >= 90:
		return HIGH
	if systolic >= 120 or diastolic >= 80:
		return ELEVATED
	return NORMAL


def _low_parts(pair) -> tuple[bool, bool]:
	if not pair:
		return False, False
	return pair[0] < 90, pair[1] < 60


def _low_alert(low_systolic: bool, low_diastolic: bool) -> str | None:
	if low_systolic and low_diastolic:
		return "Low BP (systolic and diastolic)"
	if low_systolic:
		return "Low Systolic BP"
	if low_diastolic:
		return "Low Diastolic BP"
	return None


# Referral priority, most urgent first. A visit's priority is the most urgent
# of everything that applies; every applicable action is still listed (Q2).
P_EMERGENCY = "Emergency"
P_IMMEDIATE = "Immediate clinical assessment"
P_HIGH = "Physician within 24-48 hours"
P_REVIEW = "Clinical review (low BP)"
P_ROUTINE = "Physician within 4 weeks"
P_REPEAT = "Repeat BP needed"
P_NONE = "No referral needed"
PRIORITIES = (P_EMERGENCY, P_IMMEDIATE, P_HIGH, P_REVIEW, P_ROUTINE, P_REPEAT, P_NONE)

# The priorities that are a referral, and so have to be followed through (C).
REFERRAL_PRIORITIES = (P_EMERGENCY, P_IMMEDIATE, P_HIGH, P_REVIEW, P_ROUTINE)

TECHNIQUE = (
	"Rest quietly for 5 minutes before the first reading. Use the right cuff size, with the "
	"back and arm supported and no talking. Repeat after 1-2 minutes on the same arm, and "
	"record both readings. Never delay an emergency to repeat the BP."
)


def most_urgent(priorities) -> str | None:
	present = [p for p in priorities if p]
	return min(present, key=PRIORITIES.index) if present else None


def assess_bp(first, repeat=None, red_flags: str | None = None, low_symptoms: str | None = None) -> dict:
	result = _assess_bp(first, repeat, red_flags, low_symptoms)
	result.pop("_todo")
	return result


def _assess_bp(first, repeat, red_flags, low_symptoms) -> dict:
	"""Grade a visit's BP under DRL v1.4.

	`red_flags` is red_flag_status(): RF_PRESENT, RF_NONE or None (not asked).
	`low_symptoms` is the Visit's "Low BP symptoms" answer: "Yes", "No" or None.

	Returns status (the headline tier, or Low), alerts (every abnormal finding,
	so 170/55 shows High Priority BP and Low Diastolic BP), actions (most
	urgent first) and priority.

	- The tier is the higher of the two readings: a lower repeat never lifts an
	  alert (Q3) and a higher repeat sets the priority.
	- High (140-159 / 90-99) becomes a routine referral only if the repeat is
	  still 140/90 or above (Q1).
	- Low on either reading raises the Low alert; "persistently low" means both.
	"""
	result = {"status": None, "alerts": [], "actions": [], "priority": None}
	todo = []  # (priority, action)
	if red_flags == RF_PRESENT:
		todo.append((P_EMERGENCY, EMERGENCY_ACTION))

	first_text = str(first or "").strip()
	p1 = bp_pair(first_text)
	p2 = bp_pair(repeat)
	# An invalid reading is kept as entered, for audit, but graded as if absent:
	# a valid repeat after an invalid first reading is graded on its own.
	if is_invalid(p1) or is_invalid(p2):
		result["alerts"].append("Invalid reading")
		todo.append((P_REPEAT, INVALID_ACTION))
		if is_invalid(p2):
			p2 = None
		if is_invalid(p1):
			p1, p2 = p2, None
			if not p1:
				result["status"] = INVALID
	if not first_text:
		pass
	elif result["status"] == INVALID:
		pass
	elif not p1:
		result["status"] = NEEDS_REFERENCE
		todo.append((None, "The BP reading could not be read: enter it as systolic/diastolic, e.g. 128/84."))
	else:
		tier = max([high_tier(p1)] + ([high_tier(p2)] if p2 else []), key=_TIER_RANK.get)
		low_sys1, low_dia1 = _low_parts(p1)
		low_sys2, low_dia2 = _low_parts(p2)
		low = _low_alert(low_sys1 or low_sys2, low_dia1 or low_dia2)
		repeat_prompt = "Repeat the BP after 1-2 minutes on the same arm and record it."

		if tier == SEVERE:
			result["alerts"].append("Severe BP")
			text = (
				"Severe BP: arrange immediate clinical assessment today and forward the visit "
				"under Clinical Review. A lower repeat reading does not lift this alert."
			)
			if red_flags is None:
				text += " Ask the red-flag questions now: any one present means emergency referral."
			if not p2:
				text += " " + repeat_prompt + " Do not delay the assessment to do it."
			todo.append((P_IMMEDIATE, text))
		elif tier == HIGH_PRIORITY:
			result["alerts"].append("High Priority BP")
			text = (
				"High-priority BP: advise a physician consultation within 24-48 hours. "
				"The first follow-up call is due around day 3."
			)
			if not p2:
				text += " " + repeat_prompt
			todo.append((P_HIGH, text))
		elif tier == HIGH:
			result["alerts"].append("High BP")
			if not p2:
				todo.append((P_REPEAT, "High BP: " + repeat_prompt))
			elif _TIER_RANK[high_tier(p2)] >= _TIER_RANK[HIGH]:
				todo.append(
					(
						P_ROUTINE,
						"BP still high on repeat: advise a routine physician consultation, preferably within 4 weeks.",
					)
				)
			else:
				todo.append((P_NONE, "Repeat below 140/90: both readings recorded; continue counselling."))
		elif tier == ELEVATED:
			todo.append((P_NONE, "Elevated BP: record and continue preventive counselling."))
		else:
			todo.append((P_NONE, "No BP escalation."))

		if low:
			result["alerts"].append(low)
			ask = " Ask about dizziness, fainting, unusual weakness or confusion, and record the answer."
			if low_symptoms == "Yes":
				todo.append(
					(
						P_IMMEDIATE,
						"Low BP with symptoms: stop routine counselling and arrange prompt clinical assessment.",
					)
				)
			elif not p2:
				todo.append(
					(
						P_REPEAT,
						"Low BP: seat the caregiver safely and "
						+ repeat_prompt[0].lower()
						+ repeat_prompt[1:]
						+ (ask if low_symptoms is None else ""),
					)
				)
			elif (low_sys1 or low_dia1) and (low_sys2 or low_dia2):
				todo.append(
					(
						P_REVIEW,
						"Persistently low BP: advise clinical review."
						+ (ask if low_symptoms is None else ""),
					)
				)
			else:
				todo.append(
					(
						P_NONE,
						"Low BP on one reading only: both readings recorded."
						+ (ask if low_symptoms is None else ""),
					)
				)

		if tier in (SEVERE, HIGH_PRIORITY):
			result["status"] = tier
		elif low:
			result["status"] = LOW
		else:
			result["status"] = tier

	return _finish(result, todo)


def _finish(result: dict, todo: list) -> dict:
	"""Order the (priority, action) pairs most urgent first, drop repeats, and
	set the visit's priority to the most urgent."""
	todo = sorted(dict.fromkeys(todo), key=lambda t: PRIORITIES.index(t[0]) if t[0] else len(PRIORITIES))
	result["actions"] = list(dict.fromkeys(text for _p, text in todo))
	result["priority"] = most_urgent(p for p, _text in todo)
	result["_todo"] = todo
	return result


# ---------------------------------------------------------------------------
# Heart and brain events, and the permanent Level 4 (Q7, Q8, Q11, E)
# ---------------------------------------------------------------------------

EV_HEART_ATTACK = "Heart attack (myocardial infarction)"
EV_STROKE = "Stroke"
EV_TIA = "TIA (transient ischaemic attack)"
EV_ANGIOPLASTY = "Angioplasty or stent"
EV_BYPASS = "Bypass surgery (CABG)"
EV_OTHER = "Other major heart or brain event"
EV_UNCLEAR = "Paralysis or weakness, not yet clarified"
EVENT_TYPES = (EV_HEART_ATTACK, EV_STROKE, EV_TIA, EV_ANGIOPLASTY, EV_BYPASS, EV_OTHER, EV_UNCLEAR)

SRC_DOCUMENTED = "Documented (medical record or discharge summary)"
SRC_REPORTED = "Reported by caregiver or family"
TIA_DIAGNOSED = "Clinically diagnosed"
TIA_UNVERIFIED = "Transient symptoms, not verified"
NOW = "Happening now"
RECENT = "Recent, symptoms resolved"
PAST = "Past history"

QUALIFIES = "Qualifies for Level 4 (DRL A8)"
QUALIFIES_TIA = "Qualifies for Level 4 (clinically confirmed TIA, DRL A8)"
PENDING = "Pending clarification"


def event_level_4(row: dict) -> str | None:
	"""Whether one recorded event makes the caregiver Level 4.

	- A documented or caregiver-reported heart attack, stroke, angioplasty or
	  bypass qualifies (A8; written records are not mandatory).
	- A TIA qualifies only when clinically confirmed: his explicit addition to
	  A8 (27-Oct, d). A suspected TIA gives no provisional level: the existing
	  level stands until a doctor confirms it.
	- "Paralysis" alone, an "other" event, or any event without a source stays
	  pending: it prompts questions, not a diagnosis.
	"""
	kind = row.get("event_type")
	if not kind:
		return None
	if kind in (EV_UNCLEAR, EV_OTHER) or not row.get("source"):
		return PENDING
	if kind == EV_TIA:
		return QUALIFIES_TIA if row.get("tia_diagnosis") == TIA_DIAGNOSED else PENDING
	return QUALIFIES


def event_qualifies(row: dict) -> bool:
	return (event_level_4(row) or "").startswith("Qualifies")


def event_actions(row: dict) -> list[tuple[str, str]]:
	"""(priority, action) for one event."""
	kind = row.get("event_type")
	if not kind:
		return []
	todo = []
	if row.get("timing") == NOW:
		todo.append((P_EMERGENCY, EMERGENCY_ACTION))
	elif kind in (EV_TIA, EV_UNCLEAR) and row.get("timing") == RECENT:
		# Transient focal symptoms that have resolved are a suspected TIA: an
		# emergency whatever the Prevention Level (27-Oct, d).
		todo.append(
			(
				P_EMERGENCY,
				"Suspected recent TIA: emergency clinical assessment now, even though the symptoms "
				"have resolved. Do not change the Prevention Level until a doctor confirms it.",
			)
		)
	if kind == EV_UNCLEAR:
		todo.append(
			(
				None,
				"Paralysis or weakness reported: ask what happened, when, and whether a doctor diagnosed a stroke. Do not record a stroke until that is known.",
			)
		)
	elif event_level_4(row) == PENDING and not row.get("source"):
		todo.append(
			(None, f"{kind}: record whether it is documented or reported by the caregiver or family.")
		)
	return todo


def assess_visit(values: dict, events: list[dict]) -> dict:
	"""assess_bp for a visit, with the actions its events add (a recent TIA,
	symptoms happening now, a paralysis to clarify) and the red-flag status.
	The one function the save hook and the form's live grading both call."""
	flags = red_flag_status(values)
	result = _assess_bp(
		values.get("bp_reading"),
		values.get("bp_repeat_reading"),
		flags,
		values.get("low_bp_symptoms") or None,
	)
	result = _finish(result, result.pop("_todo") + [a for row in events for a in event_actions(row)])
	result.pop("_todo")
	result["red_flag_status"] = flags
	return result


LEVELS = ("Level 1", "Level 2", "Level 3", "Level 4")
S_YES = "Yes"


def prevention_code(level: str | None, s_modifier: str | None) -> str | None:
	"""The combined code the follow-up list and the reports read ("Level 2s").

	Level and S are recorded apart (Q7); this code is only derived from them.
	A blank S gives the code without "s", but the S field itself stays blank."""
	if level not in LEVELS:
		return None
	return level + ("s" if s_modifier == S_YES else "")


def level_4_sources(visits: list[dict], tracker_events: list[dict], corrected: set[str]) -> list[str]:
	"""Why the caregiver is permanently Level 4, one line per source, or [].

	`visits`: the caregiver's other visits that are not cancelled, each with
	`name`, `prevention_level` and `events` (its event rows).
	`tracker_events`: event rows recorded on their follow-up list, each with
	`parent`.
	`corrected`: names of the visits and trackers whose Level 4 the clinical
	reviewer has removed with a submitted correction (Q11).

	An earlier visit recorded at Level 4 counts as well as a recorded event:
	Level 4 is permanent (A8), and only the reviewer may remove one entered in
	error. Recovery does not remove it.
	"""
	reasons = []
	for v in visits:
		if v["name"] in corrected:
			continue
		for row in v.get("events") or []:
			if event_qualifies(row):
				reasons.append(f"{row['event_type']} recorded on {v['name']}")
		if str(v.get("prevention_level") or "").startswith("Level 4"):
			reasons.append(f"Level 4 recorded on {v['name']}")
	for row in tracker_events:
		if row["parent"] not in corrected and event_qualifies(row):
			reasons.append(f"{row['event_type']} recorded on {row['parent']}")
	return list(dict.fromkeys(reasons))


def level_4_note(reasons: list[str]) -> str | None:
	if not reasons:
		return None
	return (
		"Level 4 is permanent (DRL A8): "
		+ "; ".join(reasons)
		+ ". Only an authorised clinical supervisor (Sparsh Clinical Reviewer role) can correct it, "
		"with a reason, and only if it was entered in error."
	)


# ---------------------------------------------------------------------------
# The clinical reviewer's queue (Q9)
# ---------------------------------------------------------------------------

_STROKE_WORDS = re.compile(r"stroke|\bcva\b|paraly|hemipleg|brain attack|\btia\b", re.I)
_BRAIN_EVENTS = (EV_STROKE, EV_TIA, EV_UNCLEAR)


def review_reasons(values: dict, events: list[dict], conditions: list[dict]) -> list[str]:
	"""Why a DRL v1.4 visit goes to the clinical reviewer, or [].

	`values`: the visit's derived red_flag_status, bp_status, low_bp_symptoms,
	bp_alerts and any_other_medical_condition. `conditions`: Medical Condition
	rows (condition, has_disease)."""
	reasons = []
	if values.get("red_flag_status") == RF_PRESENT:
		reasons.append("Red-flag emergency")
	if values.get("bp_status") == SEVERE:
		reasons.append("Severe BP")
	elif values.get("bp_status") == HIGH_PRIORITY:
		reasons.append("High-priority BP")
	if (
		any(a.startswith("Low") for a in values.get("bp_alerts") or [])
		and values.get("low_bp_symptoms") == "Yes"
	):
		reasons.append("Symptomatic low BP")
	for row in events:
		if row.get("event_type"):
			reasons.append(f"{row['event_type']}: {event_level_4(row)}")
	kinds = {row.get("event_type") for row in events}
	heart_attack_ticked = any(
		c.get("condition") == "Heart Attack" and c.get("has_disease") for c in conditions
	)
	if heart_attack_ticked and EV_HEART_ATTACK not in kinds:
		reasons.append("Heart Attack ticked under Medical Condition, but no event recorded")
	if _STROKE_WORDS.search(str(values.get("any_other_medical_condition") or "")) and not kinds & set(
		_BRAIN_EVENTS
	):
		reasons.append("Stroke or paralysis mentioned, but no event recorded")
	return reasons


# ---------------------------------------------------------------------------
# Referral follow-through (Q10, C)
# ---------------------------------------------------------------------------

CONSULTED = "Consulted a physician"
NOT_YET = "Not yet consulted"
NOT_KNOWN = "Not known"

T_NOT_PRESCRIBED = "Not prescribed"
T_NOT_STARTED = "Prescribed, not started"
T_TAKING = "Taking as prescribed"
T_PARTIAL = "Partially taking"
T_STOPPED = "Stopped"
T_NOT_KNOWN = "Not known"
TREATMENT_STATES = (T_NOT_PRESCRIBED, T_NOT_STARTED, T_TAKING, T_PARTIAL, T_STOPPED, T_NOT_KNOWN)
_STARTED = (T_TAKING, T_PARTIAL, T_STOPPED)

D_COMPLETED = "Completed: consultation done"
D_DECLINED = "Caregiver declined the referral"
D_REVIEWER = "Closed by the clinical reviewer"
DISPOSITIONS = (D_COMPLETED, D_DECLINED, D_REVIEWER)

# Days after the referral date before a missing consultation is flagged
# (27-Oct, b). Emergency and Immediate are seen the same day, so the flag comes
# after 24 hours; that does not make a day's delay acceptable. P_HIGH's 2 days
# is his "24-48 hours". A low-BP clinical review has no deadline: the next
# review follows the treating clinician's advice.
CONSULT_DUE_DAYS = {P_EMERGENCY: 0, P_IMMEDIATE: 0, P_HIGH: 2, P_ROUTINE: 28}
# He asked for the day-3 call for high-priority referrals; the more urgent ones get it too.
DAY_3_PRIORITIES = (P_EMERGENCY, P_IMMEDIATE, P_HIGH)
DAY_3 = 3
TREATMENT_FLAG_DAYS = 14

FINISHED_STATUSES = ("Not Interested", "No Response", "Closed")


def _as_date(value) -> date | None:
	if not value:
		return None
	if isinstance(value, date):
		return value
	return date.fromisoformat(str(value)[:10])


def referral_call_date(priority: str | None, referral_date) -> date | None:
	"""Day 3 after the referral, for the priorities that get the early call."""
	start = _as_date(referral_date)
	if priority not in DAY_3_PRIORITIES or not start:
		return None
	return start + timedelta(days=DAY_3)


def disposition_errors(values: dict, is_reviewer: bool) -> list[str]:
	errors = []
	disposition = values.get("referral_disposition")
	if disposition == D_COMPLETED and values.get("consultation_status") != CONSULTED:
		errors.append('Referral: "Completed" needs the consultation recorded as done.')
	if disposition == D_REVIEWER and not is_reviewer:
		errors.append("Referral: only the clinical reviewer can close it this way.")
	return errors


def referral_flags(values: dict, today: date) -> list[str]:
	"""Flags for programme review on one follow-up row, worked out on the day
	they are read (a flag stored at save would go stale).

	`values`: the tracker's referral_priority, referral_date,
	consultation_status, treatment_status, referral_disposition,
	follow_up_status and call_1_actual_date.

	An unanswered call or a follow-up that stopped never closes a referral (C):
	only a disposition does, and a follow-up that ended with the referral still
	open is itself flagged.
	"""
	priority = values.get("referral_priority")
	if priority not in REFERRAL_PRIORITIES or values.get("referral_disposition"):
		return []
	flags = []
	start = _as_date(values.get("referral_date"))
	if not start:
		return ["Referral date not recorded"]
	days = (today - start).days
	due = CONSULT_DUE_DAYS.get(priority)
	if due is not None and values.get("consultation_status") != CONSULTED and days > due:
		flags.append(f"Consultation not recorded {days} days after referral")
	if priority in DAY_3_PRIORITIES and not values.get("call_1_actual_date") and days > DAY_3:
		flags.append("Day-3 call not made")
	if (
		priority in DAY_3_PRIORITIES
		and days > TREATMENT_FLAG_DAYS
		and values.get("treatment_status") not in (*_STARTED, T_NOT_PRESCRIBED)
	):
		flags.append(f"Treatment not recorded as started after {TREATMENT_FLAG_DAYS} days")
	if values.get("follow_up_status") in FINISHED_STATUSES:
		flags.append(f"Follow-up ended ({values['follow_up_status']}) with the referral still open")
	return flags
