"""Maps internal workflow states to what the patient sees. Edit here only."""

_RECEIVED = ("Received", "received", "We have received your enquiry. Our team will review it shortly.")
_REVIEW = ("Under review", "review", "Our team is reviewing your enquiry.")
_RESPONDED = ("Responded", "responded", "We have replied to your enquiry. Please see the response below.")
_FORWARDED = ("Forwarded to our care team", "forwarded", "Your enquiry has been forwarded to our care team.")
_CLOSED = ("Closed", "closed", "This enquiry is closed. If you need anything further, please raise a new enquiry.")

STATUS_MAP = {
    "Draft": _RECEIVED,
    "Reviewed by Volunteer": _REVIEW,
    "Reviewed by Staff": _REVIEW,
    "Reviewed by Doctor": _REVIEW,
    "Responded By Staff": _RESPONDED,
    "Responded By Doctor": _RESPONDED,
    "Ticket created": _FORWARDED,
    "Rejected": _CLOSED,
    "Duplicate": _CLOSED,
}


def patient_status(workflow_state):
    label, tone, message = STATUS_MAP.get(workflow_state, _RECEIVED)
    return {"label": label, "tone": tone, "message": message}
