// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

frappe.query_reports["Sparsh Intake Overview"] = {
	filters: [
		{
			fieldname: "nodal_centre",
			label: __("Nodal Centre"),
			fieldtype: "Link",
			options: "Branch",
		},
	],
};
