// Copyright (c) 2024, Patient Reach and contributors
// For license information, please see license.txt

// DRL v1.4 (patient_reach/drl_v14.py). The rule set a visit is graded by is
// stamped by the server; this only decides what the form shows.
const DRL_RULE = "DRL v1.4";
const RED_FLAG_FIELDS = [
	"rf_balance",
	"rf_vision",
	"rf_face",
	"rf_limb",
	"rf_speech",
	"rf_chest_pain",
	"rf_breathless",
	"rf_unconscious",
	"rf_seizure",
	"rf_confusion",
	"rf_hypoglycaemia",
	"rf_headache",
	"rf_other",
	"rf_none_asked",
];

frappe.ui.form.on("Ticket", {
	refresh: function (frm) {
		toggle_sections(frm);
		show_drl_v14(frm);

		// Follow-up calls are recorded on the Sai Sparsh follow-up list, not as a
		// second visit (change request, 23-Oct-2026). The option stays in the
		// DocType so the visits already saved as Follow-up remain valid.
		if (frm.doc.visit_type !== "Follow-up") {
			frm.set_df_property("visit_type", "options", ["", "First Visit"]);
		}

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
	low_bp_symptoms: classify_measurements,
	...Object.fromEntries(RED_FLAG_FIELDS.map((f) => [f, classify_measurements])),
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
			drl_values: JSON.stringify(drl_values(frm)),
		},
		callback: function (r) {
			const result = r.message || {};
			if (result.string_test_result && result.string_test_result !== frm.doc.string_test_result) {
				frm.set_value("string_test_result", result.string_test_result);
			}
			if (result.bp_status && result.bp_status !== frm.doc.bp_status) {
				frm.set_value("bp_status", result.bp_status);
			}
			// Dr Nayanjeet's prompt or action (2026-10-07 rule and DRL v1.4; older rules have none).
			if ((result.bp_action || "") !== (frm.doc.bp_action || "")) {
				frm.set_value("bp_action", result.bp_action || "");
			}
			if (frm.doc.bp_rule === DRL_RULE) {
				// A blank result clears the field here: under DRL v1.4 nothing
				// recorded means nothing derived, never Normal.
				["bp_status", "bp_alerts", "referral_priority", "red_flag_status"].forEach(
					(field) => {
						if ((result[field] || "") !== (frm.doc[field] || "")) {
							frm.set_value(field, result[field] || "");
						}
					}
				);
				show_drl_v14(frm);
			}
		},
	});
}

function drl_values(frm) {
	if (frm.doc.bp_rule !== DRL_RULE) return null;
	const values = { low_bp_symptoms: frm.doc.low_bp_symptoms || null };
	RED_FLAG_FIELDS.forEach((f) => (values[f] = frm.doc[f] ? 1 : 0));
	values.rf_other_detail = frm.doc.rf_other_detail || "";
	values.health_events = (frm.doc.health_events || []).map((row) => ({
		event_type: row.event_type,
		source: row.source,
		tia_diagnosis: row.tia_diagnosis,
		timing: row.timing,
	}));
	return values;
}

// The emergency instruction at the top of every tab, and a way back to the
// red-flag questions from anywhere in the visit (Dr Nayanjeet, Q6).
function show_drl_v14(frm) {
	if (frm.doc.bp_rule !== DRL_RULE) return;
	frm.remove_custom_button(__("Red flags"));
	frm.add_custom_button(__("Red flags"), () => frm.scroll_to_field("rf_balance"));
	if (frm.doc.red_flag_status === "Red-flag symptom present") {
		frm.dashboard.set_headline_alert(
			`<div style="color: var(--red-600); font-weight: var(--weight-semibold);">${__(
				"EMERGENCY: call 112, or take the caregiver to the nearest Emergency Department, or use the hospital's emergency process, now. Stop routine counselling. Do not wait for a repeat BP, a doctor's review or the clinical reviewer."
			)}</div>`
		);
	} else {
		frm.dashboard.clear_headline();
	}
	frm.set_df_property("level", "read_only", frm.doc.level_4_lock ? 1 : 0);
}

frappe.ui.form.on("Sparsh Health Event", {
	event_type: classify_measurements,
	source: classify_measurements,
	tia_diagnosis: classify_measurements,
	timing: classify_measurements,
	health_events_remove: classify_measurements,
});

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
