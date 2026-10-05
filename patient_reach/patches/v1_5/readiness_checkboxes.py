"""Copy the four "ready to be measured" Yes/No answers into the new checkboxes.

The team asked for checkboxes (05-Oct-2026), knowing a checkbox cannot say
"not asked": Yes becomes ticked; No and blank both become unticked. The Yes/No
fields stay, hidden and read-only, so "No" and "never answered" can still be
told apart for visits before the change.

The new columns are created with default 0, so only Yes needs writing.
Reconciles before committing: ticked count must equal the Yes count. Idempotent.
"""

import frappe

PAIRS = {
	"is_the_caregiver_ready_to_be_measured_for_blood_pressure": "ready_for_bp",
	"is_the_caregiver_ready_to_be_measured_for_weight": "ready_for_weight",
	"is_the_caregiver_ready_to_be_measured_for_height": "ready_for_height",
	"is_the_caregiver_ready_for_the_string_test": "ready_for_string_test",
}


def execute():
	for old, new in PAIRS.items():
		frappe.db.sql(f"update tabTicket set `{new}` = 1 where `{old}` = 'Yes' and `{new}` = 0")
		yes = frappe.db.sql(f"select count(*) from tabTicket where `{old}` = 'Yes'")[0][0]
		ticked = frappe.db.sql(f"select count(*) from tabTicket where `{new}` = 1")[0][0]
		print(f"[patient_reach v1_5 readiness] {new}: Yes={yes} ticked={ticked}")
		if yes != ticked:
			frappe.db.rollback()
			frappe.throw(f"{new}: {ticked} ticked but {yes} answered Yes. Nothing was written.")
	frappe.db.commit()
