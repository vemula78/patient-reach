"""Mobile-number OTP register/login for the patient portal.

OTP is generated here, stored only as an HMAC hash in the Redis cache (5 min TTL),
and verified here. Mobile number is the business key; the Frappe User ID is a
deterministic synthetic email built from it.
"""
import hashlib
import hmac
import re
import secrets
import time

import frappe
import requests
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, strip_html_tags

ROLE = "Patient Portal User"
OTP_TTL = 300
MAX_ATTEMPTS = 5
RESEND_GAP = 30
MAX_SENDS_PER_HOUR = 5
PURPOSES = ("login", "register")


def _cache():
    c = frappe.cache
    return c() if callable(c) else c


def normalize_mobile(mobile):
    digits = re.sub(r"\D", "", mobile or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        frappe.throw("Please enter a valid 10-digit mobile number.")
    return "+91" + digits


def _hash(mobile, otp):
    key = (frappe.local.conf.get("encryption_key") or frappe.local.site).encode()
    return hmac.new(key, f"{mobile}:{otp}".encode(), hashlib.sha256).hexdigest()


def _user_for(mobile):
    return frappe.db.get_value("User", {"mobile_no": mobile, "enabled": 1}, "name")


def _clean_name(full_name):
    name = strip_html_tags(full_name or "").strip()
    if not (2 <= len(name) <= 60):
        frappe.throw("Please enter your full name (2 to 60 characters).")
    return name


def otp_mode():
    """'sms' (default) or 'static' (a fixed OTP, no SMS sent).

    'static' is honoured only on a site with developer_mode set. A live site
    never has it, so a leftover portal_otp_mode in site_config.json cannot
    turn the login into a fixed six-digit code.
    """
    if frappe.conf.get("portal_otp_mode") == "static" and frappe.conf.get("developer_mode"):
        return "static"
    return "sms"


def static_otp():
    return str(frappe.conf.get("portal_static_otp") or "123456")


def _demo_numbers():
    """None = any number allowed. Otherwise a set of normalised numbers."""
    cfg = frappe.conf.get("portal_demo_mobiles")
    if cfg is None:
        frappe.throw(
            "Static OTP mode needs 'portal_demo_mobiles' in site_config.json "
            "(use \"*\" to allow any number)."
        )
    if cfg == "*":
        return None
    return {normalize_mobile(m) for m in cfg}


def _check_static_allowed(mobile):
    allowed = _demo_numbers()
    if allowed is not None and mobile not in allowed:
        frappe.throw("This demo accepts only the configured test mobile numbers.")


def _make_otp():
    if otp_mode() == "static":
        return static_otp()
    return f"{secrets.randbelow(10**6):06d}"


# The DLT-registered wording. The gateway refuses a body that differs from the
# registered template, so change this only together with the template on the DLT portal.
DEFAULT_OTP_MESSAGE = "{otp} is your OTP to log in or register on SSSIHMS Patient Reach. Valid for 5 minutes. Do not share it with anyone."
EXOTEL_SETTINGS = (
    "exotel_subdomain",
    "exotel_account_sid",
    "exotel_api_key",
    "exotel_api_token",
    "portal_sms_sender_id",
    "portal_sms_dlt_entity_id",
    "portal_sms_dlt_template_id",
)


def _deliver(mobile, otp):
    """Send the OTP by SMS through Exotel. Every setting lives in site_config.json.

    The API key and token are secrets and so are never in code, the database or
    a log. Nothing about the recipient or the message is logged either.
    """
    if otp_mode() == "static":
        return  # developer sites: nothing is sent; the OTP is the configured static value
    conf = frappe.conf
    if not all(conf.get(k) for k in EXOTEL_SETTINGS):
        frappe.throw("SMS is not configured yet. Please contact the administrator.")

    template = conf.get("portal_otp_message") or DEFAULT_OTP_MESSAGE
    try:
        res = requests.post(
            f"https://{conf.exotel_subdomain}/v1/Accounts/{conf.exotel_account_sid}/Sms/send.json",
            auth=(conf.exotel_api_key, conf.exotel_api_token),
            data={
                "From": conf.portal_sms_sender_id,
                "To": mobile,
                "Body": template.format(otp=otp),
                "DltEntityId": conf.portal_sms_dlt_entity_id,
                "DltTemplateId": conf.portal_sms_dlt_template_id,
                "SmsType": "transactional",
            },
            timeout=10,
        )
        ok = res.status_code in (200, 201)
        status = res.status_code
    except requests.RequestException as e:
        ok, status = False, type(e).__name__
    if not ok:
        frappe.log_error(title="Portal OTP SMS failed", message=f"Exotel answered: {status}")
        frappe.throw("We could not send the OTP just now. Please try again in a few minutes.")


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=3600)
def send_otp(mobile, purpose="login", full_name=None):
    if purpose not in PURPOSES:
        frappe.throw("Invalid request.")
    mobile = normalize_mobile(mobile)
    if otp_mode() == "static":
        _check_static_allowed(mobile)
    user = _user_for(mobile)

    if purpose == "register":
        _clean_name(full_name)
        if user:
            frappe.throw("This mobile number is already registered. Please log in.")

    cache = _cache()
    gap_key, sends_key = f"portal_otp_gap:{mobile}", f"portal_otp_sends:{mobile}"
    if cache.get_value(gap_key):
        frappe.throw(f"Please wait {RESEND_GAP} seconds before requesting another OTP.")
    sends = cint(cache.get_value(sends_key))
    if sends >= MAX_SENDS_PER_HOUR:
        frappe.throw("Too many OTP requests. Please try again after some time.")
    cache.set_value(gap_key, 1, expires_in_sec=RESEND_GAP)
    cache.set_value(sends_key, sends + 1, expires_in_sec=3600)

    # Login for an unknown number answers exactly as for a known one but sends
    # nothing, so the login page cannot be used to find out who is registered.
    if purpose == "login" and not user:
        return {"sent": True, "resend_in": RESEND_GAP}

    otp = _make_otp()
    cache.set_value(
        f"portal_otp:{purpose}:{mobile}",
        {"h": _hash(mobile, otp), "a": 0, "exp": time.time() + OTP_TTL},
        expires_in_sec=OTP_TTL,
    )
    _deliver(mobile, otp)
    return {"sent": True, "resend_in": RESEND_GAP}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=40, seconds=3600)
