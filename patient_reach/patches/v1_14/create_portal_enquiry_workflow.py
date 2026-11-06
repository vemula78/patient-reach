"""The workflow and the portal role for the Portal Enquiry doctype.

A Portal Enquiry is raised by a patient on the public portal, so it has its own
workflow, separate from the Visit ("Raise Ticket Workflow"). The states keep the
names portal/status.py already translates for the patient, so what the patient
reads and what staff see stay in step.

  Draft (patient sees "Received")
    -> Reviewed by Volunteer / Staff / Doctor
    -> Responded By Staff / Doctor   (needs at least one row in Responses)
    -> Ticket created                (staff make the Visit by hand)
    -> Rejected / Duplicate

Roles are care's existing Volunteer, Staff and Doctor, plus Patient Portal User
(no desk access) for the patient. Nothing is overwritten: a Workflow State,
Action or role that already exists is left as it is, and a workflow already
named "Portal Enquiry Workflow" is left alone so a later edit in the desk
survives. Re-run with:
bench --site <site> execute patient_reach.patches.v1_14.create_portal_enquiry_workflow.execute
"""

import frappe

WORKFLOW = "Portal Enquiry Workflow"
DOCTYPE = "Portal Enquiry"

STATES = [
	# (state, style, who may edit it)
	("Draft", "Warning", "Volunteer"),
	("Reviewed by Volunteer", "Primary", "Volunteer"),
	("Reviewed by Staff", "Primary", "Staff"),
	("Reviewed by Doctor", "Info", "Doctor"),
	("Responded By Staff", "Success", "Staff"),
	("Responded By Doctor", "Success", "Doctor"),
	("Ticket created", "Info", "Staff"),
	("Rejected", "Danger", "Staff"),
	("Duplicate", "Inverse", "Staff"),
]

HAS_RESPONSE = "doc.responses and len(doc.responses) > 0"

# (from, action, to, role, condition)
TRANSITIONS = [
	("Draft", "Review", "Reviewed by Volunteer", "Volunteer", None),
	("Draft", "Review", "Reviewed by Staff", "Staff", None),
	("Draft", "Review", "Reviewed by Doctor", "Doctor", None),
	("Reviewed by Volunteer", "Pass to Staff", "Reviewed by Staff", "Volunteer", None),
	("Reviewed by Volunteer", "Pass to Staff", "Reviewed by Staff", "Staff", None),
	("Reviewed by Volunteer", "Refer to Doctor", "Reviewed by Doctor", "Volunteer", None),
	("Reviewed by Volunteer", "Refer to Doctor", "Reviewed by Doctor", "Staff", None),
	("Reviewed by Staff", "Refer to Doctor", "Reviewed by Doctor", "Staff", None),
	("Reviewed by Staff", "Respond", "Responded By Staff", "Staff", HAS_RESPONSE),
	("Reviewed by Doctor", "Respond", "Responded By Doctor", "Doctor", HAS_RESPONSE),
	("Reviewed by Staff", "Create Ticket", "Ticket created", "Staff", None),
	("Reviewed by Doctor", "Create Ticket", "Ticket created", "Doctor", None),
	("Responded By Staff", "Reopen", "Reviewed by Staff", "Staff", None),
	("Responded By Doctor", "Reopen", "Reviewed by Doctor", "Doctor", None),
]
# Anyone who can review may also turn an enquiry away as a duplicate or reject it.
for _state in ("Draft", "Reviewed by Volunteer", "Reviewed by Staff", "Reviewed by Doctor"):
	for _action, _to in (("Reject", "Rejected"), ("Mark Duplicate", "Duplicate")):
		for _role in ("Staff", "Doctor"):
			TRANSITIONS.append((_state, _action, _to, _role, None))
		if _state in ("Draft", "Reviewed by Volunteer"):
			TRANSITIONS.append((_state, _action, _to, "Volunteer", None))


def _ensure_role():
	# Syncing the doctype may already have created the role, with desk access on.
	if not frappe.db.exists("Role", "Patient Portal User"):
		frappe.get_doc({"doctype": "Role", "role_name": "Patient Portal User"}).insert(ignore_permissions=True)
	frappe.db.set_value("Role", "Patient Portal User", "desk_access", 0)


def execute():
	_ensure_role()

	for state, style, _ in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)
	for action in {t[1] for t in TRANSITIONS}:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	if frappe.db.exists("Workflow", WORKFLOW):
		return

	wf = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW,
			"document_type": DOCTYPE,
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"states": [
				{"state": s, "doc_status": "0", "allow_edit": role} for s, _style, role in STATES
			],
			"transitions": [
				{
					"state": f,
					"action": a,
					"next_state": t,
					"allowed": role,
					"allow_self_approval": 1,
					"condition": cond,
				}
				for f, a, t, role, cond in TRANSITIONS
			],
		}
	)
	wf.insert(ignore_permissions=True)
	frappe.db.commit()
