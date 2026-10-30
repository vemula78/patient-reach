"""The Healthcare page (where most counsellors land) and the Visit list, as the
counselling team's change request of 29-Oct-2026 asks. Both are records on
care, not shipped by any app, so they are edited here:

Healthcare workspace
- Number cards: Total Caregivers (the old Total Patients count: active
  caregivers), Total Visits (every visit not cancelled) and Total Follow-ups
  (every follow-up row, the count the "Caregiver Follow-ups" shortcut showed),
  in place of Total Patients and Total Patients Admitted. They are new,
  non-standard Number Cards: the health app's own are left untouched, so an
  upgrade of it cannot rename them back.
- Shortcuts, each counting the logged-in counsellor's own records:
  My Caregiver (was Patient/Caregiver), My Caregiver Visits (was Visit) and
  My Caregiver Follow-ups (was My Follow-ups; now leaves out Not Interested,
  No Response and Closed, reversing v1_11 at the team's request). Then
  "Counsellor/Coach wise Statistics", which only holders of Sparsh Statistics
  Viewer see. Caregiver Follow-ups, Request for Consultation and Dashboard
  are taken off the page; their shortcut rows are kept.
- The Masters card's "Patient / Caregiver" links say "Caregiver".

Visit list (List View Settings "Ticket", which fixes its columns): no Visit
Type, Follow-up Date or Follow-up By; the Department column shows the
original patient's department; "Patient/Caregiver" labels say "Caregiver".

`modified` is left alone on the workspace, as in v1_7 and v1_9. Idempotent,
and safe to re-run after a migrate that restores the health app's page:
bench --site <site> execute patient_reach.patches.v1_13.healthcare_landing_page.execute
"""

import json

import frappe

WS = "Healthcare"
TRACKER = "Sparsh Follow-up Tracker"
FINISHED = ["Not Interested", "No Response", "Closed"]
ME = "frappe.session.user"

# label: (document_type, filters_json, colour)
NUMBER_CARDS = {
	"Total Caregivers": ("Patient", [["Patient", "status", "=", "Active", False]], "#7A89C2"),
	"Total Visits": ("Ticket", [["Ticket", "docstatus", "!=", 2, False]], "#449CF0"),
	"Total Follow-ups": (TRACKER, [], "#48BB74"),
}
# The page's old cards, and the new one that takes each place.
CARD_SWAP = {"Total Patients": "Total Caregivers", "Total Patients Admitted": "Total Visits"}

# (old label, link_to) -> (new label, stats_filter)
SHORTCUTS = {
	("Patient", "Patient"): ("My Caregiver", f'{{"custom_counsellor_name": ["=", {ME}]}}'),
	("Ticket", "Ticket"): (
		"My Caregiver Visits",
		f'{{"counsellor_name": ["=", {ME}], "docstatus": ["!=", 2]}}',
	),
	("My Follow-ups", TRACKER): (
		"My Caregiver Follow-ups",
		f'{{"counsellor": ["=", {ME}], "follow_up_status": ["not in", {json.dumps(FINISHED)}]}}',
	),
}
STATISTICS = "Counsellor/Coach wise Statistics"
STATISTICS_REPORT = "Sparsh Counsellor Statistics"
OFF_THE_PAGE = ("Caregiver Follow-ups", "Request for Consultation", "Dashboard")

VISIT_COLUMNS_DROPPED = ("visit_type", "follow_up_date", "follow_up_by")
VISIT_LABELS = {
	"patient_id": "Caregiver ID",
	"patient_name": "Caregiver Name",
	"patient_mobile_no": "Caregiver Mobile No",
}


def execute():
	if frappe.db.exists("Workspace", WS):
		_number_cards()
		_shortcuts()
		_masters_labels()
	_visit_list()
	frappe.clear_cache()


def _child(parentfield, idx, **values):
	return frappe.get_doc(
		{
			"doctype": values.pop("doctype"),
			"parent": WS,
			"parenttype": "Workspace",
			"parentfield": parentfield,
			"idx": idx,
			**values,
		}
	)


def _blocks():
	return json.loads(frappe.db.get_value("Workspace", WS, "content") or "[]")


def _save_blocks(blocks):
	frappe.db.set_value("Workspace", WS, "content", json.dumps(blocks), update_modified=False)


