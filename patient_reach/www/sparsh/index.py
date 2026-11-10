"""Phone home for Sai Sparsh volunteers: two buttons, First Visit and Follow-up Calls.

Staff-side users only. A signed-out visitor is sent to the normal /login and returned here;
a portal-only (patient/caregiver) user goes to /enquiries instead.
"""
import frappe
from frappe.utils import get_fullname

STAFF_ROLES = {"Volunteer", "Staff", "Doctor", "System Manager"}


def get_context(context):
    context.no_cache = 1
    context.no_header = 1
    context.show_sidebar = 0
    context.title = "Sai Sparsh"
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/sparsh"
        raise frappe.Redirect
    if not STAFF_ROLES & set(frappe.get_roles()):
        frappe.local.flags.redirect_location = "/enquiries"
        raise frappe.Redirect
    context.user_full_name = get_fullname(frappe.session.user)
