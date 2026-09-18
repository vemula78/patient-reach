// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

frappe.query_reports["Sparsh Overdue Calls"] = {
	filters: [
		{
			fieldname: "coach_id",
			label: __("Coach"),
			fieldtype: "Link",
			options: "User",
		},
	],
};
