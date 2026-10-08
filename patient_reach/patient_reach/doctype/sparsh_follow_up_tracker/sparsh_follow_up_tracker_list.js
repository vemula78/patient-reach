// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

// The caregiver list counsellors land on. A call past its date shows red
// whatever the status, so it stands out when scanning. The ID column (SFT-...)
// stays: counsellors copy it into the Health4All app (08-Oct-2026).
frappe.listview_settings["Sparsh Follow-up Tracker"] = {
	add_fields: ["follow_up_status", "next_call_date"],

	get_indicator: function (doc) {
		const today = frappe.datetime.get_today();
		if (doc.follow_up_status !== "Closed" && doc.next_call_date && doc.next_call_date < today) {
			return [__("Overdue"), "red", "next_call_date,<," + today + "|follow_up_status,!=,Closed"];
		}
		const colour = { "Follow-up 1": "blue", "Follow-up 2": "orange", "Follow-up 3": "purple", Closed: "green" }[
			doc.follow_up_status
		];
		return [__(doc.follow_up_status), colour || "gray", "follow_up_status,=," + doc.follow_up_status];
	},
};
