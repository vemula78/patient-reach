// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

frappe.listview_settings["Sparsh Follow Up"] = {
	add_fields: [
		"call_disposition",
		"safety_red_flag",
		"clinical_review_status",
		"current_traffic_light",
		"docstatus",
		"scheduled_date",
		"actual_call_date",
	],

	get_indicator: function (doc) {
		// Safety takes priority over everything else: an unread red flag must
		// stand out on the list even if the record is otherwise submitted.
		if (doc.safety_red_flag && doc.clinical_review_status === "Pending") {
			return [__("Red flag - Pending review"), "red", "safety_red_flag,=,1|clinical_review_status,=,Pending"];
		}
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
		// A call not yet made: say whether it is late, so a counsellor filtering
		// the list by Counsellor sees what is pending for them at a glance.
		if (doc.docstatus === 0 && !doc.actual_call_date && doc.scheduled_date) {
			const today = frappe.datetime.get_today();
			const pending = "docstatus,=,0|actual_call_date,is,not set";
			if (doc.scheduled_date < today) return [__("Overdue"), "red", pending + "|scheduled_date,<," + today];
			if (doc.scheduled_date === today) return [__("Due today"), "orange", pending + "|scheduled_date,=," + today];
			return [__("Scheduled"), "blue", pending + "|scheduled_date,>," + today];
		}
		if (doc.docstatus === 0) {
			return [__("Draft"), "yellow", "docstatus,=,0"];
		}
		// Submitted: colour by the traffic light the counsellor just set,
		// since that is what a coach scanning the list actually wants to know.
		const traffic_colour = { Red: "red", Yellow: "yellow", Green: "green" }[doc.current_traffic_light];
		if (traffic_colour) {
			return [doc.current_traffic_light, traffic_colour, "current_traffic_light,=," + doc.current_traffic_light];
		}
		return [__("Submitted"), "blue", "docstatus,=,1"];
	},
};
