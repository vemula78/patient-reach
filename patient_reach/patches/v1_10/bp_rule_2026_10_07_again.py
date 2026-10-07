"""Run v1_8's regrade again (07-Oct-2026 night).

At 13:00 on 07-Oct a form opened before v1_8 saved its old `bp_rule` back,
putting TKT-2026-01262 on the 06-Oct rule again. `ticket_before_validate` now
keeps the stored rule on every save after the first, so this cannot recur; this
patch moves whatever reverted back to Dr Nayanjeet's rule, with v1_8's Comment
and counts. Idempotent.
"""

from patient_reach.patches.v1_8.bp_rule_2026_10_07 import execute  # noqa: F401
