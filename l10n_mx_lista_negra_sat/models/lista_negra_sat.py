# -*- coding: utf-8 -*-

from odoo import models, fields, api
import chardet
import requests
from odoo.tools import pycompat
import io

class ListaNegraSat(models.Model):
    _name = "lista.negra.sat"
    
    vat=fields.Char(string='RFC')
    name = fields.Char(string='Nombre del Contribuyente')

    @api.model
    def download_list_negra_sat_file(self):
        url = self.env['ir.config_parameter'].sudo().get_param('list_negra_url', default='http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv')
        #url='https://transfer.sh/P8IFg/Listado_Completo_69-B.csv'

        try:
            csv_data = requests.get(url).content
        except Exception:
            return
        encoding = chardet.detect(csv_data)['encoding'].lower()
        csv_data = csv_data.decode(encoding).encode('utf-8')
        csv_iterator = pycompat.csv_reader(io.BytesIO(csv_data))
        
        created_vats = []
        
        for index, row in enumerate(csv_iterator):
            if index<3 or len(row)<3:
                continue
            
            vat = row[1]
            name = row[2]
            if vat in created_vats:
                continue
            record_exist = self.search([('vat','=', vat)])
            if record_exist:
                record_exist.write({'name':name})
            else:
                self.create({'name': name, 'vat': vat})
            created_vats.append(vat)
        return True
    
class ResPartner(models.Model):
    _inherit = "res.partner"

    lista_negra_en_sat=fields.Boolean(string="Lista Negra En SAT")

    @api.model
    def automatic_lista_negra_en_sat_true(self):
        if hasattr(self, 'vat'):
            partners = self.search([('vat','!=',False),('lista_negra_en_sat','!=', True)])
            vats = dict([(p.id,p.vat) for p in partners])

            lista_negras = self.env['lista.negra.sat'].search([('vat','in', list(vats.values()))])
            lista_negras_vat = lista_negras.mapped('vat')
            partner_ids = []
            if lista_negras_vat:
                for partner_id, vat in vats.items():
                    if vat in lista_negras_vat:
                        partner_ids.append(partner_id)
            if partner_ids:
                self.browse(partner_ids).write({'lista_negra_en_sat': True})
        return True
