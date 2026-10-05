"""Turn the typed counsellor names on Tickets into counsellors' logins.

`counsellor_name` became a Link to User on 05-Oct-2026 so a counsellor is
picked, not typed. On that day 10 of the 39 values in use were not logins
(31 Tickets). A Link holding a non-user value cannot be saved, so those
Tickets would refuse every later edit until someone re-picked the counsellor.

Matching, in order, against users holding the Volunteer role (every counsellor
had it) -- and only when exactly one user matches, never a guess between two:

1. the value contains an email address that is a User;
2. the value equals a user's full name (case, spacing and punctuation ignored);
3. the value is the first name of exactly one user's full name.

The team confirmed the two values these rules cannot settle by full name on
05-Oct-2026 (one first name only, one name followed by the login). No name
or login is written into this file: the repo is public.

Anything still unmatched is left as it was and listed in the patch output, by
value, for a person to fix. Every change leaves a Comment on the Ticket.
Idempotent: a re-run finds only logins and the unmatched.
"""

import re

import frappe

PATCH_DATE = "05-Oct-2026"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _log(msg):
	print(f"[patient_reach v1_5 counsellor_name] {msg}")


def _norm(s):
	return re.sub(r"[^a-z]", "", (s or "").lower())


def _match(value, users, counsellors):
	emails = [e for e in EMAIL.findall(value) if e in users]
	if len(set(emails)) == 1:
		return emails[0]
	by_full = [name for name, full in counsellors if _norm(full) and _norm(full) == _norm(value)]
	if len(by_full) == 1:
		return by_full[0]
	first = [name for name, full in counsellors if full and _norm(full.split()[0]) == _norm(value)]
	if len(first) == 1 and _norm(value):
		return first[0]
	return None


def execute():
	users = set(frappe.get_all("User", pluck="name"))
	counsellors = frappe.db.sql(
		"""select u.name, u.full_name from `tabUser` u
		where exists (select 1 from `tabHas Role` r
			where r.parent = u.name and r.parenttype = 'User' and r.role = 'Volunteer')"""
	)
	rows = frappe.db.sql(
		"select name, counsellor_name from tabTicket where ifnull(counsellor_name, '') <> ''"
	)
	typed = [(t, v) for t, v in rows if v not in users]
	_log(
		f"tickets with a counsellor: {len(rows)}; not a login: {len(typed)} ({len({v for _, v in typed})} values)"
	)

	mapped, unmatched = 0, {}
	for ticket, value in typed:
		login = _match(value, users, counsellors)
		if not login:
			unmatched[value] = unmatched.get(value, 0) + 1
			continue
		frappe.db.set_value("Ticket", ticket, "counsellor_name", login, update_modified=False)
		_comment(ticket, value, login)
		mapped += 1
	_log(f"mapped to a login: {mapped}")
	for value, n in unmatched.items():
		_log(f"UNMATCHED, left as typed: {value!r} on {n} ticket(s) -- pick the counsellor on those Tickets")
	frappe.db.commit()


def _comment(ticket, old, new):
	content = f'Counsellor changed from the typed "{old}" to the login {new} (patch patient_reach.v1_5, {PATCH_DATE})'
	if frappe.db.exists(
		"Comment", {"reference_doctype": "Ticket", "reference_name": ticket, "content": content}
	):
		return
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Ticket",
			"reference_name": ticket,
			"content": content,
		}
	).insert(ignore_permissions=True)
