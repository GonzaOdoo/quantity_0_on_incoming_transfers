from odoo import models,api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom_id, company_id, supplier_info, po):
        """ Sobrescribimos para permitir inyectar una descripción personalizada desde approval. """
        vals = super()._prepare_purchase_order_line(
            product_id, product_qty, product_uom_id, company_id, supplier_info, po
        )

        # Intentamos obtener la descripción personalizada desde el contexto
        custom_description = self.env.context.get('custom_po_description')
        if custom_description:
            vals['name'] = custom_description

        return vals



class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def action_create_purchase_orders(self):
        """ Create Purchase Orders: one line per approval line, even if product repeats. """
        self.ensure_one()
        self.product_line_ids._check_products_vendor()
    
        for line in self.product_line_ids:
            seller = line.seller_id or line.product_id.with_company(line.company_id)._select_seller(
                quantity=line.po_uom_qty,
                uom_id=line.product_id.uom_po_id,
            )
            vendor = seller.partner_id
            po_domain = line._get_purchase_orders_domain(vendor)
            purchase_orders = self.env['purchase.order'].search(po_domain)
    
            if purchase_orders:
                # Siempre usar la primera orden existente (no importa si ya tiene líneas)
                purchase_order = purchase_orders[0]
            else:
                # Crear nueva orden
                po_vals = line._get_purchase_order_values(vendor)
                purchase_order = self.env['purchase.order'].create(po_vals)
    
            # ✅ Siempre crear una NUEVA línea, sin buscar existentes
            po_line_vals = self.env['purchase.order.line'].with_context(
                custom_po_description=line.description or line.name
            )._prepare_purchase_order_line(
                line.product_id,
                line.quantity,
                line.product_uom_id,
                line.company_id,
                seller,
                purchase_order,
            )
            new_po_line = self.env['purchase.order.line'].create(po_line_vals)
            line.purchase_order_line_id = new_po_line.id
    
            # Actualizar origin
            new_origin = {self.name}
            origins = set((purchase_order.origin or '').split(', ')) - {''}
            if not new_origin.issubset(origins):
                origins.update(new_origin)
                purchase_order.write({'origin': ', '.join(sorted(origins))})