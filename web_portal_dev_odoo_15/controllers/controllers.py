from odoo.addons.portal.controllers.portal import CustomerPortal, pager

from odoo import http,_
from odoo.http import request


class CustomerPortalController(CustomerPortal):

    @http.route(['/new/hospital'], type='http', method='["POST", "GET"]', auth='user', website=True)
    def create_new_patient_info(self, **kwargs):
        patient_obj = request.env['medical.patient'].search([])
        patients_sex = [('m', 'Male'), ('f', 'Female')]
        patients_marital_status = [('s', 'Single'), ('m', 'Married'), ('w', 'Widowed'), ('d', 'Divorced'),
                                  ('x', 'Separated')]
        context = {
            'patients_sex': patients_sex,
            'marital_status': patients_marital_status
        }


        if request.httprequest.method == 'POST':
            error_list = []
            if not kwargs.get('name'):
                error_list.append('Name field is required')
            if not kwargs.get('street'):
                error_list.append('Address field is required')
            if not kwargs.get('date_of_birth'):
                error_list.append('Date of Birth field is required')
            if not kwargs.get('marital_status'):
                error_list.append('Marital Status field is required')
            if not kwargs.get('sex'):
                error_list.append('Sex field is required')


            if not error_list:
                create_partner = {
                    'name': kwargs.get('name'),
                    'street': kwargs.get('street')
                }
                partner_id = request.env['res.partner'].create(create_partner)
                create_patient = {
                    'patient_id': partner_id.id,
                    'date_of_birth': kwargs.get('date_of_birth'),
                    'marital_status': kwargs.get('marital_status'),
                    'sex': kwargs.get('sex'),
                    'street': partner_id.street
                }
                patient_id = request.env['medical.patient'].create(create_patient)
                success = 'Patient Record Created Successfully!!'
                context['success_msg'] = success
            else:
                context['error_list'] = error_list
        else:
            print('Get Method...........')

        return request.render('web_portal_dev_15.new_hospital_patient_creation_form', context)

    def _prepare_home_portal_values(self, counters):
        rtn = super(CustomerPortalController, self)._prepare_home_portal_values(counters)
        rtn['hms_count'] = request.env['medical.patient'].search_count([])
        return rtn

    def _get_hospital(self):
        return {
            'id': {'label': _('ID Desc'), 'order': 'id desc'},
            'name': {'label': _('Name'), 'order': 'name'}
        }


    @http.route(['/my/hospital/', '/my/hospital/page/<int:page>'], type='http',auth='user', website=True)
    def my_hospital(self, page=1, sortby=None, search="", search_in="All", **kwargs):
        values = self._prepare_portal_layout_values()

        search_list = {
            'All': {'label': _('ALL'), 'input': 'all', 'domain':[]},
            'Patient': {'label': _('Patient Name'), 'input': 'Patient', 'domain':[('patient_id.name','ilike',search)]}
        }
        search_domain = search_list[search_in]['domain']
        searchbar_sortings = self._get_hospital()
        if not sortby:
            sortby = 'id'
        sort_order = searchbar_sortings[sortby]['order']
        patients_cnt = request.env['medical.patient'].search_count(search_domain)
        page_details = pager(
            url='/my/hospital/',
            url_args={'sortby':sortby, 'search_in':search_in, 'search':search},
            total=patients_cnt,
            page=page,
            step=3
        )
        patients = request.env['medical.patient'].search(search_domain, limit=3, order=sort_order, offset=page_details['offset'])
        values.update({
            'patients': patients,
            'page_name': 'patients_list_view',
            'pager': page_details,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'default_url': '/my/hospital',
            'search_in': search_in,
            'searchbar_inputs': search_list,
            'search': search

        })
        return request.render('web_portal_dev_15.hospital_patient_info_portal', values)


    @http.route(['/my/hospital/<model("medical.patient"):patient_id>'], type='http', auth='user', website=True)
    def my_hospital_form(self, patient_id, **kwargs):
        context = {'patient_id': patient_id, 'page_name': 'patients_form_view'}
        patient_records = request.env['medical.patient'].search([])
        patient_ids = patient_records.ids
        patient_index = patient_ids.index(patient_id.id)
        if patient_index != 0 and patient_ids[patient_index - 1]:
            context['prev_record'] = '/my/hospital/{}'.format(patient_ids[patient_index - 1])

        if patient_index < len(patient_ids) - 1 and patient_ids[patient_index + 1]:
            context['next_record'] = '/my/hospital/{}'.format(patient_ids[patient_index + 1])
        return request.render('web_portal_dev_15.hospital_form_view_based_on_id', context)

