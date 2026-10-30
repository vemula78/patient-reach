# Copyright (c) 2026, Patient Reach and contributors
# See license.txt

"""The rows of Sparsh Counsellor Statistics, with no database."""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

from patient_reach.patient_reach.report.sparsh_counsellor_statistics.sparsh_counsellor_statistics import (
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
		rows = build_rows({}, {"old@x.org": 5, None: 2, "": 1}, {}, {})
		self.assertEqual([(r["counsellor_name"], r["caregivers"]) for r in rows], [("old@x.org", 5)])

	def test_only_the_statistics_role_opens_it(self):
		self.assertEqual([r["role"] for r in REPORT["roles"]], ["Sparsh Statistics Viewer"])
		roles = json.loads((Path(__file__).parents[3] / "fixtures" / "role.json").read_text())
		self.assertIn("Sparsh Statistics Viewer", [r["name"] for r in roles])
