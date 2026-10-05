"""Add NEPAL and BANGLADESH to Patient State.

State is mandatory on the Patient and the list held only Indian states, so a
caregiver from Nepal (6 on care) or Bangladesh (1) had to be given an Indian
state or "NOT STATED" (05-Oct-2026). Upper case like the existing entries.
Existing Patients are not changed: which state each of them should show is for
the counselling team to correct on the record.
"""

import frappe


def execute():
	for state in ("NEPAL", "BANGLADESH"):
		if not frappe.db.exists("Patient State", state):
			frappe.get_doc({"doctype": "Patient State", "state": state}).insert(ignore_permissions=True)
			print(f"[patient_reach v1_5 states] added {state}")
