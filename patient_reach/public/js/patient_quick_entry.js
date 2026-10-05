// The health app's "New Patient/Caregiver" popup, trimmed for Sai Sparsh
// (05-Oct-2026). Health hard-codes the popup's fields in
// healthcare/public/js/patient_quick_entry.js, so they cannot be hidden with a
// Property Setter; this extends that class instead of editing the health app.
//
// - drops Blood Group, Email, Invite as User and the Primary Address section,
//   none of which the counselling team uses (Invite as User would give a
//   caregiver a login);
// - adds District under State, filtered to the chosen State.
//
// Re-check after every health upgrade: this relies on Health's class name,
// its get_standard_fields(), and render_dialog() splicing the remaining
// mandatory fields (which include State) into the popup.
(function () {
	const DROPPED = new Set([
		"blood_group",
		"email",
		"invite_user",
		"address_line1",
		"address_line2",
		"pincode",
		"city",
		"state",
		"country",
	]);
	const BREAKS = ["Section Break", "Column Break"];

	function without_empty_breaks(fields) {
		const out = [];
		for (const df of fields) {
			const prev = out[out.length - 1];
			if (df.fieldtype === "Column Break" && (!prev || prev.fieldtype === "Section Break")) continue;
			if (df.fieldtype === "Section Break" && prev && prev.fieldtype === "Section Break") out.pop();
			out.push(df);
		}
		while (out.length && BREAKS.includes(out[out.length - 1].fieldtype)) out.pop();
		return out;
	}

	function install() {
		const Base = frappe.ui.form.PatientQuickEntryForm;
		if (!Base || Base.patient_reach) return;

		class PatientReachQuickEntryForm extends Base {
			get_standard_fields() {
				return without_empty_breaks(super.get_standard_fields().filter((df) => !DROPPED.has(df.fieldname)));
			}

			render_dialog() {
				const state_at = this.mandatory.findIndex((df) => df.fieldname === "custom_state");
				const district = frappe.meta.get_docfield("Patient", "custom_district");
				if (state_at >= 0 && district && !this.mandatory.some((df) => df.fieldname === "custom_district")) {
					this.mandatory.splice(
						state_at + 1,
						0,
						Object.assign({}, district, {
							get_query: () => ({ filters: { state: this.dialog.get_value("custom_state") } }),
						})
					);
				}
				super.render_dialog();
				const state = this.dialog && this.dialog.fields_dict.custom_state;
				if (state) state.df.onchange = () => this.dialog.set_value("custom_district", "");
			}
		}
		PatientReachQuickEntryForm.patient_reach = true;
		frappe.ui.form.PatientQuickEntryForm = PatientReachQuickEntryForm;
	}

	// healthcare.bundle.js is included before this file (app install order),
	// so the class normally exists already.
	install();
	document.addEventListener("DOMContentLoaded", install);
})();
