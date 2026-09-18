# PLAN-REVIEW-LOG

Append-only. Never edit a past entry. Any edit to PLAN.md invalidates the hash
recorded against it — re-hash and log a revision before treating the plan as current.

Scope: the Sparsh Follow Up build of 18-Sep-2026 only. Not a general project artifact.

## 2026-09-18 — plan recorded

- PLAN.md sha256: `1456387dbd9f7c2154d6eb0f927aadd80e4cd398f72a21ef6c621710a0ad75e5`
- Advisor: Fable 5.1 (`/panel` Phase 1)
- Orchestrator verification before builders were spawned: every file the plan
  asserts exists was checked. All present except
  `patient_reach/patient_reach/report/`, which the plan correctly lists as new.
- The plan's central trap was confirmed against `ticket.json` rather than taken on
  trust: intake `sunset_rule` is "Does the caregiver have dinner **after** 8 PM ?"
  (Yes = non-compliant) while the follow-up asks "heaviest meal **before** 8 PM?"
  (Yes = compliant, decision 4). Opposite polarity, same concept.
- `prevention_level` confirmed to carry `Level 1s/2s/3s/4s`, so decision 10's
  Level/S split is necessary and not cosmetic.
- PHI gate: AUDIT_MODE=code-only. The app repos hold no patient rows; Codex is
  passed source only, never data files or live values.

## 2026-09-18 — build, acceptance and audit

Plan hash this audit ran against: `1456387dbd9f7c2154d6eb0f927aadd80e4cd398f72a21ef6c621710a0ad75e5` (unchanged since the plan was recorded).

**Acceptance check A** — run by the orchestrator with its own frappe stub and its
own assertions, not the builders': **16 checks, 0 failed**. Every tuple PLAN.md
specifies matches, including the decisive decision-5 case (same healthy count,
different `answered`). 20/20 structural assertions on the JSON confirm all ten
decisions are traceable to a field or rule. Both hook targets resolve to real
functions. Lint: `ruff 0.8.1 check` all passed, `format --check` 49 files clean.

**Codex tier: gpt-5.6-sol.** `gpt-5.6-astra` was chosen first — clinical
aggregation, a one-way data patch, cross-file interaction — but that model is not
available on this account ("not supported when using Codex with a ChatGPT
account"), so the audit ran one tier down. Coverage at the lower tier is a
residual risk, though it did find the blocker.

23 findings. Disposition:

| # | Finding | Disposition |
|---|---|---|
| 1 | Overdue report crashes on mixed blank/populated call dates | **CONFIRMED, fixed.** Reproduced independently: `TypeError: '>' not supported between 'str' and 'datetime.date'`. A connected call plus a same-week No-Answer retry — routine under decision 1. `_sort_key` now coerces every element to `str`. |
| 4 | An unanswered retry drops a caregiver off the overdue list | **CONFIRMED, fixed.** Silent drop, and it fired exactly when a call had failed. `latest_per_ticket` now considers only Connected calls, since only those set `next_call_date`. |
| 5 | "Latest" keyed on programme week, not chronology | **CONFIRMED, fixed.** Same function; now ordered by `actual_call_date` then `creation`. |
| 21 | Two divergent `split_prevention_level` implementations | **CONFIRMED, fixed.** The report copy did not `strip()`. It now delegates to the controller's single implementation. |
| 22 | Stress patch does not reconcile | **CONFIRMED, fixed.** Now asserts before-total == after-total and zero surviving obsolete spellings, rolling back and throwing otherwise. |
| 15 | Number Cards / workspace tiles absent | **REJECTED.** They exist in the ops repo (`sssihms-frappe-deploy/workspaces/care-sssihms-org.number-cards.json`), which the code-only audit payload did not include. |
| 2, 3 | Baseline ownership and ticket-type enforced only client-side | **DEFERRED.** Real, and the same class as the `mandatory_depends_on` trap the plan already names. Needs a server guard in `_guard_baseline_ticket`; it is a behaviour change worth putting to the counselling team first. |
| 8, 17, 18, 19 | Post-submit clinical review; disposition changed after the fact; stale red-flag state | **DEFERRED.** Workflow questions for the physician, not defects in what was specified. |
| 6, 7, 9, 12, 13, 14, 16, 20 | Blank shells counted; draft/submitted mixed in one report; out-of-order backfill; invalid stored answers; race on the per-week guard; missing attempt date; one-sided date filters; unchecked numeric bounds | **DEFERRED**, recorded for the rehearsal. None changes a clinical number as specified; several are only reachable via API or import. |
| 10, 11, 23 | Invalid levels swallowed; reports bypass row-level permissions; no integration coverage | **DEFERRED.** 23 is inherent — there is no bench here; acceptance B exists precisely to cover it on the VM. |

**Re-audit needed.** Five fixes landed after Codex ran, four of them in
`sparsh_overdue_calls.py` and `sparsh_intake_overview.py`. The audit above does
not cover the fixed versions; treat it as stale for those two files.

Acceptance re-run after fixes: A 16/16, the three overdue regressions verified
(no crash, still listed after a failed retry, zero rows clean), lint clean.
