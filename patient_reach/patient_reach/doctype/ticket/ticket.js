// Copyright (c) 2024, Patient Reach and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ticket", {
    refresh: function(frm) {
        toggle_sections(frm);

        frm.set_query("forward_to", function() {
            return {
                query: "frappe.core.doctype.user.user.user_query",
                filters: {
                    role: "Doctor"
                }
            };
        });
    },
    ticket_type: function(frm) {
        toggle_sections(frm);
    },
    visit_type: function(frm) {
        toggle_sections(frm);
    },
    nodal_centre: function(frm) {
        if (frm.doc.nodal_centre === 'SSSIHMS-WFD Preventive Medicine Centre - Sai Sparsh') {
            frm.set_value('department', 'Cardiology - SSSIHMS');
            frm.set_value('ticket_type', 'Preventive Cardiology');
        }else{
            frm.set_value('department', '');
            frm.set_value('ticket_type', '');
        }
    }
});

function toggle_sections(frm) {

    let show_patient_enquiry =
        frm.doc.ticket_type === 'Patient Enquiry' &&
        frm.doc.visit_type === 'First Visit';

    frm.set_df_property(
        'patient_enquiry_section',
        'hidden',
        show_patient_enquiry ? 0 : 1
    );

    let show_preventive =
        frm.doc.ticket_type === 'Preventive Cardiology' &&
        frm.doc.visit_type === 'First Visit';

    frm.set_df_property(
        'preventive_cardiology_section',
        'hidden',
        show_preventive ? 0 : 1
    );

    frm.set_df_property('section_d', 'hidden', show_preventive ? 0 : 1);
    frm.set_df_property('bp_heading', 'hidden', show_preventive ? 0 : 1);
    frm.set_df_property('section_title', 'hidden', show_preventive ? 0 : 1);
    frm.set_df_property(
        'clinical_section',
        'hidden',
        frm.doc.ticket_type === 'Preventive Cardiology' ? 1 : 0
    );
}