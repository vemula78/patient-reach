import frappe
from frappe import _
from frappe.model.naming import make_autoname
from healthcare.healthcare.doctype.patient.patient_dashboard import get_data as standard_get_data


def has_app_permission():
	return True


def patient_autoname(doc, method):
	# An unset hospital used to interpolate the string "None" into the id, and 138
	# imported patients were named SWF-None-#### before anyone noticed. The field is
	# mandatory on the form, so only a bulk insert can reach here without one.
	branch_code = (
		frappe.db.get_value("Branch", doc.custom_hospital_id, "custom_branch_code")
		if doc.custom_hospital_id
		else None
	)
	if not branch_code:
		frappe.throw(
			_("Cannot name a Patient without a Hospital that has a Branch Code. "
			  "Set Hospital on the Patient, or give Branch {0} a Branch Code.").format(
				doc.custom_hospital_id or _("(none)")
			)
		)
	doc.name = make_autoname(f"SWF-{branch_code}-.####")


def get_data(data=None):
	if not data:
		data = standard_get_data()

	data.setdefault("non_standard_fieldnames", {})

	# Tell Frappe that Ticket links to Patient via patient_id
	data["non_standard_fieldnames"]["Ticket"] = "patient_id"

	data["transactions"].append({"label": frappe._("Support"), "items": ["Ticket"]})

	return data
