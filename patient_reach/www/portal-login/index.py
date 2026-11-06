from patient_reach.portal.shell import setup_page


def get_context(context):
    setup_page(context, redirect_if_logged_in=True, title="Log in")
