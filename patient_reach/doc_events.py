"""Document event handlers for Patient Reach.

These were previously four **Server Script** documents stored in the database.
That had three problems: they lived only in a Docker volume so they were absent
from the app source and from `bench backup`; they required
`server_script_enabled` in `common_site_config.json`, which grants anyone with
the Script Manager role arbitrary server-side Python; and they could not be code
reviewed or shipped with an image.

Moved into the app 06-Sep-2026. Behaviour is preserved except where noted.
"""

import re

import frappe

# --------------------------------------------------------------------------
# Derived measurements
# --------------------------------------------------------------------------

def _string_test_result(waist_cm, height_cm):
    """PASS when waist is under half of height. Returns None if not computable."""
    try:
        waist = float(waist_cm or 0)
        height = float(height_cm or 0)
    except (TypeError, ValueError):
        return None
    if waist <= 0 or height <= 0:
        return None
    # These two strings must stay identical to string_test_result's options in
    # ticket.json. A mismatch does not raise -- the Select just holds a value it
    # will not offer, and the grid renders blank.
    return ("PASS (Ends touch/ W:H < 0.5)" if waist < 0.5 * height
            else "FAIL (Gap exists - Central Obesity)")


def _bp_status(bp_reading):
    """Classify a free-text BP reading such as "128/84".

    The field is free text and genuinely contains non-numeric entries — "BP
    machine not working" appears in live data — so anything unparseable returns
    "Needs Reference" rather than guessing.

    Readings between normal and high (systolic 120-139 or diastolic 80-89) also
    return "Needs Reference": the field has no "Elevated" option, and silently
    calling that band "Normal" would understate it.
    """
    if not bp_reading:
        return None
    m = re.search(r"(\d{2,3})\s*[/\\-]\s*(\d{2,3})", str(bp_reading))
    if not m:
        return "Needs Reference"
    systolic, diastolic = int(m.group(1)), int(m.group(2))
    if not (50 <= systolic <= 300 and 30 <= diastolic <= 200):
        return "Needs Reference"
    if systolic < 90 or diastolic < 60:
        return "Low"
    if systolic >= 140 or diastolic >= 90:
        return "High"
    if systolic < 120 and diastolic < 80:
        return "Normal"
    return "Needs Reference"


# --------------------------------------------------------------------------
# Ticket (the Visit form)
# --------------------------------------------------------------------------

def ticket_before_validate(doc, method=None):
    # Drafts are saved part-way through a consultation, so mandatory fields are
    # only enforced on submit. (Previously the "Visit - Skip Mandatory on Draft
    # Save" server script.)
    if doc.docstatus == 0:
        doc.flags.ignore_mandatory = True

    # Derive the measurements the counselling team asked to have calculated
    # rather than chosen by hand. These are descriptive summaries of values the
    # counsellor already recorded, not clinical decisions.
    result = _string_test_result(doc.get("waist_cm"), doc.get("height_cm"))
    if result:
        doc.string_test_result = result

    status = _bp_status(doc.get("bp_reading"))
    if status:
        doc.bp_status = status


def ticket_after_insert(doc, method=None):
    # Stamp who counselled and when. counselled_date is only defaulted when the
    # user has NOT supplied one: the counselling team reported that the date of
    # counselling is routinely different from the date the record is entered,
    # and the previous server script overwrote their entry with doc.creation
    # every time.
    if not doc.get("counselled_date"):
        doc.db_set("counselled_date", frappe.utils.getdate(doc.creation), update_modified=False)
    if not doc.get("counsellor_name"):
        # doc.owner -- the login id, not the display name. Briefly changed to
        # get_fullname() on 06-Sep-2026; the counselling team asked for the user
        # id back on 07-Sep-2026, so that is withdrawn. The field is editable,
        # so this only fills a blank.
        doc.db_set("counsellor_name", doc.owner, update_modified=False)


def ticket_after_save(doc, method=None):
    """Reassign the ToDo when a ticket is forwarded to a different doctor."""
    if not (doc.has_value_changed("forward_to") or doc.has_value_changed("forward_reason")):
        return
    if not doc.forward_to:
        return

    description = f"Ticket {doc.name} assigned to you"
    if doc.forward_reason:
        description += f"\nReason: {doc.forward_reason}"

    for existing in frappe.get_all(
        "ToDo",
        filters={"reference_type": doc.doctype, "reference_name": doc.name,
                 "status": ("!=", "Cancelled")},
        pluck="name",
    ):
        frappe.delete_doc("ToDo", existing, ignore_permissions=True)

    frappe.get_doc({
        "doctype": "ToDo",
        "owner": doc.forward_to,
        "assigned_by": frappe.session.user,
        "reference_type": doc.doctype,
        "reference_name": doc.name,
        "description": description,
        "status": "Open",
    }).insert(ignore_permissions=True)


# --------------------------------------------------------------------------
# Patient
# --------------------------------------------------------------------------

def patient_after_insert(doc, method=None):
    # Same "do not overwrite a user-supplied date" rule as the Ticket.
    if not doc.get("custom_counselled_date"):
        doc.db_set("custom_counselled_date", frappe.utils.getdate(doc.creation),
                   update_modified=False)
    if not doc.get("custom_counsellor_name"):
        doc.db_set("custom_counsellor_name", doc.owner, update_modified=False)
