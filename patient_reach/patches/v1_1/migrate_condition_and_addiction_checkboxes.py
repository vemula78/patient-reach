"""Move Patient Condition / Patient Addictions from one Yes-No Select to checkboxes.

The counselling team asked for the Google Form's layout: two checkboxes per
disease (Has Disease, Has Medication) and a single checkbox per addiction.

Two things this patch deliberately does NOT do:

* It does not delete or overwrite `response`. That Select is the only record of
  what was actually asked before 07-Sep-2026, and it is what `has_disease` /
  `has_addiction` are derived from -- so keeping it makes this patch re-runnable
  and keeps the original answer auditable.

* It does not write `medication_recorded`. Medication was never asked before
  today, so an unticked Has Medication on an old row must not read as "no
  medication". Nothing needs doing: Frappe adds a Check column as
  `default 0`, so every pre-existing row is already 0 ("not recorded"), while
  the doctype default of 1 applies only to documents created from now on. That
  asymmetry is the whole mechanism -- do not "fix" it by backfilling.

Condition names change to match the form's grid rows. "Other" is no longer
offered, but the rows already holding it keep the value and are reported below
rather than dropped.
"""

import frappe

# old value in the data -> the form's wording
CONDITION_RENAMES = {
    "Thyroid disease": "Thyroid",
    "Renal disease": "Kidney Issue",
    "Liver disease": "Liver Issue",
    "Dyslipidemia": "Cholesterol",
    "Cardiac disease": "Heart Disease",
    "Any cardiac event before": "Heart Attack",
    "Any surgery before": "Surgery",
}


def _log(msg):
    print("[patient_reach v1_1 conditions] %s" % msg)


def execute():
    _log("Patient Condition rows: %s" % frappe.db.count("Patient Condition"))
    _log("Patient Addictions rows: %s" % frappe.db.count("Patient Addictions"))

    # 1. Rename condition values. Row-at-a-time via set_value rather than a bulk
    #    UPDATE: a keyless UPDATE is refused outright when the server runs in
    #    safe-update mode, which bit this project once already.
    renamed = 0
    for old, new in CONDITION_RENAMES.items():
        names = frappe.get_all("Patient Condition", filters={"condition": old}, pluck="name")
        for n in names:
            frappe.db.set_value("Patient Condition", n, "condition", new, update_modified=False)
        if names:
            _log("renamed %-26s -> %-14s %s rows" % (old, new, len(names)))
        renamed += len(names)
    _log("condition values renamed: %s" % renamed)

    # 2. Derive the checkboxes from the answer that was actually recorded.
    for doctype, target in (("Patient Condition", "has_disease"),
                            ("Patient Addictions", "has_addiction")):
        yes = frappe.get_all(doctype, filters={"response": "Yes"}, pluck="name")
        for n in yes:
            frappe.db.set_value(doctype, n, target, 1, update_modified=False)
        no = frappe.db.count(doctype, {"response": "No"})
        blank = frappe.db.count(doctype, {"response": ["in", ["", None]]})
        _log("%s: %s -> %s=1, %s were 'No', %s had no answer recorded "
             "(left unticked)" % (doctype, len(yes), target, no, blank))

    # 3. Report, do not touch, the rows on a value the form no longer offers.
    for doctype, field in (("Patient Condition", "condition"),
                           ("Patient Addictions", "habits")):
        n = frappe.db.count(doctype, {field: "Other"})
        if n:
            _log("%s: %s rows keep %s='Other', which is no longer selectable "
                 "(retained on purpose)" % (doctype, n, field))

    frappe.db.commit()
