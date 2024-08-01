{
    'name': 'Hospital Management',
    'version': '1.0.0',
    'category': 'Hospital',
    'author': 'Erfan Ahammed',
    'sequence': -100,
    'summary': 'Hospital management system',
    'description': """Hospital Management system""",
    'depends': [
        'mail',
        'product',
        'report_xlsx',
    ],
    'data': [

        'security/ir.model.access.csv',

        'data/patient_tag_data.xml',
        'data/patient.tag.csv',
        'data/sequence_data.xml',
        'data/appointment_sequence_data.xml',

        'wizard/cancel_appointment_wizard.xml',
        'wizard/search_appointment_wizard.xml',
        'wizard/all_patient_report.xml',

        'views/patient.xml',
        'views/female_patient_view.xml',
        'views/appointment_view.xml',
        'views/patient_tag_view.xml',
        'views/operation_view.xml',
        'views/menu.xml',

        'report/all_patient_list.xml',
        'report/search_appointment_details.xml',
        'report/patient_details.xml',
        'report/patient_card.xml',
        'report/report.xml',

    ],
    'demo': [],
    'installable': True,
    "application": True,
    'auto_install': False,
    'license': 'LGPL-3',

}
