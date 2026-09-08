"""Move Patient Condition / Patient Addictions from one Yes-No Select to checkboxes.

The counselling team asked for the Google Form's layout: two checkboxes per
disease (Has Disease, Has Medication) and a single checkbox per addiction.

Two things this patch deliberately does NOT do:

* It does not delete or overwrite `response`. That Select is the only record of
  what was actually asked before 07-Sep-2026, and it is what `has_disease` /
  `has_addiction` are derived from -- so keeping it makes this patch re-runnable
  and keeps the original answer auditable.

* It does not touch `has_medication`. Medication was never asked before today,
  so it stays unticked and `medication_recorded` is what says whether that
  means "no" or "never asked".

  `medication_recorded` IS backfilled here, and must be. An earlier version of
  this patch assumed Frappe would create the new Check column with `default 0`,
  leaving old rows at 0 ("not recorded") while the doctype default of 1 applied
  only to new documents. That is wrong: Frappe creates the column using the
  FIELD's default, so all 412 existing rows came out as 1 -- claiming medication
  status had been established when it was never asked. Caught by rehearsing this
  patch against a restore of live data.

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
    print(f"[patient_reach v1_1 conditions] {msg}")


def execute():
    _log("Patient Condition rows: {}".format(frappe.db.count("Patient Condition")))
    _log("Patient Addictions rows: {}".format(frappe.db.count("Patient Addictions")))

    # 1. Rename condition values. Row-at-a-time via set_value rather than a bulk
    #    UPDATE: a keyless UPDATE is refused outright when the server runs in
    #    safe-update mode, which bit this project once already.
    renamed = 0
    for old, new in CONDITION_RENAMES.items():
        names = frappe.get_all("Patient Condition", filters={"condition": old}, pluck="name")
        for n in names:
            frappe.db.set_value("Patient Condition", n, "condition", new, update_modified=False)
        if names:
            _log(f"renamed {old:<26} -> {new:<14} {len(names)} rows")
        renamed += len(names)
    _log(f"condition values renamed: {renamed}")

    # 2. Derive the checkboxes from the answer that was actually recorded.
    for doctype, target in (("Patient Condition", "has_disease"),
                            ("Patient Addictions", "has_addiction")):
        yes = frappe.get_all(doctype, filters={"response": "Yes"}, pluck="name")
        for n in yes:
            frappe.db.set_value(doctype, n, target, 1, update_modified=False)
        no = frappe.db.count(doctype, {"response": "No"})
        blank = frappe.db.count(doctype, {"response": ["in", ["", None]]})
        _log(f"{doctype}: {len(yes)} -> {target}=1, {no} were 'No', {blank} had no answer recorded "
             "(left unticked)")

    # 3. Mark every row that predates the medication question as "not recorded".
    #    Every Patient Condition row that exists when this patch runs was
    #    captured before the two-checkbox model, so all of them qualify. New rows
    #    get 1 from the doctype default. This relies on Frappe's guarantee that a
    #    patch in patches.txt runs once per site -- re-running it after new rows
    #    existed would wrongly mark those as unrecorded too.
    legacy = frappe.get_all("Patient Condition", pluck="name")
    for n in legacy:
        frappe.db.set_value("Patient Condition", n, "medication_recorded", 0,
                            update_modified=False)
    _log(f"medication_recorded=0 on {len(legacy)} pre-existing rows (medication was not asked "
         "before this release, so an unticked Has Medication must not read as 'no')")

    # 4. Report, do not touch, the rows on a value the form no longer offers.
    for doctype, field in (("Patient Condition", "condition"),
                           ("Patient Addictions", "habits")):
        n = frappe.db.count(doctype, {field: "Other"})
        if n:
            _log(f"{doctype}: {n} rows keep {field}='Other', which is no longer selectable "
                 "(retained on purpose)")

    frappe.db.commit()
