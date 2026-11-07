"""Fill the new Level and S modifier dropdowns of the Sparsh Follow-up Tracker
from the Current Prevention Level each call already holds (change request of
07-Nov-2026: the same two dropdowns the visit has). "Level 2s" becomes Level 2
and S modifier Yes; "Level 2" becomes Level 2 and No. The old string field
stays and is still what reports read.

A value that does not read as one of the eight Levels is left as it is, and
counted: the form hides that field now, so a free-text level would be invisible.
Counts only, no caregiver or row names. Idempotent: a call whose Level is
already set is not touched.
"""

import frappe

from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
	CALLS,
	split_level,
)

DOCTYPE = "Sparsh Follow-up Tracker"


def execute():
	fields = ["name"] + [f"call_{n}_{f}" for n in CALLS for f in ("prevention_level", "level")]
	rows = frappe.get_all(DOCTYPE, fields=fields, limit_page_length=0)
	split = unreadable = already = 0
	for row in rows:
		for n in CALLS:
			text, level = row.get(f"call_{n}_prevention_level"), row.get(f"call_{n}_level")
			if level:
				already += 1
			elif text:
				new_level, s_modifier = split_level(text)
				if new_level:
					frappe.db.set_value(
						DOCTYPE,
						row.name,
						{f"call_{n}_level": new_level, f"call_{n}_s_modifier": s_modifier},
						update_modified=False,
					)
					split += 1
				else:
					unreadable += 1
	print(
		f"split_follow_up_levels: {len(rows)} trackers; {split} call levels split, "
		f"{already} already set, {unreadable} not one of the eight Levels (left as typed, hidden on the form)"
	)
