"""The Telemedicine dashboard: a Dashboard, a Workspace page and the cards and
charts on them, all counting Telemedicine Session only. Separate from the
Healthcare page and the Sai Sparsh counts, which it does not touch.

Only counts are shown, never a name or a WS number. Idempotent; an existing card,
chart, dashboard or workspace of the same name is left as it is. Re-run with:
bench --site <site> execute patient_reach.patches.v1_15.create_telemedicine_dashboard.execute
"""

import json

import frappe

DT = "Telemedicine Session"
NAME = "Telemedicine"
ROLES = ("Volunteer", "Staff", "Doctor", "System Manager")


def _f(field, op, value):
	return [DT, field, op, value, False]


# label: (filters, colour)
NUMBER_CARDS = {
	"Telemedicine Sessions Today": ([_f("session_datetime", "Timespan", "today")], "#449CF0"),
	"Telemedicine Sessions Scheduled": ([_f("workflow_state", "=", "Scheduled")], "#ECAD4B"),
	"Telemedicine Sessions Completed This Month": (
		[_f("workflow_state", "=", "Completed"), _f("session_datetime", "Timespan", "this month")],
		"#48BB74",
	),
	"Telemedicine No-shows This Month": (
		[_f("workflow_state", "=", "No Show"), _f("session_datetime", "Timespan", "this month")],
		"#E24C4C",
	),
	"Telemedicine Sessions Total": ([], "#7A89C2"),
}

# chart name: extra fields
CHARTS = {
	"Telemedicine Sessions per Month": {
		"chart_type": "Count",
		"based_on": "session_datetime",
		"timeseries": 1,
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"type": "Bar",
		"color": "#449CF0",
	},
	"Telemedicine Sessions by Status": {
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "workflow_state",
		"type": "Donut",
	},
	"Telemedicine Sessions by Department": {
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "department",
		"number_of_groups": 10,
		"type": "Bar",
		"color": "#7A89C2",
	},
	"Telemedicine Sessions by Consulting Doctor": {
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "consulting_doctor",
		"number_of_groups": 10,
		"type": "Bar",
		"color": "#48BB74",
	},
	"Telemedicine Sessions by Nodal Centre": {
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "nodal_centre",
		"number_of_groups": 10,
		"type": "Bar",
		"color": "#ECAD4B",
	},
}


def _block(kind, **data):
	return {"id": frappe.generate_hash(length=10), "type": kind, "data": data}


def execute():
	for label, (filters, colour) in NUMBER_CARDS.items():
		if not frappe.db.exists("Number Card", label):
			frappe.get_doc(
				{
					"doctype": "Number Card",
					"label": label,
					"type": "Document Type",
					"document_type": DT,
					"function": "Count",
					"filters_json": json.dumps(filters),
					"is_public": 1,
					"show_percentage_stats": 0,
					"color": colour,
				}
			).insert(ignore_permissions=True)

	for chart_name, extra in CHARTS.items():
		if not frappe.db.exists("Dashboard Chart", chart_name):
			frappe.get_doc(
				{
					"doctype": "Dashboard Chart",
					"chart_name": chart_name,
					"document_type": DT,
					"filters_json": "[]",
					"dynamic_filters_json": "[]",
					"is_public": 1,
					**extra,
				}
			).insert(ignore_permissions=True)

	if not frappe.db.exists("Dashboard", NAME):
		frappe.get_doc(
			{
				"doctype": "Dashboard",
				"dashboard_name": NAME,
				"cards": [{"card": c} for c in NUMBER_CARDS],
				"charts": [
					{"chart": c, "width": "Full" if i == 0 else "Half"} for i, c in enumerate(CHARTS)
				],
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Workspace", NAME):
		blocks = [_block("header", text='<span class="h4"><b>Telemedicine Sessions</b></span>', col=12)]
		blocks += [_block("number_card", number_card_name=c, col=3) for c in NUMBER_CARDS]
		blocks.append(_block("spacer", col=12))
		blocks += [_block("chart", chart_name=c, col=6) for c in CHARTS]
		blocks.append(_block("spacer", col=12))
		blocks += [_block("shortcut", shortcut_name=s, col=3) for s in ("All Sessions", "Scheduled Sessions")]
		frappe.get_doc(
			{
				"doctype": "Workspace",
				"label": NAME,
				"title": NAME,
				"module": "Patient Reach",
				"public": 1,
				"type": "Workspace",
				"content": json.dumps(blocks),
				"number_cards": [{"number_card_name": c, "label": c} for c in NUMBER_CARDS],
				"charts": [{"chart_name": c, "label": c} for c in CHARTS],
				"shortcuts": [
					{"label": "All Sessions", "type": "DocType", "link_to": DT, "doc_view": "List"},
					{
						"label": "Scheduled Sessions",
						"type": "DocType",
						"link_to": DT,
						"doc_view": "List",
						"stats_filter": json.dumps({"workflow_state": ["=", "Scheduled"]}),
					},
				],
				"roles": [{"role": r} for r in ROLES],
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache()
