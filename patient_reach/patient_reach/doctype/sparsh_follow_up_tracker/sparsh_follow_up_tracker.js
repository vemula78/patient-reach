// Copyright (c) 2026, Patient Reach and contributors
// For license information, please see license.txt

// Convenience only: the server (sparsh_follow_up_tracker.py) sets the chained
// Scheduled Dates and refuses a Next Follow-up Date without Yes / May be.

const GOING_ON = ["Yes", "May be"];

frappe.ui.form.on("Sparsh Follow-up Tracker", {
	setup: function (frm) {
		// Only counsellors' logins, as on the visit form.
		[1, 2, 3].forEach((n) =>
			frm.set_query(`call_${n}_by`, () => ({ query: "patient_reach.api.counsellor_query" }))
		);
	},

	call_1_level: (frm) => file_level(frm, 1),
	call_1_s_modifier: (frm) => file_level(frm, 1),
	call_2_level: (frm) => file_level(frm, 2),
	call_2_s_modifier: (frm) => file_level(frm, 2),
	call_3_level: (frm) => file_level(frm, 3),
	call_3_s_modifier: (frm) => file_level(frm, 3),

	call_1_interest: (frm) => clear_next_date_unless_going_on(frm, 1),
	call_2_interest: (frm) => clear_next_date_unless_going_on(frm, 2),

	call_1_next_date: (frm) => frm.set_value("call_2_scheduled_date", frm.doc.call_1_next_date || null),
	call_2_next_date: (frm) => frm.set_value("call_3_scheduled_date", frm.doc.call_2_next_date || null),
});

function clear_next_date_unless_going_on(frm, n) {
	if (!GOING_ON.includes(frm.doc[`call_${n}_interest`]) && frm.doc[`call_${n}_next_date`]) {
		frm.set_value(`call_${n}_next_date`, null);
	}
}

// The filed Current Prevention Level is the Level, with an "s" when the S
// modifier is Yes ("Level 2" and Yes is "Level 2s"), as on the visit. The
// server files it again on save (sparsh_follow_up_tracker.py).
function file_level(frm, n) {
	const level = frm.doc[`call_${n}_level`];
	const filed = level ? level + (frm.doc[`call_${n}_s_modifier`] === "Yes" ? "s" : "") : null;
	frm.set_value(`call_${n}_prevention_level`, filed);
}
