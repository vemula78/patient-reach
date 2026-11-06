"""Shared page setup + hospital details for all portal pages."""
import frappe
from frappe.utils import get_fullname

# Source: https://sssihms.org/
HOSPITAL = {
    "name": "Sri Sathya Sai Institute of Higher Medical Sciences",
    "short_name": "SSSIHMS",
    "tagline": "Service to Man is Service to God",
    "note": "Tertiary care, provided at no charge to the patient.",
    "website": "https://sssihms.org/",
    "appointments_phone": "080-47104600",
    "campuses": [
        {
            "name": "Whitefield",
            "address": "EPIP Area, Whitefield, Bangalore 560 066, Karnataka, India",
            "phone": "+91 (080) 47104600",
            "tel": "+918047104600",
            "site": "https://whitefield.sssihms.org",
        },
        {
            "name": "Prasanthigram",
            "address": "Prasanthigram, Puttaparthi, Sri Sathya Sai District, Andhra Pradesh 515134, India",
            "phone": "+91 (08555) 287388 Ext: 1709",
            "tel": "+918555287388",
            "email": "publicrelationspg@sssihms.org.in",
            "site": "https://prasanthigram.sssihms.org/",
        },
    ],
}


def setup_page(context, login_required=False, redirect_if_logged_in=False, title=None):
    context.no_cache = 1
    context.no_header = 1
    context.show_sidebar = 0
    context.title = title or HOSPITAL["name"]
    context.hospital = HOSPITAL
    context.logged_in = frappe.session.user != "Guest"
    context.user_full_name = get_fullname(frappe.session.user) if context.logged_in else ""
    # Developer sites only: tell testers which OTP to use when no SMS is sent.
    from patient_reach.portal.auth import otp_mode, static_otp

    context.demo_otp = static_otp() if otp_mode() == "static" else None

    if login_required and not context.logged_in:
        _redirect("/portal-login")
    if redirect_if_logged_in and context.logged_in:
        _redirect("/enquiries")


def _redirect(path):
    frappe.local.flags.redirect_location = path
    raise frappe.Redirect
