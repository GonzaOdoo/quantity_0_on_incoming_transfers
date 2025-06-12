import io
import xlsxwriter
import base64
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)
class PendingPurchases(models.TransientModel):
    _name ='purchase.order.pending'
    _description = 'Pedidos Pendientes'

    name = fields.Char('Nombre',compute='_compute_name')
    partner_id = fields.Many2one('res.partner',string='Proveedor')
    date_start = fields.Date('Desde')
    date_end = fields.Date('Hasta')
    order_list = fields.Many2many('purchase.order.line',string='Líneas pendientes',compute='_compute_order_list')
    

    @api.depends('partner_id')
    def _compute_name(self):
        for record in self:
            if record.partner_id:
                record.name = f"Reporte pendientes: {record.partner_id.name}"
            else:
                record.name = "Reporte pendientes"

    
    @api.depends('partner_id', 'date_start', 'date_end')
    def _compute_order_list(self):
        for record in self:
            domain = [
                ('order_id.state', 'in', ['purchase', 'done']),
            ]
            
            if record.partner_id:
                domain.append(('order_id.partner_id', '=', record.partner_id.id))
            
            if record.date_start:
                domain.append(('date_approve', '>=', record.date_start))
            if record.date_end:
                domain.append(('date_approve', '<=', record.date_end))
            lines = self.env['purchase.order.line'].search(domain, order='date_approve asc')
            pending_lines = lines.filtered(lambda l: l.qty_received < l.product_qty)
            record.order_list = [Command.clear(), Command.set(pending_lines.ids)]


    def generate_excel_report(self):
        self.ensure_one()
        
        # Crear el archivo en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Compras Pendientes')
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        
        # Cabeceras
        headers = [
            'Fecha Aprobación',
            'Orden de Compra',
            'Producto',
            'Código Origen',
            'Presentación',
            'Proveedor',
            'Precio Unitario',
            'Cantidad Pedida',
            'Cantidad Recibida',
            'Cantidad Pendiente',
            'Subtotal',
            'Total'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos
        row = 1
        for line in self.order_list.sorted(key=lambda r: r.date_approve or ''):
            subtotal = line.price_unit * line.pending_amount
            total = subtotal * (1 + sum(tax.amount for tax in line.taxes_id) / 100)     
            
            worksheet.write(row, 0, line.date_approve, date_format)
            worksheet.write(row, 1, line.order_id.name or '')
            worksheet.write(row, 2, line.product_id.display_name or '')
            worksheet.write(row, 3, line.product_origin_code or '')
            worksheet.write(row, 4, line.product_presentation or '')
            worksheet.write(row, 5, line.partner_id.name or '')
            worksheet.write(row, 6, line.price_unit, money_format)
            worksheet.write(row, 7, line.product_uom_qty)
            worksheet.write(row, 8, line.qty_received)
            worksheet.write(row, 9, line.pending_amount)
            worksheet.write(row, 10, subtotal, money_format)
            worksheet.write(row, 11, total, money_format)
            row += 1
        
        # Ajustar ancho de columnas
        worksheet.set_column('A:A', 15)  # Fecha
        worksheet.set_column('B:B', 15)  # OC
        worksheet.set_column('C:C', 30)  # Producto
        worksheet.set_column('D:D', 15)  # Código
        worksheet.set_column('E:E', 20)  # Presentación
        worksheet.set_column('F:F', 30)  # Proveedor
        worksheet.set_column('G:L', 15)  # Valores numéricos
        
        # Totales
        if row > 1:
            total_pendiente = sum(line.pending_amount for line in self.order_list)
            total_subtotal = sum(line.price_unit * line.pending_amount for line in self.order_list)
            total_total = sum((line.price_unit * line.pending_amount) * (1 + sum(tax.amount for tax in line.taxes_id) / 100) for line in self.order_list )
            worksheet.write(row, 9, total_pendiente)
            worksheet.write(row, 10, total_subtotal, money_format)
            worksheet.write(row, 11, total_total, money_format)
            worksheet.write(row, 0, 'TOTALES', header_format)
        
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.getvalue())
        output.close()
        
        # Crear adjunto temporal para descarga
        attachment = self.env['ir.attachment'].create({
            'name': 'Reporte_Pedidos_Pendientes_{}.xlsx'.format(
                datetime.now().strftime('%Y%m%d')),
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
            'public': True  # Para permitir la descarga sin autenticación
        })
        
        # Retornar acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

class OrderLine(models.Model):
    _inherit='purchase.order.line'

    pending_amount = fields.Float('Cantidad pendiente',compute='_compute_pending_amount')
    product_origin_code = fields.Char('Cod. Origen',related='product_id.product_tmpl_id.x_studio_codigo_de_origen')
    product_presentation = fields.Char('Presentación',related='product_id.product_tmpl_id.presentation')

    @api.depends('product_qty','qty_received')
    def _compute_pending_amount(self):
        for line in self:
            line.pending_amount = line.product_qty - line.qty_received
            