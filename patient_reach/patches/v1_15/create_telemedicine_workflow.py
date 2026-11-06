"""The workflow for the Telemedicine Session doctype.

Volunteers operate the form, so Volunteer, Staff and Doctor can all move a
session along; only Staff can reopen a completed one. Nothing is overwritten: an
existing Workflow State, Action or workflow of the same name is left alone, so a
later edit in the desk survives. Re-run with:
bench --site <site> execute patient_reach.patches.v1_15.create_telemedicine_workflow.execute

  Scheduled -> In Progress -> Completed   (needs the advice recorded)
  Scheduled or In Progress -> Cancelled, No Show
"""

import frappe

WORKFLOW = "Telemedicine Session Workflow"
DOCTYPE = "Telemedicine Session"
OPERATORS = ("Volunteer", "Staff", "Doctor")

STATES = [
	# (state, style, who may edit it)
	("Scheduled", "Warning", "Volunteer"),
	("In Progress", "Primary", "Volunteer"),
	("Completed", "Success", "Staff"),
	("Cancelled", "Danger", "Staff"),
	("No Show", "Inverse", "Staff"),
]

# (from, action, to, roles)
MOVES = [
	("Scheduled", "Start Session", "In Progress", OPERATORS),
	("Scheduled", "Cancel Session", "Cancelled", OPERATORS),
	("Scheduled", "Mark No Show", "No Show", OPERATORS),
	("In Progress", "Complete Session", "Completed", OPERATORS),
	("In Progress", "Cancel Session", "Cancelled", OPERATORS),
	("In Progress", "Mark No Show", "No Show", OPERATORS),
	("Completed", "Reopen Session", "In Progress", ("Staff",)),
]
TRANSITIONS = [(f, a, t, role) for f, a, t, roles in MOVES for role in roles]


def execute():
	for state, style, _ in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)
	for action in {m[1] for m in MOVES}:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)
	if frappe.db.exists("Workflow", WORKFLOW):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW,
			"document_type": DOCTYPE,
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"states": [{"state": s, "doc_status": "0", "allow_edit": role} for s, _style, role in STATES],
			"transitions": [
				{"state": f, "action": a, "next_state": t, "allowed": role, "allow_self_approval": 1}
				for f, a, t, role in TRANSITIONS
			],
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
