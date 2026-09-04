import frappe
from frappe.model.naming import make_autoname
from healthcare.healthcare.doctype.patient.patient_dashboard import (
    get_data as standard_get_data
)

def has_app_permission():
    return True

def patient_autoname(doc, method):
    branch_code = frappe.db.get_value(
        "Branch",
        doc.custom_hospital_id,
        "custom_branch_code"
    )
    doc.name = make_autoname(f"SWF-{branch_code}-.####")


def get_data(data=None):
    if not data:
        data = standard_get_data()

    data.setdefault("non_standard_fieldnames", {})

    # Tell Frappe that Ticket links to Patient via patient_id
    data["non_standard_fieldnames"]["Ticket"] = "patient_id"

    data["transactions"].append(
        {
            "label": frappe._("Support"),
            "items": ["Ticket"]
        }
    )

    return data