def verify_otp(mobile, otp, purpose="login", full_name=None):
    if purpose not in PURPOSES:
        frappe.throw("Invalid request.")
    mobile = normalize_mobile(mobile)
    cache, key = _cache(), f"portal_otp:{purpose}:{mobile}"
    rec = cache.get_value(key)
    remaining = int(rec["exp"] - time.time()) if rec else 0
    if not rec or remaining <= 0:
        frappe.throw("OTP expired or invalid. Please request a new one.")
    if rec["a"] >= MAX_ATTEMPTS:
        cache.delete_value(key)
        frappe.throw("Too many wrong attempts. Please request a new OTP.")

    if not hmac.compare_digest(rec["h"], _hash(mobile, (otp or "").strip())):
        rec["a"] += 1
        cache.set_value(key, rec, expires_in_sec=remaining)
        frappe.throw("Incorrect OTP. Please try again.")

    cache.delete_value(key)  # single use

    if purpose == "register":
        user = _create_user(mobile, full_name)
    else:
        user = _user_for(mobile)
        if not user:
            frappe.throw("OTP expired or invalid. Please request a new one.")

    frappe.local.login_manager.login_as(user)
    return {"verified": True, "redirect": "/enquiries"}


def _create_user(mobile, full_name):
    name = _clean_name(full_name)
    if _user_for(mobile):
        frappe.throw("This mobile number is already registered. Please log in.")
    domain = frappe.conf.get("portal_user_email_domain") or "portal.local"
    doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": f"{mobile.lstrip('+')}@{domain}",
            "first_name": name,
            "mobile_no": mobile,
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0,
        }
    )
    doc.append("roles", {"role": ROLE})
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name
