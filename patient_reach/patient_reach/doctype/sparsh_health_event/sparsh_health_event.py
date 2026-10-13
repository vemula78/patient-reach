# Copyright (c) 2026, Patient Reach and contributors
# For license information, please see license.txt

"""A heart or brain event (DRL A8) recorded on a visit or on the follow-up
list. Its Level 4 column is worked out by the parent's save
(drl_v14.event_level_4); the row itself holds only what the caregiver or a
record says."""

from frappe.model.document import Document


class SparshHealthEvent(Document):
	pass
