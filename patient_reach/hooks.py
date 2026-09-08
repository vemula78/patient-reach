app_name = "patient_reach"
app_title = "Patient Reach"
app_publisher = "Frugal Scientific"
app_description = "A custom application built on the Frappe Framework to extend and tailor business workflows, data management, and automation according to specific organizational needs."
app_email = "ziya.fazal@frugalscientific.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "patient_reach",
		"logo": "/assets/patient_reach/images/patient_reach.svg",
		"title": "Patient Reach",
		"route": "/app/healthcare",
		"has_permission": "patient_reach.api.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/patient_reach/css/patient_reach.css"
# app_include_js = "/assets/patient_reach/js/patient_reach.js"

# include js, css files in header of web template
# web_include_css = "/assets/patient_reach/css/patient_reach.css"
# web_include_js = "/assets/patient_reach/js/patient_reach.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "patient_reach/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "patient_reach/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "patient_reach.utils.jinja_methods",
# 	"filters": "patient_reach.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "patient_reach.install.before_install"
# after_install = "patient_reach.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "patient_reach.uninstall.before_uninstall"
# after_uninstall = "patient_reach.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "patient_reach.utils.before_app_install"
# after_app_install = "patient_reach.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "patient_reach.utils.before_app_uninstall"
# after_app_uninstall = "patient_reach.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "patient_reach.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"patient_reach.tasks.all"
# 	],
# 	"daily": [
# 		"patient_reach.tasks.daily"
# 	],
# 	"hourly": [
# 		"patient_reach.tasks.hourly"
# 	],
# 	"weekly": [
# 		"patient_reach.tasks.weekly"
# 	],
# 	"monthly": [
# 		"patient_reach.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "patient_reach.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "patient_reach.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "patient_reach.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["patient_reach.utils.before_request"]
# after_request = ["patient_reach.utils.after_request"]

# Job Events
# ----------
# before_job = ["patient_reach.utils.before_job"]
# after_job = ["patient_reach.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"patient_reach.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"Patient-custom_hospital_id",
					"Patient-custom_aadhaar_no",
					"Patient-custom_district",
					"Patient-custom_state",
					"Patient-custom_country",
					"Patient-custom_mother_name",
					"Patient-custom_language",
					"Patient-custom_other_known_language",
					"Branch-custom_branch_code",
					"Patient-custom_counselled_date",
					"Patient-custom_counsellor_name",
					"Patient-custom_other_known_language",
					"Patient-custom_marital_status",
					# Ticket's whole tab layout. Added 06-Sep-2026: these six Tab
					# Breaks (and the Counselling section) existed ONLY in the
					# care.sssihms.org database, so ticket.json described a form
					# with no tabs at all and a rebuild on a fresh site could not
					# reproduce what the counselling team actually uses.
					"Ticket-custom_caregiver_profiling__habits",
					"Ticket-custom_measurements",
					"Ticket-custom_change__referrals",
					"Ticket-custom_status__enquiry",
					"Ticket-custom_clinical_review",
					"Ticket-custom_touchpoint",
					"Ticket-custom_counselling_section",
					"Ticket-custom_counselling_col",
					# 07-Sep-2026: Curry/Hurry/Worry moved out of tab 1 into their
					# own "Habits & Principles" tab, as the Google Form has them.
					"Ticket-custom_habits__principles",
					"Ticket-custom_habits_principles_section",
				],
			]
		],
	},
	{
		# Ticket added 06-Sep-2026, same reason as its Custom Fields above: 41
		# Property Setters -- including a field_order override for the whole
		# doctype -- lived only in the site database.
		#
		# NOTE: the Patient entries in fixtures/property_setter.json are STALE.
		# The live site has 27 Property Setters on Patient; only 12 are
		# exported here. Re-exporting them would change Patient's form on the
		# next migrate, so it was left alone deliberately rather than swept in
		# with the Ticket work. Reconcile it as its own task.
		"dt": "Property Setter",
		"filters": [["doc_type", "in", ["Patient", "Ticket"]]],
	},
	{
		"dt": "Client Script",
		"filters": [
			[
				"name",
				"in",
				[
					"Pledge Form in Raise Ticket",
					"Filter District based on State",
					"Patient hide comments and activity",
					"Visit Button in Ticket",
				],
			]
		],
	},
	{
		# Server Scripts intentionally no longer exported. The three that lived
		# here (Visit Owner Creation, Patient List, Update todo list if forward
		# to is updated) moved to patient_reach/doc_events.py on 06-Sep-2026.
		# Keeping them as fixtures reinstalled them on every migrate, so they ran
		# alongside the hooks and overwrote user-supplied values. They also
		# required server_script_enabled, which grants anyone with Script Manager
		# arbitrary server-side Python.
		"dt": "Server Script",
		"filters": [["name", "in", []]],
	},
	{"dt": "Translation", "filters": [["source_text", "in", ["Ticket", "Patient"]]]},
]

doc_events = {
	"Patient": {
		"autoname": "patient_reach.api.patient_autoname",
		"after_insert": "patient_reach.doc_events.patient_after_insert",
	},
	"Ticket": {
		"before_validate": "patient_reach.doc_events.ticket_before_validate",
		"after_insert": "patient_reach.doc_events.ticket_after_insert",
		"after_save": "patient_reach.doc_events.ticket_after_save",
	},
}

override_doctype_dashboards = {"Patient": "patient_reach.api.get_data"}
