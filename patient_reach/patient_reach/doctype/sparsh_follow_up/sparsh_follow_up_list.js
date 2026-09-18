// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

frappe.listview_settings["Sparsh Follow Up"] = {
	add_fields: [
		"call_disposition",
		"safety_red_flag",
		"clinical_review_status",
		"current_traffic_light",
		"docstatus",
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
