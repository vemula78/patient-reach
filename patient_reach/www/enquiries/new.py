from patient_reach.portal.shell import setup_page


def get_context(context):
    setup_page(context, login_required=True, title="New Enquiry")
