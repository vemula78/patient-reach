# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""The rows of Sparsh Counsellor Statistics, with no database."""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

from patient_reach.patient_reach.report.sparsh_counsellor_statistics.sparsh_counsellor_statistics import (
	NO_COUNSELLOR,
	build_rows,
)

REPORT = json.loads((Path(__file__).parent / "sparsh_counsellor_statistics.json").read_text())


class TestCounsellorStatistics(UnitTestCase):
	def test_one_row_per_counsellor_by_name(self):
		rows = build_rows(
			{"b@x.org": "Bina", "a@x.org": "anil"},
			{"a@x.org": 3},
			{"a@x.org": 4, "b@x.org": 1},
			{"b@x.org": 2},
		)
		self.assertEqual(
			rows,
			[
				{
					"counsellor_name": "anil",
					"counsellor_email": "a@x.org",
					"caregivers": 3,
					"visits": 4,
					"follow_ups": 0,
				},
				{
					"counsellor_name": "Bina",
					"counsellor_email": "b@x.org",
					"caregivers": 0,
					"visits": 1,
					"follow_ups": 2,
				},
			],
		)

	def test_a_login_with_records_but_no_volunteer_role_is_still_counted(self):
		rows = build_rows({}, {"old@x.org": 5}, {}, {})
		self.assertEqual([(r["counsellor_name"], r["caregivers"]) for r in rows], [("old@x.org", 5)])

	def test_records_with_no_counsellor_are_counted_in_a_last_row(self):
		"""1 draft visit on care had no counsellor on 30-Oct-2026: the column
		totals must still equal the page's Total Visits."""
		rows = build_rows({"a@x.org": "Anil"}, {"a@x.org": 3}, {"a@x.org": 4, None: 1, "": 2}, {})
		self.assertEqual(
			[(r["counsellor_name"], r["counsellor_email"], r["visits"]) for r in rows],
			[("Anil", "a@x.org", 4), (NO_COUNSELLOR, "", 3)],
		)
		self.assertEqual(sum(r["visits"] for r in rows), 7)

	def test_only_the_statistics_role_opens_it(self):
		self.assertEqual([r["role"] for r in REPORT["roles"]], ["Sparsh Statistics Viewer"])
		roles = json.loads((Path(__file__).parents[3] / "fixtures" / "role.json").read_text())
		self.assertIn("Sparsh Statistics Viewer", [r["name"] for r in roles])
