from odoo import models,api,fields

class StockLocation(models.Model):
    _inherit = 'stock.location'

    product_category_id =  fields.Many2one('product.category',string='Categoria de Producto')
    