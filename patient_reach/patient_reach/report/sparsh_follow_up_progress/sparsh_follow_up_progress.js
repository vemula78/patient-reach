// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

frappe.query_reports["Sparsh Follow-Up Progress"] = {
	filters: [
		{
			fieldname: "coach_id",
			label: __("Coach"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "call_disposition",
			label: __("Call Outcome"),
			fieldtype: "Select",
			options: ["", "Connected", "No Answer", "Wrong Number", "Caregiver Declined"],
		},
		{
			fieldname: "from_date",
			label: __("Scheduled From"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Scheduled To"),
			fieldtype: "Date",
		},
	],
};
