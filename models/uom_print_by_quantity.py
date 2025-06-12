# models/lot_label_layout.py
from collections import defaultdict
from odoo import models, fields, api

# models/uom_category.py
from odoo import models, fields

class UomCategory(models.Model):
    _inherit = 'uom.category'
    
    count_by_quantity = fields.Boolean(
        string='Unidad',
        help='If checked, products in this category will be counted by quantity in lot labels instead of as single units'
    )

class ProductLabelLayout(models.TransientModel):
    _inherit = 'lot.label.layout'

    def process(self):
        self.ensure_one()
        xml_id = 'stock.action_report_lot_label'
        if self.print_format == 'zpl':
            xml_id = 'stock.label_lot_template'
        
        if self.label_quantity == 'lots':
            docids = self.move_line_ids.lot_id.ids
        else:
            # Obtenemos todas las categorías marcadas para contar por cantidad
            quantity_categories = self.env['uom.category'].search([('count_by_quantity', '=', True)])
            uom_categ_unit = self.env.ref('uom.product_uom_categ_unit')
            
            quantity_by_lot = defaultdict(int)
            for move_line in self.move_line_ids:
                if not move_line.lot_id:
                    continue
                if (move_line.product_uom_id.category_id == uom_categ_unit or 
                    move_line.product_uom_id.category_id in quantity_categories):
                    quantity_by_lot[move_line.lot_id.id] += int(move_line.quantity)
                else:
                    quantity_by_lot[move_line.lot_id.id] += 1
            
            docids = []
            for lot_id, qty in quantity_by_lot.items():
                docids.extend([lot_id] * qty)
        
        report_action = self.env.ref(xml_id).report_action(docids, config=False)
        report_action.update({'close_on_report_download': True})
        return report_action