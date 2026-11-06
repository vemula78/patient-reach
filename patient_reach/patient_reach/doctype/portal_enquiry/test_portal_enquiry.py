# Copyright (c) 2026, Frugal Scientific and Contributors
# See license.txt

"""Tests for the patient portal: OTP login, raising an enquiry, and its workflow.

`UnitTestCase`, not `IntegrationTestCase`, for the reason given in
doctype/ticket/test_ticket.py: IntegrationTestCase builds test records for every
Link field, and Portal Enquiry links to Branch, whose Branch Code is mandatory
here. The tests touch the database themselves and roll back at the end.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.model.workflow import WorkflowTransitionError, apply_workflow
from frappe.tests import UnitTestCase

from patient_reach.patches.v1_14.create_portal_enquiry_workflow import execute as create_workflow
from patient_reach.portal import auth
from patient_reach.portal.enquiry import create_enquiry

MOBILE_A, MOBILE_B = "9876500001", "9876500002"
OTP = "654321"


def _raw(fn):
	"""The function under the rate limiter, so a test is not throttled by it."""
	return getattr(fn, "__wrapped__", fn)


def _clear_otp_keys(mobile):
	cache = auth._cache()
	for key in (
		f"portal_otp:login:{mobile}",
		f"portal_otp:register:{mobile}",
		f"portal_otp_gap:{mobile}",
		f"portal_otp_sends:{mobile}",
	):
		cache.delete_value(key)


class TestPortalAuth(UnitTestCase):
	def setUp(self):
		self.mobile = auth.normalize_mobile(MOBILE_A)
		_clear_otp_keys(self.mobile)
		self.addCleanup(_clear_otp_keys, self.mobile)
		self.addCleanup(frappe.db.rollback)

	def _send(self, purpose, full_name=None):
		with patch.object(auth, "_make_otp", return_value=OTP), patch.object(auth, "_deliver") as deliver:
			out = _raw(auth.send_otp)(MOBILE_A, purpose, full_name)
		return out, deliver

	def test_mobile_is_normalised_and_junk_refused(self):
		self.assertEqual(auth.normalize_mobile("+91 98765-00001"), "+919876500001")
		for bad in ("12345", "5876500001", "", None, "98765000012345"):
			with self.assertRaises(frappe.ValidationError):
				auth.normalize_mobile(bad)

	def test_static_otp_is_ignored_off_developer_sites(self):
		with patch.dict(frappe.local.conf, {"portal_otp_mode": "static", "developer_mode": 0}):
			self.assertEqual(auth.otp_mode(), "sms")
		with patch.dict(frappe.local.conf, {"portal_otp_mode": "static", "developer_mode": 1}):
			self.assertEqual(auth.otp_mode(), "static")

	def test_login_for_an_unregistered_number_looks_like_success_and_sends_nothing(self):
		out, deliver = self._send("login")
		self.assertTrue(out["sent"])
		deliver.assert_not_called()
		self.assertIsNone(auth._cache().get_value(f"portal_otp:login:{self.mobile}"))

	def test_register_then_wrong_otps_lock_the_code(self):
		out, deliver = self._send("register", "Test Caregiver")
		deliver.assert_called_once_with(self.mobile, OTP)
		verify = _raw(auth.verify_otp)
		for _ in range(auth.MAX_ATTEMPTS):
			with self.assertRaises(frappe.ValidationError):
				verify(MOBILE_A, "000000", "register", "Test Caregiver")
		# Even the right code no longer works: it was spent by the failures.
		with self.assertRaises(frappe.ValidationError):
			verify(MOBILE_A, OTP, "register", "Test Caregiver")
		self.assertFalse(frappe.db.exists("User", {"mobile_no": self.mobile}))

	def test_register_creates_a_portal_user_once_and_the_otp_is_single_use(self):
		self._send("register", "Test Caregiver")
		verify = _raw(auth.verify_otp)
		with patch.object(frappe.local, "login_manager", MagicMock(), create=True) as lm:
			out = verify(MOBILE_A, OTP, "register", "Test Caregiver")
		self.assertTrue(out["verified"])
		user = frappe.db.get_value("User", {"mobile_no": self.mobile}, ["name", "user_type"], as_dict=True)
		self.assertEqual(user.user_type, "Website User")
		self.assertIn(auth.ROLE, frappe.get_roles(user.name))
		lm.login_as.assert_called_once_with(user.name)
		with self.assertRaises(frappe.ValidationError):
			verify(MOBILE_A, OTP, "register", "Test Caregiver")


class TestExotelDelivery(UnitTestCase):
	CONF = {
		"exotel_subdomain": "api.example.test",
		"exotel_account_sid": "acct",
		"exotel_api_key": "key",
		"exotel_api_token": "token",
		"portal_sms_sender_id": "SENDER",
		"portal_sms_dlt_entity_id": "1000000000000000001",
		"portal_sms_dlt_template_id": "1000000000000000002",
	}

	def _conf(self, **over):
		return patch.dict(frappe.local.conf, {**self.CONF, "developer_mode": 0, **over})

	def test_unconfigured_site_refuses_instead_of_pretending(self):
		missing = {k: None for k in self.CONF}
		with patch.dict(frappe.local.conf, {**missing, "developer_mode": 0}), patch(
			"patient_reach.portal.auth.requests.post"
		) as post:
			with self.assertRaises(frappe.ValidationError):
				auth._deliver("+919876500001", OTP)
		post.assert_not_called()

	def test_sms_goes_to_exotel_with_the_dlt_fields_and_basic_auth(self):
		with self._conf(), patch("patient_reach.portal.auth.requests.post") as post:
			post.return_value.status_code = 200
			auth._deliver("+919876500001", OTP)
		(url,), kw = post.call_args
		self.assertEqual(url, "https://api.example.test/v1/Accounts/acct/Sms/send.json")
		self.assertEqual(kw["auth"], ("key", "token"))
		self.assertEqual(kw["data"]["DltTemplateId"], "1000000000000000002")
		self.assertEqual(kw["data"]["DltEntityId"], "1000000000000000001")
		self.assertEqual(kw["data"]["To"], "+919876500001")
		self.assertIn(OTP, kw["data"]["Body"])
		self.assertNotIn("token", url)

	def test_a_gateway_refusal_is_an_error_and_the_log_holds_no_number_or_otp(self):
		with self._conf(), patch("patient_reach.portal.auth.requests.post") as post, patch(
			"patient_reach.portal.auth.frappe.log_error"
		) as log:
			post.return_value.status_code = 400
			with self.assertRaises(frappe.ValidationError):
				auth._deliver("+919876500001", OTP)
		logged = " ".join(map(str, log.call_args.kwargs.values()))
		self.assertNotIn("9876500001", logged)
		self.assertNotIn(OTP, logged)


class TestPortalEnquiry(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_workflow()
		cls.portal_a = cls._user("portal.a@example.test", MOBILE_A, auth.ROLE)
		cls.portal_b = cls._user("portal.b@example.test", MOBILE_B, auth.ROLE)
		cls.staff = cls._user("portal.staff@example.test", None, "Staff")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDownClass()

	@staticmethod
	def _user(email, mobile, role):
		doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"mobile_no": ("+91" + mobile) if mobile else None,
				"user_type": "Website User" if role == auth.ROLE else "System User",
				"send_welcome_email": 0,
			}
		)
		doc.append("roles", {"role": role})
		doc.flags.ignore_permissions = True
		doc.insert()
		return doc.name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Portal Enquiry")

	def _raise(self, user, subject="Appointment query", details="When can I get an appointment?"):
		frappe.set_user(user)
		return frappe.get_doc("Portal Enquiry", create_enquiry(subject, details)["name"])

	def test_guest_cannot_raise_an_enquiry(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			create_enquiry("Appointment query", "When can I get an appointment?")

	def test_enquiry_is_owned_by_the_session_user_and_starts_as_draft(self):
		doc = self._raise(self.portal_a)
		self.assertEqual(doc.enquirer, self.portal_a)
		self.assertEqual(doc.workflow_state, "Draft")
		self.assertEqual(doc.mobile_no, "+91" + MOBILE_A)
		self.assertTrue(doc.enquirer_name)

	def test_html_is_stripped_and_length_is_enforced(self):
		doc = self._raise(self.portal_a, "<b>Hello</b> there", "<script>x</script>Please call me back")
		self.assertNotIn("<", doc.subject + doc.details)
		frappe.set_user(self.portal_a)
		with self.assertRaises(frappe.ValidationError):
			create_enquiry("ok", "too short")

	def test_a_sixth_enquiry_in_an_hour_is_refused(self):
		for i in range(5):
			self._raise(self.portal_a, f"Enquiry number {i}")
		with self.assertRaises(frappe.ValidationError):
			create_enquiry("One more enquiry", "This is the sixth one this hour")

	def test_a_portal_user_reads_only_their_own_enquiry_and_cannot_edit_it(self):
		doc = self._raise(self.portal_a)
		frappe.set_user("Administrator")
		self.assertTrue(frappe.has_permission("Portal Enquiry", "read", doc, user=self.portal_a))
		self.assertFalse(frappe.has_permission("Portal Enquiry", "read", doc, user=self.portal_b))
		self.assertFalse(frappe.has_permission("Portal Enquiry", "write", doc, user=self.portal_a))
		self.assertFalse(frappe.has_permission("Portal Enquiry", "delete", doc, user=self.portal_a))

	def test_respond_needs_a_response_and_staff_can_walk_the_workflow(self):
		doc = self._raise(self.portal_a)
		frappe.set_user(self.staff)
		doc = apply_workflow(doc, "Review")
		self.assertEqual(doc.workflow_state, "Reviewed by Staff")
		with self.assertRaises(WorkflowTransitionError):
			apply_workflow(doc, "Respond")
		doc.append("responses", {"response": "Please call 080-47104600 on a weekday."})
		doc.save()
		doc = apply_workflow(doc, "Respond")
		self.assertEqual(doc.workflow_state, "Responded By Staff")
		row = doc.responses[0]
		self.assertEqual(row.responder, self.staff)
		self.assertTrue(row.responding_date)

	def test_administrator_can_work_an_enquiry(self):
		"""Administrator holds every role, Patient Portal User too; the enquirer check must not catch it."""
		doc = self._raise(self.portal_a)
		frappe.set_user("Administrator")
		doc = apply_workflow(doc, "Review")
		self.assertIn(doc.workflow_state, ("Reviewed by Volunteer", "Reviewed by Staff", "Reviewed by Doctor"))

	def test_a_patient_posting_directly_cannot_forge_status_or_a_hospital_reply(self):
		frappe.set_user(self.portal_a)
		doc = frappe.get_doc(
			{
				"doctype": "Portal Enquiry",
				"enquirer": self.portal_b,
				"workflow_state": "Responded By Doctor",
				"enquirer_name": "Someone Else",
				"subject": "Forged subject here",
				"details": "A forged enquiry body of text",
				"responses": [{"response": "The hospital says everything is fine"}],
			}
		)
		doc.insert()
		self.assertEqual(doc.enquirer, self.portal_a)
		self.assertEqual(doc.workflow_state, "Draft")
		self.assertNotEqual(doc.enquirer_name, "Someone Else")
		self.assertEqual(len(doc.responses), 0)

	def test_the_patient_cannot_move_their_own_enquiry_along(self):
		doc = self._raise(self.portal_a)
		with self.assertRaises((WorkflowTransitionError, frappe.PermissionError)):
			apply_workflow(doc, "Respond")

	def test_every_workflow_state_is_one_the_patient_page_understands(self):
		from patient_reach.portal.status import STATUS_MAP
		from patient_reach.patches.v1_14.create_portal_enquiry_workflow import STATES

		for state, _style, _role in STATES:
			self.assertIn(state, STATUS_MAP, f"patient page has no wording for {state}")
