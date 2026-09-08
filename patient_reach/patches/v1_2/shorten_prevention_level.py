"""Store the prevention level as a short code; the description text moves to help text.

Requested by the counselling team on 07-Sep-2026: the dropdown should hold
`Level 2`, not the full sentence, and the explanatory text should sit under the
field rather than in the database. Reports and exports become readable, and the
Excel backlog already records short codes, so the pending import needs no
mapping.

This runs immediately after v1_1's rewording patch, which put the FULL text in.
Doing it in two steps is deliberate rather than tidy: v1_1 was already built,
rehearsed and deployed when this request arrived, and rewriting a released patch
is worse than adding a second one. Both maps are 1:1 by level, so nothing is
reinterpreted either time.

Two source vocabularies are accepted, because both exist in the wild:
  * the v1_1 wording, on every row migrated earlier today;
  * the pre-v1_1 wording, in case any site has not taken v1_1 yet.
"""

import frappe

CODES = ["Level 1", "Level 1s", "Level 2", "Level 2s", "Level 3", "Level 3s", "Level 4", "Level 4s"]

# v1_1 wording -> short code
FROM_V1_1 = {
	"Level 1 (Primordial): Healthy, No bad habits, No Cardiometabolic diagnosis, No family history.": "Level 1",
	'Level 1s: "S" modifier (Past surgeries and Structural illness) for Level 1.': "Level 1s",
	'Level 2 (Primary): "At Risk." Has habits (Smoking/Stress/Pre-diabetic/family history) but no disease yet.': "Level 2",
	'Level 2s: "S" modifier (Past surgeries and Structural illness) for Level 2.': "Level 2s",
	'Level 3 (Secondary): "Sick." Has BP/Diabetes/Obesity/Heart Disease/Kidney/Thyroid/Liver disease.': "Level 3",
	'Level 3s: "S" modifier (Past surgeries and Structural illness) for Level 3.': "Level 3s",
	'Level 4 (Tertiary): "Survivor." Already had a heart attack/stroke.': "Level 4",
	'Level 4s: "S" modifier (Past surgeries and Structural illness) for Level 4.': "Level 4s",
}

# the wording that predates v1_1, for a site that skipped it
FROM_ORIGINAL = {
	"Level 1 - Healthy,no habits,no family history": "Level 1",
	"Level 1s- S modifier(Past surgeries and Structural illness) for Level 1": "Level 1s",
	"Level 2 - At Risk(Smoking/Sugar/Stress), no disease yet": "Level 2",
	"Level 2s- S modifier(Past surgeries and Structural illness) for Level 2": "Level 2s",
	"Level 3 - Has BP/Diabetes/Obesity etc": "Level 3",
	"Level 3s- S modifier(Past surgeries and Structural illness) for Level 3": "Level 3s",
	"Level 4 - Survivor(Heart attack/stroke)": "Level 4",
	"Level 4s- S modifier (Past surgeries and Structural illness) for Level 4": "Level 4s",
}


def _log(msg):
	print(f"[patient_reach v1_2 prevention_level] {msg}")


def execute():
	total = frappe.db.sql("select count(*) from tabTicket where ifnull(prevention_level,%s)<>%s", ("", ""))[
		0
	][0]
	_log(f"tickets with a prevention level: {total}")

	moved = 0
	for mapping, label in ((FROM_V1_1, "v1_1 wording"), (FROM_ORIGINAL, "pre-v1_1 wording")):
		for old, code in mapping.items():
			names = frappe.get_all("Ticket", filters={"prevention_level": old}, pluck="name")
			for n in names:
				frappe.db.set_value("Ticket", n, "prevention_level", code, update_modified=False)
			if names:
				_log(f"{label}: {len(names)} rows -> {code!r}")
			moved += len(names)
	_log(f"migrated: {moved}")

	# Anything left that is neither blank nor a short code would render as an
	# empty field, so say so rather than let it be found later.
	rows = frappe.db.sql(
		"select prevention_level, count(*) from tabTicket "
		"where ifnull(prevention_level,%s)<>%s group by prevention_level",
		("", ""),
	)
	unknown = [(v, c) for v, c in rows if v not in CODES]
	if unknown:
		_log(f"WARNING not covered by either map, left as-is and now unselectable: {unknown}")
	else:
		_log("every populated value is now a short code")
	frappe.db.commit()
