from odoo import models, fields, api

class ProducTemplate(models.Model):
    _inherit = 'product.template'

    presentation = fields.Char('Presentación')
    origin_code = fields.Char('Código de Origen')