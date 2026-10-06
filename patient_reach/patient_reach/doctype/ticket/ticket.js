// Copyright (c) 2024, Patient Reach and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ticket", {
	refresh: function (frm) {
		toggle_sections(frm);

		// Only counsellors' logins; a Link cannot hold a typed name.
		frm.set_query("counsellor_name", function () {
			return { query: "patient_reach.api.counsellor_query" };
		});

		frm.set_query("forward_to", function () {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					role: "Doctor",
				},
			};
		});
	},
	ticket_type: function (frm) {
		toggle_sections(frm);
	},
	visit_type: function (frm) {
		toggle_sections(frm);
	},
	waist_cm: classify_measurements,
	height_cm: classify_measurements,
	bp_reading: classify_measurements,
	bp_repeat_reading: classify_measurements,
	bp_concerning_symptoms: classify_measurements,
	nodal_centre: function (frm) {
		if (frm.doc.nodal_centre === "SSSIHMS-WFD Preventive Medicine Centre - Sai Sparsh") {
			frm.set_value("department", "Cardiology - SSSIHMS");
			frm.set_value("ticket_type", "Preventive Cardiology");
		} else {
			frm.set_value("department", "");
			frm.set_value("ticket_type", "");
		}
	},
});

// Show the String Test result and BP Status as soon as the numbers are typed.
// The server does the classifying (patient_reach.api.classify_measurements), with
// the same functions the save hook uses, so the form cannot disagree with what
// is saved. A blank result means "nothing to derive" and leaves the field alone,
// as the save hook does.
function classify_measurements(frm) {
	frappe.call({
		method: "patient_reach.api.classify_measurements",
		args: {
			waist_cm: frm.doc.waist_cm,
			height_cm: frm.doc.height_cm,
			bp_reading: frm.doc.bp_reading,
			bp_rule: frm.doc.bp_rule,
			is_new: frm.is_new() ? 1 : 0,
			amended_from: frm.doc.amended_from,
			bp_repeat_reading: frm.doc.bp_repeat_reading,
			bp_concerning_symptoms: frm.doc.bp_concerning_symptoms ? 1 : 0,
		},
		callback: function (r) {
			const result = r.message || {};
			if (result.string_test_result && result.string_test_result !== frm.doc.string_test_result) {
				frm.set_value("string_test_result", result.string_test_result);
			}
			if (result.bp_status && result.bp_status !== frm.doc.bp_status) {
				frm.set_value("bp_status", result.bp_status);
			}
			// Dr Nayanjeet's prompt or action (2026-10-07 rule only; older rules have none).
			if ((result.bp_action || "") !== (frm.doc.bp_action || "")) {
				frm.set_value("bp_action", result.bp_action || "");
			}
		},
	});
}

function toggle_sections(frm) {
	let show_patient_enquiry =
		frm.doc.ticket_type === "Patient Enquiry" && frm.doc.visit_type === "First Visit";

	frm.set_df_property("patient_enquiry_section", "hidden", show_patient_enquiry ? 0 : 1);

	let show_preventive =
		frm.doc.ticket_type === "Preventive Cardiology" && frm.doc.visit_type === "First Visit";

	[
		"preventive_cardiology_section",
		"medical_condition_section",
		"addictions_section",
		"risk_level_section",
		"section_d",
		"height_section",
		"string_test_section",
		"bp_heading",
		"section_title",
	].forEach((section) => frm.set_df_property(section, "hidden", show_preventive ? 0 : 1));
	frm.set_df_property(
		"clinical_section",
		"hidden",
		frm.doc.ticket_type === "Preventive Cardiology" ? 1 : 0
	);
}
