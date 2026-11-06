// Copyright (c) 2026, Frugal Scientific and contributors
// For license information, please see license.txt

frappe.ui.form.on("Telemedicine Session", {
	setup(frm) {
		// Care users who hold the Doctor role; portal accounts are User records too and are not offered.
		frm.set_query("consulting_doctor", () => ({
			query: "patient_reach.patient_reach.doctype.telemedicine_session.telemedicine_session.doctor_users",
		}));
		frm.set_query("follow_up_by", () => ({ filters: { enabled: 1, user_type: "System User" } }));
	},
	patient_ws_number(frm) {
		const value = (frm.doc.patient_ws_number || "").replace(/\s+/g, "").toUpperCase();
		if (value !== frm.doc.patient_ws_number) frm.set_value("patient_ws_number", value);
		if (value && !/^WS(00|0000)[0-9]{6}$/.test(value)) {
			frappe.show_alert({
				message: __("The WS number must be WS, then 00 or 0000, then six digits."),
				indicator: "orange",
			});
		}
	},
});
