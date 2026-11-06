import frappe
from frappe.utils import format_datetime

from patient_reach.portal.shell import setup_page
from patient_reach.portal.status import patient_status


def get_context(context):
    setup_page(context, login_required=True, title="My Enquiries")

    rows = frappe.get_all(
        "Portal Enquiry",
        filters={"enquirer": frappe.session.user},  # only this user's enquiries
        fields=["name", "subject", "workflow_state", "creation"],
        order_by="creation desc",
        limit_page_length=100,
    )
    context.enquiries = [
        {
            "name": r.name,
            "subject": r.subject,
            "created": format_datetime(r.creation, "dd MMM yyyy"),
            "status": patient_status(r.workflow_state),
        }
        for r in rows
    ]