def _number_cards():
	for label, (doctype, filters, colour) in NUMBER_CARDS.items():
		if not frappe.db.exists("Number Card", label):
			frappe.get_doc(
				{
					"doctype": "Number Card",
					"label": label,
					"type": "Document Type",
					"document_type": doctype,
					"function": "Count",
					"filters_json": json.dumps(filters),
					"is_public": 1,
					"show_percentage_stats": 1,
					"stats_time_interval": "Daily",
					"color": colour,
				}
			).insert(ignore_permissions=True)
	ws = frappe.get_doc("Workspace", WS)
	have = {c.label for c in ws.number_cards}
	n = len(ws.number_cards)
	for label in NUMBER_CARDS:
		if label not in have:
			n += 1
			_child(
				"number_cards", n, doctype="Workspace Number Card", number_card_name=label, label=label
			).db_insert()

	blocks = _blocks()
	cards = [b for b in blocks if b.get("type") == "number_card"]
	if any(b["data"].get("number_card_name") == "Total Follow-ups" for b in cards):
		return
	for b in cards:
		new = CARD_SWAP.get(b["data"].get("number_card_name"))
		if new:
			b["data"]["number_card_name"] = new
	at = next(
		(
			i
			for i, b in enumerate(blocks)
			if b.get("type") == "number_card" and b["data"]["number_card_name"] == "Total Visits"
		),
		None,
	)
	if at is None:
		return
	blocks.insert(
		at + 1,
		{
			"id": frappe.generate_hash(length=10),
			"type": "number_card",
			"data": {"number_card_name": "Total Follow-ups", "col": 3},
		},
	)
	_save_blocks(blocks)


def _shortcuts():
	ws = frappe.get_doc("Workspace", WS)
	renamed = {}
	for s in ws.shortcuts:
		old = s.label
		if s.type == "DocType" and (old, s.link_to) in SHORTCUTS:
			label, stats_filter = SHORTCUTS[(old, s.link_to)]
			frappe.db.set_value(
				"Workspace Shortcut",
				s.name,
				{"label": label, "stats_filter": stats_filter},
				update_modified=False,
			)
			renamed[old] = label
	if not any(s.label == STATISTICS for s in ws.shortcuts):
		_child(
			"shortcuts",
			len(ws.shortcuts) + 1,
			doctype="Workspace Shortcut",
			type="Report",
			link_to=STATISTICS_REPORT,
			report_ref_doctype="Ticket",
			label=STATISTICS,
			color="Grey",
		).db_insert()

	blocks = _blocks()
	for b in blocks:
		if b.get("type") == "shortcut" and b["data"].get("shortcut_name") in renamed:
			b["data"]["shortcut_name"] = renamed[b["data"]["shortcut_name"]]
			b["data"]["col"] = 3
	blocks = [
		b
		for b in blocks
		if not (b.get("type") == "shortcut" and b["data"].get("shortcut_name") in OFF_THE_PAGE)
	]
	if not any(b.get("type") == "shortcut" and b["data"].get("shortcut_name") == STATISTICS for b in blocks):
		last = max(
			(
				i
				for i, b in enumerate(blocks)
				if b.get("type") == "shortcut"
				and b["data"].get("shortcut_name") in {v[0] for v in SHORTCUTS.values()}
			),
			default=len(blocks) - 1,
		)
		blocks.insert(
			last + 1,
			{
				"id": frappe.generate_hash(length=10),
				"type": "shortcut",
				"data": {"shortcut_name": STATISTICS, "col": 3},
			},
		)
	_save_blocks(blocks)
	print(f"[patient_reach v1_13] Healthcare shortcuts renamed: {renamed}")


def _masters_labels():
	for row in frappe.get_all(
		"Workspace Link",
		filters={"parent": WS, "label": ["like", "%Patient%Caregiver%"]},
		fields=["name", "label"],
	):
		label = row.label.replace("Patient / Caregiver", "Caregiver").replace(
			"Patient/Caregiver", "Caregiver"
		)
		frappe.db.set_value("Workspace Link", row.name, "label", label, update_modified=False)


def _visit_list():
	if not frappe.db.exists("List View Settings", "Ticket"):
		return
	fields = json.loads(frappe.db.get_value("List View Settings", "Ticket", "fields") or "[]")
	kept = []
	for f in fields:
		if f.get("fieldname") in VISIT_COLUMNS_DROPPED:
			continue
		if f.get("fieldname") == "department":
			f = {"fieldname": "department_of_original_patient", "label": "Department"}
		if f.get("fieldname") in VISIT_LABELS:
			f = {**f, "label": VISIT_LABELS[f["fieldname"]]}
		kept.append(f)
	frappe.db.set_value("List View Settings", "Ticket", "fields", json.dumps(kept), update_modified=False)
	print(f"[patient_reach v1_13] Visit list columns: {[f['fieldname'] for f in kept]}")
