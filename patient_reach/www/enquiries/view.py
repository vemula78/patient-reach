import frappe
from frappe.utils import format_datetime

from patient_reach.portal.shell import setup_page
from patient_reach.portal.status import patient_status


def get_context(context):
    setup_page(context, login_required=True, title="Enquiry")

    name = frappe.form_dict.get("name")
    # Not found and "not yours" look identical, so references cannot be probed.
    if not name or not frappe.db.exists("Portal Enquiry", {"name": name, "enquirer": frappe.session.user}):
        frappe.throw("Enquiry not found", frappe.DoesNotExistError)

    doc = frappe.get_doc("Portal Enquiry", name)
    context.enquiry = {
        "name": doc.name,
        "subject": doc.subject,
        "details": doc.details,
        "created": format_datetime(doc.creation, "dd MMM yyyy, hh:mm a"),
        "status": patient_status(doc.workflow_state),
        # Staff identity is deliberately not exposed to the patient.
        "responses": [
            {"date": format_datetime(r.responding_date, "dd MMM yyyy, hh:mm a"), "text": r.response}
            for r in doc.get("responses")
        ],
    }
    context.just_submitted = bool(frappe.form_dict.get("submitted"))
