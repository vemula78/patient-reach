"""Merge the two duplicate `type_of_stress` spellings into the surviving pair.

Decision 6 of the clinical review of 18-Sep-2026. The intake form offered, at
different times, two spellings of each of the two stress types. Both sets are in
the live data, so a breakdown by type of stress silently reports four buckets
where the counselling team asks about two.

`ticket.json` already offers only the surviving spellings plus `None`, so the
obsolete variants are unselectable today and **no meta change is needed** -- this
patch moves data only.

Unlike v1_1/v1_2, which rewrote a whole vocabulary, this corrects a typo-level
duplication that nobody chose. That makes it invisible in the record afterwards,
so every row moved also gets a `Comment` saying what it used to say. A counsellor
looking at a Ticket whose stress type is not what they entered can then see why.

Idempotent: re-running finds nothing left to move, and the Comment insert is
guarded by an existence check besides.
"""

import frappe

PATCH_DATE = "18-Sep-2026"

# obsolete spelling -> the spelling ticket.json still offers.
# Both targets are byte-identical to the options in ticket.json, spacing and all
# -- including the space before the closing bracket in "(Medical related )" and
# the trailing comma in "etc.,)". They read as typos and are not; a "tidied"
# target would be a value the Select will not offer, which renders blank.
SPELLINGS = {
	"Clinical Stress (Medical-Related)": "Clinical Stress (Medical related )",
	"Non-Clinical Stress (Family, Financial, Social, etc.)": (
		"Non - Clinical Stress (Family, Financial, Social etc.,)"
	),
}

CURRENT = [
	"Clinical Stress (Medical related )",
	"Non - Clinical Stress (Family, Financial, Social etc.,)",
	"None",
]


def _log(msg):
	print(f"[patient_reach v1_3 type_of_stress] {msg}")


def execute():
	total = frappe.db.sql("select count(*) from tabTicket where ifnull(type_of_stress,%s)<>%s", ("", ""))[0][
		0
	]
	_log(f"tickets with a type of stress: {total}")

	moved = 0
	for old, new in SPELLINGS.items():
		names = frappe.get_all("Ticket", filters={"type_of_stress": old}, pluck="name")
		for name in names:
			frappe.db.set_value("Ticket", name, "type_of_stress", new, update_modified=False)
			_add_audit_comment(name, old, new)
		if names:
			_log(f"{len(names)} rows {old!r} -> {new!r}")
		moved += len(names)
	_log(f"migrated: {moved}")

	rows = frappe.db.sql(
		"select type_of_stress, count(*) from tabTicket "
		"where ifnull(type_of_stress,%s)<>%s group by type_of_stress",
		("", ""),
	)
	unknown = [(value, count) for value, count in rows if value not in CURRENT]
	if unknown:
		_log(f"WARNING not covered by the map, left as-is and now unselectable: {unknown}")
	else:
		_log("every populated value is now one the form offers")

	# Reconcile before committing. A spelling merge must move rows between
	# buckets and change no totals; if the after-total differs, something other
	# than this patch wrote to the column while it ran and the safe thing is to
	# roll back rather than leave a half-corrected column behind. Likewise a
	# surviving obsolete spelling means the map did not match what is stored --
	# byte-for-byte, including the odd spacing these values carry.
	after = sum(count for _value, count in rows)
	remaining = sum(count for value, count in rows if value in SPELLINGS)
	_log(f"reconcile: before={total} after={after} moved={moved} obsolete_left={remaining}")

	if after != total:
		frappe.db.rollback()
		frappe.throw(
			f"type_of_stress row count changed during the merge: {total} -> {after}. "
			"Nothing was written; re-run when no one else is editing Tickets."
		)
	if remaining:
		frappe.db.rollback()
		frappe.throw(
			f"{remaining} row(s) still hold an obsolete spelling after the merge. "
			"Nothing was written; check SPELLINGS against the stored values."
		)

	frappe.db.commit()


def _add_audit_comment(ticket, old, new):
	content = (
		f'type_of_stress spelling corrected: "{old}" -> "{new}" (patch patient_reach.v1_3, {PATCH_DATE})'
	)
	if frappe.db.exists(
		"Comment",
		{"reference_doctype": "Ticket", "reference_name": ticket, "content": content},
	):
		return
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Ticket",
			"reference_name": ticket,
			"content": content,
		}
	).insert(ignore_permissions=True)
