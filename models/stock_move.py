from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.depends('product_uom_qty', 'product_uom', 'picking_id.picking_type_id')
    def _compute_quantity(self):
        super(StockMove, self)._compute_quantity()
        for move in self:
            if move.picking_id and move.picking_id.picking_type_id.code == 'incoming':
                move.quantity = 0