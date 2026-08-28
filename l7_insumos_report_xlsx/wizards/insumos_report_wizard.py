from odoo import _, fields, models
from odoo.exceptions import UserError


class L7InsumosReportWizard(models.TransientModel):
    _name = "l7.insumos.report.wizard"
    _description = "Generar historico de insumos"

    safety_percent = fields.Float(
        string="Colchon de seguridad (%)",
        default=10.0,
        required=True,
    )

    def _get_full_history_period(self):
        """
        Obtiene el periodo completo y confiable del almacen
        CEDIS INSUMOS antes de crear el registro del reporte.

        Tipos de operacion:
        731 = Recepciones
        732 = Ordenes de entrega
        735 = Traslados internos
        740 = Ordenes de PdV
        736 = Devoluciones
        """
        Move = self.env["stock.move"].sudo()

        moves = Move.search(
            [
                ("company_id", "=", 1),
                ("state", "=", "done"),
                (
                    "picking_type_id",
                    "in",
                    [731, 732, 735, 740, 736],
                ),
            ],
            order="date asc, id asc",
        )

        if not moves:
            raise UserError(
                _(
                    "No existen movimientos terminados "
                    "en el almacen CEDIS INSUMOS."
                )
            )

        date_from = fields.Date.to_date(
            moves[0].date
        )

        date_to = fields.Date.context_today(
            self
        )

        return date_from, date_to

    def action_generate(self):
        self.ensure_one()

        # --------------------------------------------------------------
        # Obtener fechas ANTES de crear el reporte.
        # Esto permite mantener compatibilidad aunque date_from/date_to
        # sigan marcados como obligatorios en la estructura existente.
        # --------------------------------------------------------------

        date_from, date_to = (
            self._get_full_history_period()
        )

        report = self.env["l7.insumos.report"].create({
            "date_from": date_from,
            "date_to": date_to,
            "safety_percent": self.safety_percent,
            "requested_by": self.env.user.id,
            "requested_at": fields.Datetime.now(),
        })

        report.generate_report()

        return {
            "type": "ir.actions.act_window",
            "name": _("Reporte historico de insumos"),
            "res_model": "l7.insumos.report",
            "res_id": report.id,
            "view_mode": "form",
            "target": "current",
        }
