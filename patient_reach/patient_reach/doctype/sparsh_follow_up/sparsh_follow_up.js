// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

// Client-side behaviour for the Sai Sparsh caregiver follow-up call.
//
// This file owns UI convenience only. The rules that actually protect data --
// conditional mandatory on submit, the one-Connected-record-per-week guard,
// the Ticket-cancelled/renamed guard -- live in sparsh_follow_up.py, because
// mandatory_depends_on and everything in this file are client-side only and
// are never evaluated by the server (see PLAN.md, "Decision 1"). Treat every
// toggle here as a convenience for the counsellor, not as validation.

frappe.ui.form.on("Sparsh Follow Up", {
	refresh: function (frm) {
		set_baseline_ticket_query(frm);
		toggle_connected_only_sections(frm);
		show_habit_answered_reminder(frm);
		color_red_flag(frm);
	},

	caregiver_id: function (frm) {
		// A new caregiver invalidates whatever Ticket was previously chosen.
		frm.set_value("baseline_ticket", "");
		set_baseline_ticket_query(frm);
	},

	call_disposition: function (frm) {
		toggle_connected_only_sections(frm);
	},

	safety_red_flag: function (frm) {
		color_red_flag(frm);
		if (frm.doc.safety_red_flag && frm.doc.call_disposition !== "Connected") {
			// The server throws on this combination (a call that never
			// connected cannot have observed a red flag); warn here so the
			// counsellor sees it before submit rather than after.
			frappe.show_alert({
				message: __("A red flag needs a Connected call -- the server will refuse this on submit."),
				indicator: "orange",
			});
		}
	},

	sunset_rule_binary: recompute_habit_preview,
	builder_habit_binary: recompute_habit_preview,
	stress_check_binary: recompute_habit_preview,
	sleep_check_binary: recompute_habit_preview,
});

function set_baseline_ticket_query(frm) {
	// Only the chosen caregiver's own, not-cancelled intake Tickets are valid
	// baselines. Mirrors the server-side check in validate(); this is the
	// convenience half, not the enforcement.
	frm.set_query("baseline_ticket", function () {
		return {
			filters: {
				patient_id: frm.doc.caregiver_id,
				docstatus: ["!=", 2],
			},
		};
	});
}

function toggle_connected_only_sections(frm) {
	// Decision 1: the eight connected-only fields are reqd only when the call
	// actually connected. mandatory_depends_on in the JSON gives the red
	// asterisk already; this only dims the sections visually so a not-answered
	// call reads as "nothing to fill in" rather than "form is broken".
	const connected = frm.doc.call_disposition === "Connected";
	frm.dashboard.clear_headline();
	if (!connected && frm.doc.call_disposition) {
		frm.dashboard.set_headline(
			__("Call outcome is {0} -- progress, lifestyle and new-pledge fields are not required.", [
				frm.doc.call_disposition,
			])
		);
	}
}

function show_habit_answered_reminder(frm) {
	if (frm.doc.habit_score_display) {
		frm.set_intro(frm.doc.habit_score_display, "blue");
	}
}

function color_red_flag(frm) {
	if (frm.doc.safety_red_flag) {
		frm.set_intro(__("Safety red flag recorded -- clinical review status: {0}", [
			frm.doc.clinical_review_status || __("Pending"),
		]), "red");
	}
}

function recompute_habit_preview(frm) {
	// habit_score / habit_answered / habit_score_display are server-computed
	// (Decision 5 -- blank must never collapse into zero, and the mapping is
	// pure Python so client and server cannot drift). This only nudges the
	// counsellor to save so the read-only display catches up; it does not
	// compute the score itself.
	if (!frm.is_new() || frm.doc.__islocal) {
		frm.dirty();
	}
}
