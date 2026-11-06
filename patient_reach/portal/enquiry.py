import frappe
from frappe.utils import add_to_date, now_datetime, strip_html_tags


@frappe.whitelist(methods=["POST"])
def create_enquiry(subject, details):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to raise an enquiry.", frappe.PermissionError)

    subject = strip_html_tags(subject or "").strip()
    details = strip_html_tags(details or "").strip()
    if not (3 <= len(subject) <= 140):
        frappe.throw("Subject must be between 3 and 140 characters.")
    if not (10 <= len(details) <= 2000):
        frappe.throw("Details must be between 10 and 2000 characters.")

    recent = frappe.db.count(
        "Portal Enquiry",
        {"enquirer": frappe.session.user, "creation": [">", add_to_date(now_datetime(), hours=-1)]},
    )
    if recent >= 5:
        frappe.throw("You have raised several enquiries recently. Please try again later.")

    doc = frappe.get_doc(
        {
            "doctype": "Portal Enquiry",
            "enquirer": frappe.session.user,  # always the session user, never from the client
            "subject": subject,
            "details": details,
        }
    )
    doc.flags.ignore_permissions = True  # explicit checks above
    doc.insert()
    return {"name": doc.name}
