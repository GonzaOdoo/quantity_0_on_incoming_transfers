from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class PurchaseRequirements(models.Model):
    _name = 'purchase.requirements'
    _description = 'Purchase requirements'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', default='Pedido prueba')
    state = fields.Selection(selection=[('draft','Borrador'),('pending','Por aprobar'),('done','Hecho')])
    date = fields.Date('Fecha')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    category_id = fields.Many2one('product.category', string='Sector', required=True)
    line_ids = fields.One2many('purchase.requirements.line', 'requirement_id', string='Líneas de requerimiento')

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            # Elimina las líneas existentes (opcional)
            self.line_ids = [(5, 0, 0)]

            # Busca productos de esta categoría
            products = self.env['product.product'].search([('categ_id', '=', self.category_id.id)])

            # Prepara los comandos para agregar nuevas líneas
            lines = []
            for product in products:
                lines.append((0, 0, {
                    'product_id': product.id,
                    'partner_id': self.partner_id.id,
                }))
            self.line_ids = lines
                
class PurchaseRequirementsLine(models.Model):
    _name = 'purchase.requirements.line'
    _description = 'Linea de requirimiento'

    partner_id = fields.Many2one('res.partner',string='Proveedor')
    requirement_id = fields.Many2one('purchase.requirements',string='Requirimiento')
    product_id = fields.Many2one('product.product',string='Producto')
    qty_on_hand = fields.Float('A mano', readonly=True, compute='_compute_qty')
    qty_forecast = fields.Float('Pronosticado', readonly=True, compute='_compute_qty')
    qty_to_order = fields.Float('A ordenar')
    min = fields.Float('Min',related='product_id.reordering_min_qty')
    max = fields.Float('Max',related='product_id.reordering_max_qty')
    
    @api.depends('product_id')
    def _compute_qty(self):
        for record in self:
            if not record.product_id:
                record.qty_on_hand = False
                record.qty_forecast = False
            else:
                record.qty_on_hand = record.product_id.qty_available
                record.qty_forecast = record.product_id.qty_available + record.product_id.incoming_qty - record.product_id.outgoing_qty

    
    