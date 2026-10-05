"""Copy each Ticket's single-choice Type of Stress into the new multi-select.

Type of Stress became a multi-select on 05-Oct-2026 (`stress_types`, rows of
`Ticket Stress Type` linking to `Stress Type`). The old `type_of_stress` Select
is kept, hidden and read-only, as the record of what was chosen before -- the
same reason the child tables keep their legacy `response`.

The three Stress Type names are byte-identical to the old options (the odd
spacing included; see v1_3), so a report reading either field counts a visit
the same way. A value that is not one of them is left uncopied and reported.

Reconciles before committing: every Ticket with a recognised value must end
with exactly that one row. Idempotent: a Ticket that already has rows is
skipped.
"""

import frappe

STRESS_TYPES = [
	"Clinical Stress (Medical related )",
	"Non - Clinical Stress (Family, Financial, Social etc.,)",
	"None",
]


def _log(msg):
	print(f"[patient_reach v1_5 stress_types] {msg}")


def execute():
	for stress_type in STRESS_TYPES:
		if not frappe.db.exists("Stress Type", stress_type):
			frappe.get_doc({"doctype": "Stress Type", "stress_type": stress_type}).insert(
				ignore_permissions=True
			)

	rows = frappe.db.sql("select name, type_of_stress from tabTicket where ifnull(type_of_stress, '') <> ''")
	has_rows = set(
		frappe.db.sql_list("select distinct parent from `tabTicket Stress Type` where parenttype = 'Ticket'")
	)
	copied, skipped, unknown = 0, 0, {}
	for ticket, value in rows:
		if value not in STRESS_TYPES:
			unknown[value] = unknown.get(value, 0) + 1
			continue
		if ticket in has_rows:
			skipped += 1
			continue
		frappe.get_doc(
			{
				"doctype": "Ticket Stress Type",
				"parent": ticket,
				"parenttype": "Ticket",
				"parentfield": "stress_types",
				"idx": 1,
				"stress_type": value,
			}
		).db_insert()
		copied += 1
	_log(f"tickets with a type of stress: {len(rows)}; copied: {copied}; already had rows: {skipped}")
	if unknown:
		_log(f"WARNING not a Stress Type, not copied: {unknown}")

	mismatched = frappe.db.sql(
		"""select count(*) from tabTicket t
		where t.type_of_stress in %(types)s
			and (select count(*) from `tabTicket Stress Type` s
				where s.parent = t.name and s.parenttype = 'Ticket' and s.stress_type = t.type_of_stress) <> 1""",
		{"types": tuple(STRESS_TYPES)},
	)[0][0]
	_log(f"reconcile: tickets whose old value is not exactly one matching row: {mismatched}")
	if mismatched:
		frappe.db.rollback()
		frappe.throw(
			f"{mismatched} Ticket(s) do not have exactly their old Type of Stress as one row. Nothing was written."
		)
	frappe.db.commit()
