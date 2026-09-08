"""Reword two Ticket Selects to the Google Form's own wording, and carry the data.

Changing a Select's options does not touch stored values: a Ticket keeps the old
string and the field simply renders blank, because the value is no longer an
offered option. Silent, and it would have hit 830 risk-profiling values and 549
string-test results.

Both maps are 1:1 and by level/verdict, so nothing is reinterpreted -- only
reworded. Re-running is a no-op: once migrated, no old string matches.
"""

import frappe

PREVENTION_LEVEL = {
	"Level 1 - Healthy,no habits,no family history": "Level 1 (Primordial): Healthy, No bad habits, No Cardiometabolic diagnosis, "
	"No family history.",
	"Level 1s- S modifier(Past surgeries and Structural illness) for Level 1": 'Level 1s: "S" modifier (Past surgeries and Structural illness) for Level 1.',
	"Level 2 - At Risk(Smoking/Sugar/Stress), no disease yet": 'Level 2 (Primary): "At Risk." Has habits (Smoking/Stress/Pre-diabetic/family '
	"history) but no disease yet.",
	"Level 2s- S modifier(Past surgeries and Structural illness) for Level 2": 'Level 2s: "S" modifier (Past surgeries and Structural illness) for Level 2.',
	"Level 3 - Has BP/Diabetes/Obesity etc": 'Level 3 (Secondary): "Sick." Has BP/Diabetes/Obesity/Heart Disease/Kidney/'
	"Thyroid/Liver disease.",
	"Level 3s- S modifier(Past surgeries and Structural illness) for Level 3": 'Level 3s: "S" modifier (Past surgeries and Structural illness) for Level 3.',
	"Level 4 - Survivor(Heart attack/stroke)": 'Level 4 (Tertiary): "Survivor." Already had a heart attack/stroke.',
	"Level 4s- S modifier (Past surgeries and Structural illness) for Level 4": 'Level 4s: "S" modifier (Past surgeries and Structural illness) for Level 4.',
}

STRING_TEST_RESULT = {
	"PASS (Waist < 0.5 x Height)": "PASS (Ends touch/ W:H < 0.5)",
	"FAIL (Central Obesity)": "FAIL (Gap exists - Central Obesity)",
}


def _log(msg):
	print(f"[patient_reach v1_1 rewording] {msg}")


def _remap(fieldname, mapping):
	moved = 0
	for old, new in mapping.items():
		names = frappe.get_all("Ticket", filters={fieldname: old}, pluck="name")
		for n in names:
			frappe.db.set_value("Ticket", n, fieldname, new, update_modified=False)
		if names:
			_log(f"{fieldname}: {len(names)} rows  {old[:38]!r} -> {new[:38]!r}")
		moved += len(names)

	# Anything left that is neither blank nor one of the new strings is a value
	# this patch did not know about. Report it rather than leave it to be found
	# as a blank field months later.
	valid = set(mapping.values())
	stragglers = frappe.db.sql(
		f"select `{fieldname}`, count(*) from tabTicket "
		f"where ifnull(`{fieldname}`, '') <> '' group by `{fieldname}`"
	)
	unknown = [(v, c) for v, c in stragglers if v not in valid]
	if unknown:
		_log(
			f"WARNING {fieldname}: {len(unknown)} value(s) not covered by the map, left untouched and now "
			f"unselectable: {unknown}"
		)
	_log(f"{fieldname}: {moved} rows migrated, {len(stragglers)} distinct values remain")
	return moved


def execute():
	_remap("prevention_level", PREVENTION_LEVEL)
	_remap("string_test_result", STRING_TEST_RESULT)
	frappe.db.commit()
