# -*- coding: utf-8 -*-

import base64
import io

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_is_zero


GROUP_XMLID = (
    "l7_consignacion_price_report."
    "group_consignacion_price_report"
)

PRICELIST_NAME = "PRECIO MAYOREO"

CONSIGNACION_LOCATION_COMPLETE_NAME = (
    "Ubicaciones virtuales/Traspaso Consignaciones"
)

CONSIGNACION_LOCATION_NAME = "Traspaso Consignaciones"


class L7ConsignacionPriceReportWizard(models.TransientModel):
    _name = "l7.consignacion.price.report.wizard"
    _description = "Lista de precios de consignacion"
    _transient_max_hours = 2

    consignacion_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Ubicacion de consignacion",
        default=lambda self: self._default_consignacion_location(),
        readonly=True,
    )

    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Lista de precios",
        default=lambda self: self._default_pricelist(),
        readonly=True,
    )

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Salida a consignacion",
        required=True,
    )

    company_id = fields.Many2one(
        related="picking_id.company_id",
        string="Empresa",
        readonly=True,
    )

    partner_id = fields.Many2one(
        related="picking_id.partner_id",
        string="Cliente / Consignatario",
        readonly=True,
    )

    origin = fields.Char(
        related="picking_id.origin",
        string="Origen / Referencia",
        readonly=True,
    )

    state = fields.Selection(
        related="picking_id.state",
        string="Estado",
        readonly=True,
    )

    scheduled_date = fields.Datetime(
        related="picking_id.scheduled_date",
        string="Fecha programada",
        readonly=True,
    )

    date_done = fields.Datetime(
        related="picking_id.date_done",
        string="Fecha realizada",
        readonly=True,
    )

    file_data = fields.Binary(
        string="Archivo Excel",
        readonly=True,
    )

    file_name = fields.Char(
        string="Nombre archivo",
        readonly=True,
    )

    # ==============================================================================================
    # CONFIGURACION
    # ==============================================================================================

    @api.model
    def _find_consignacion_location(self):
        Location = self.env["stock.location"].sudo()

        location = Location.search(
            [
                (
                    "complete_name",
                    "=",
                    CONSIGNACION_LOCATION_COMPLETE_NAME,
                ),
                ("usage", "=", "transit"),
            ],
            limit=1,
        )

        if not location:
            location = Location.search(
                [
                    ("name", "=", CONSIGNACION_LOCATION_NAME),
                    ("usage", "=", "transit"),
                ],
                limit=1,
            )

        return location

    @api.model
    def _default_consignacion_location(self):
        return self._find_consignacion_location().id

    @api.model
    def _find_pricelist(self):
        Pricelist = self.env["product.pricelist"].sudo()

        # Lista exacta detectada en TEST:
        # ID 33 - PRECIO MAYOREO - GLOBAL
        #
        # No fijamos el ID para que el modulo pueda migrarse a PROD.
        pricelist = Pricelist.search(
            [
                ("name", "=", PRICELIST_NAME),
                ("company_id", "=", False),
                ("active", "=", True),
            ],
            limit=1,
        )

        if not pricelist:
            pricelist = Pricelist.search(
                [
                    ("name", "=", PRICELIST_NAME),
                    ("active", "=", True),
                ],
                limit=1,
            )

        return pricelist

    @api.model
    def _default_pricelist(self):
        return self._find_pricelist().id

    # ==============================================================================================
    # SEGURIDAD
    # ==============================================================================================

    def _check_report_access(self):
        if not self.env.user.has_group(GROUP_XMLID):
            raise AccessError(
                _(
                    "No tienes permiso para generar la "
                    "Lista de consignacion."
                )
            )

    # ==============================================================================================
    # VALIDACIONES
    # ==============================================================================================

    def _validate_configuration(self):
        self.ensure_one()

        self._check_report_access()

        location = self._find_consignacion_location()

        if not location:
            raise UserError(
                _(
                    "No se encontro la ubicacion "
                    "'Ubicaciones virtuales/Traspaso Consignaciones'."
                )
            )

        pricelist = self._find_pricelist()

        if not pricelist:
            raise UserError(
                _(
                    "No se encontro la lista exacta "
                    "'PRECIO MAYOREO'."
                )
            )

        if not self.picking_id:
            raise UserError(
                _("Debes seleccionar una salida a consignacion.")
            )

        picking = self.picking_id

        if picking.state == "cancel":
            raise UserError(
                _("No se puede generar el reporte de una salida cancelada.")
            )

        if picking.location_dest_id.id != location.id:
            raise UserError(
                _(
                    "El movimiento seleccionado no es una salida "
                    "a consignacion."
                )
            )

        return location, pricelist

    # ==============================================================================================
    # PRECIOS
    # ==============================================================================================

    def _get_price_date(self):
        """
        El usuario solicita la lista de precios vigente al momento
        de generar el reporte, aunque la consignacion sea historica.
        """
        return fields.Date.context_today(self)

    def _get_pricelist_price(
        self,
        pricelist,
        product,
        quantity,
        uom,
        price_date,
    ):
        pricelist = pricelist.sudo()

        if hasattr(pricelist, "_get_product_price"):
            try:
                return pricelist._get_product_price(
                    product,
                    quantity,
                    uom=uom,
                    date=price_date,
                )
            except TypeError:
                try:
                    return pricelist._get_product_price(
                        product,
                        quantity,
                        uom_id=uom.id,
                        date=price_date,
                    )
                except TypeError:
                    return pricelist._get_product_price(
                        product,
                        quantity,
                    )

        if hasattr(pricelist, "get_product_price"):
            try:
                return pricelist.get_product_price(
                    product,
                    quantity,
                    False,
                    date=price_date,
                    uom_id=uom.id,
                )
            except TypeError:
                return pricelist.get_product_price(
                    product,
                    quantity,
                    False,
                )

        result = pricelist.price_get(
            product.id,
            quantity,
            False,
        )

        return result.get(pricelist.id, 0.0)

    # ==============================================================================================
    # LINEAS DEL REPORTE
    # ==============================================================================================

    def _get_report_lines(self, picking, pricelist):
        aggregated = {}

        moves = picking.move_ids_without_package.filtered(
            lambda move: move.state != "cancel"
        )

        for move in moves:
            product = move.product_id
            uom = move.product_uom

            # Salida realizada:
            # cantidad realmente entregada.
            if picking.state == "done":
                quantity = sum(
                    move.move_line_ids.mapped("qty_done")
                )

            # Salida pendiente:
            # cantidad programada.
            else:
                quantity = move.product_uom_qty

            if float_is_zero(
                quantity,
                precision_rounding=uom.rounding,
            ):
                continue

            key = (
                product.id,
                uom.id,
            )

            if key not in aggregated:
                aggregated[key] = {
                    "product": product,
                    "uom": uom,
                    "quantity": 0.0,
                }

            aggregated[key]["quantity"] += quantity

        price_date = self._get_price_date()

        rows = []

        for values in aggregated.values():
            product = values["product"]
            uom = values["uom"]
            quantity = values["quantity"]

            wholesale_price = self._get_pricelist_price(
                pricelist=pricelist,
                product=product,
                quantity=quantity,
                uom=uom,
                price_date=price_date,
            )

            employee_price = wholesale_price * 0.97

            total_wholesale = wholesale_price * quantity
            total_employee = employee_price * quantity

            product_name = product.with_context(
                display_default_code=False
            ).display_name

            rows.append({
                "sku": product.default_code or "",
                "barcode": product.barcode or "",
                "product": product_name,
                "quantity": quantity,
                "uom": uom.name or "",
                "wholesale_price": wholesale_price,
                "employee_price": employee_price,
                "total_wholesale": total_wholesale,
                "total_employee": total_employee,
            })

        rows.sort(
            key=lambda row: (
                row["sku"] or "",
                row["product"] or "",
            )
        )

        return rows

    # ==============================================================================================
    # XLSX
    # ==============================================================================================

    def action_generate_xlsx(self):
        self.ensure_one()

        location, pricelist = self._validate_configuration()

        picking = self.picking_id

        rows = self._get_report_lines(
            picking=picking,
            pricelist=pricelist,
        )

        if not rows:
            raise UserError(
                _(
                    "La salida seleccionada no contiene productos "
                    "con cantidad mayor a cero."
                )
            )

        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(
            output,
            {
                "in_memory": True,
            },
        )

        worksheet = workbook.add_worksheet("Consignacion")

        # ------------------------------------------------------------------------------------------
        # FORMATOS
        # ------------------------------------------------------------------------------------------

        title_format = workbook.add_format({
            "bold": True,
            "font_size": 16,
            "align": "center",
            "valign": "vcenter",
        })

        label_format = workbook.add_format({
            "bold": True,
        })

        header_format = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
        })

        text_format = workbook.add_format({
            "border": 1,
            "valign": "top",
        })

        qty_format = workbook.add_format({
            "border": 1,
            "num_format": "#,##0.00",
            "align": "right",
        })

        money_format = workbook.add_format({
            "border": 1,
            "num_format": '$#,##0.00',
            "align": "right",
        })

        total_label_format = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "right",
        })

        total_money_format = workbook.add_format({
            "bold": True,
            "border": 1,
            "num_format": '$#,##0.00',
            "align": "right",
        })

        note_format = workbook.add_format({
            "italic": True,
        })

        # ------------------------------------------------------------------------------------------
        # COLUMNAS
        # ------------------------------------------------------------------------------------------

        worksheet.set_column("A:A", 18)
        worksheet.set_column("B:B", 18)
        worksheet.set_column("C:C", 55)
        worksheet.set_column("D:D", 13)
        worksheet.set_column("E:E", 14)
        worksheet.set_column("F:I", 19)

        # ------------------------------------------------------------------------------------------
        # CABECERA
        # ------------------------------------------------------------------------------------------

        worksheet.merge_range(
            "A1:I1",
            "LISTA DE CONSIGNACION",
            title_format,
        )

        worksheet.write("A3", "Empresa:", label_format)
        worksheet.write(
            "B3",
            picking.company_id.name or "",
        )

        worksheet.write("A4", "Salida:", label_format)
        worksheet.write(
            "B4",
            picking.name or "",
        )

        worksheet.write(
            "A5",
            "Origen / Referencia:",
            label_format,
        )
        worksheet.write(
            "B5",
            picking.origin or "",
        )

        worksheet.write(
            "A6",
            "Cliente / Consignatario:",
            label_format,
        )
        worksheet.write(
            "B6",
            picking.partner_id.display_name
            if picking.partner_id
            else "",
        )

        worksheet.write(
            "A7",
            "Estado:",
            label_format,
        )

        state_label = dict(
            picking._fields["state"].selection
        ).get(
            picking.state,
            picking.state,
        )

        worksheet.write(
            "B7",
            state_label,
        )

        worksheet.write(
            "E3",
            "Destino:",
            label_format,
        )
        worksheet.write(
            "F3",
            location.complete_name or "",
        )

        worksheet.write(
            "E4",
            "Lista de precios:",
            label_format,
        )
        worksheet.write(
            "F4",
            pricelist.name or "",
        )

        worksheet.write(
            "E5",
            "Moneda:",
            label_format,
        )
        worksheet.write(
            "F5",
            pricelist.currency_id.name or "",
        )

        price_date = self._get_price_date()

        worksheet.write(
            "E6",
            "Fecha de precios:",
            label_format,
        )
        worksheet.write(
            "F6",
            price_date.strftime("%d/%m/%Y"),
        )

        worksheet.write(
            "E7",
            "Precio empleado:",
            label_format,
        )
        worksheet.write(
            "F7",
            "PRECIO MAYOREO - 3%",
        )

        worksheet.merge_range(
            "A9:I9",
            (
                "Los precios corresponden a la lista "
                "PRECIO MAYOREO vigente al generar este archivo."
            ),
            note_format,
        )

        # ------------------------------------------------------------------------------------------
        # TABLA
        # ------------------------------------------------------------------------------------------

        header_row = 10

        headers = [
            "SKU",
            "Codigo de barras",
            "Producto",
            "Cantidad",
            "UDM",
            "Precio Mayoreo",
            "Precio Empleado -3%",
            "Total Mayoreo",
            "Total Empleado",
        ]

        for col, header in enumerate(headers):
            worksheet.write(
                header_row,
                col,
                header,
                header_format,
            )

        first_data_row = header_row + 1

        total_wholesale = 0.0
        total_employee = 0.0

        for index, row in enumerate(rows):
            excel_row = first_data_row + index

            worksheet.write(
                excel_row,
                0,
                row["sku"],
                text_format,
            )

            worksheet.write(
                excel_row,
                1,
                row["barcode"],
                text_format,
            )

            worksheet.write(
                excel_row,
                2,
                row["product"],
                text_format,
            )

            worksheet.write_number(
                excel_row,
                3,
                row["quantity"],
                qty_format,
            )

            worksheet.write(
                excel_row,
                4,
                row["uom"],
                text_format,
            )

            worksheet.write_number(
                excel_row,
                5,
                row["wholesale_price"],
                money_format,
            )

            worksheet.write_number(
                excel_row,
                6,
                row["employee_price"],
                money_format,
            )

            worksheet.write_number(
                excel_row,
                7,
                row["total_wholesale"],
                money_format,
            )

            worksheet.write_number(
                excel_row,
                8,
                row["total_employee"],
                money_format,
            )

            total_wholesale += row["total_wholesale"]
            total_employee += row["total_employee"]

        last_data_row = first_data_row + len(rows) - 1
        total_row = last_data_row + 1

        worksheet.merge_range(
            total_row,
            0,
            total_row,
            6,
            "TOTALES",
            total_label_format,
        )

        worksheet.write_number(
            total_row,
            7,
            total_wholesale,
            total_money_format,
        )

        worksheet.write_number(
            total_row,
            8,
            total_employee,
            total_money_format,
        )

        worksheet.autofilter(
            header_row,
            0,
            last_data_row,
            8,
        )

        worksheet.freeze_panes(
            first_data_row,
            0,
        )

        workbook.close()

        output.seek(0)

        safe_picking_name = (
            (picking.name or "consignacion")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )

        filename = (
            "Lista_Consignacion_%s.xlsx"
            % safe_picking_name
        )

        self.write({
            "file_data": base64.b64encode(output.read()),
            "file_name": filename,
            "pricelist_id": pricelist.id,
            "consignacion_location_id": location.id,
        })

        output.close()

        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content?"
                "model=l7.consignacion.price.report.wizard"
                "&id=%s"
                "&field=file_data"
                "&filename_field=file_name"
                "&download=true"
            ) % self.id,
            "target": "self",
        }
