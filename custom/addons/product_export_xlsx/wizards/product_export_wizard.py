from odoo import fields, models, _
from odoo.exceptions import UserError


class ProductExportXlsxWizard(models.TransientModel):
    _name = "product.export.xlsx.wizard"
    _description = "Generar Excel de Productos"

    def action_generate(self):
        self.ensure_one()

        Export = self.env[
            "product.export.xlsx"
        ]

        running = Export.search(
            [
                (
                    "state",
                    "in",
                    [
                        "pending",
                        "processing",
                    ],
                ),
            ],
            limit=1,
        )

        if running:
            raise UserError(
                _(
                    "Ya existe una exportacion pendiente o en proceso."
                )
            )

        job = Export.create({
            "requested_by": self.env.user.id,
            "requested_at": fields.Datetime.now(),
            "state": "pending",
            "progress_message": (
                "Pendiente de procesamiento"
            ),
        })

        cron = self.env.ref(
            "product_export_xlsx.ir_cron_product_export",
            raise_if_not_found=False,
        )

        if cron:
            cron.sudo().write({
                "nextcall": fields.Datetime.now(),
            })

        return {
            "type": "ir.actions.act_window",
            "name": _("Exportacion de productos"),
            "res_model": "product.export.xlsx",
            "view_mode": "form",
            "res_id": job.id,
            "target": "current",
        }
