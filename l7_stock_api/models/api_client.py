import hashlib
import secrets

from odoo import _, fields, models


class L7StockApiClient(models.Model):
    _name = "l7.stock.api.client"
    _description = "Cliente API de existencias L7"
    _order = "name"

    name = fields.Char(
        string="Proveedor / Integracion",
        required=True,
        index=True,
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Empresa autorizada",
        required=True,
        ondelete="restrict",
        index=True,
        help=(
            "La API solamente devolvera existencias correspondientes "
            "a esta empresa. El consumidor no puede cambiarla mediante "
            "parametros de la peticion."
        ),
    )

    token_hash = fields.Char(
        string="Hash del token",
        readonly=True,
        copy=False,
        index=True,
    )

    token_last4 = fields.Char(
        string="Ultimos caracteres",
        readonly=True,
        copy=False,
    )

    requests_per_minute = fields.Integer(
        string="Peticiones por minuto",
        default=60,
        required=True,
        help="Limite de llamadas permitidas por minuto para este token.",
    )

    max_page_size = fields.Integer(
        string="Maximo por pagina",
        default=1000,
        required=True,
        help="Numero maximo de renglones devueltos por llamada.",
    )

    last_used_at = fields.Datetime(
        string="Ultimo uso",
        readonly=True,
        copy=False,
    )

    notes = fields.Text(
        string="Notas",
    )

    _sql_constraints = [
        (
            "l7_stock_api_token_hash_unique",
            "unique(token_hash)",
            "El token ya esta asignado a otro cliente API.",
        ),
        (
            "l7_stock_api_requests_positive",
            "CHECK(requests_per_minute > 0)",
            "Las peticiones por minuto deben ser mayores a cero.",
        ),
        (
            "l7_stock_api_page_size_positive",
            "CHECK(max_page_size > 0)",
            "El maximo por pagina debe ser mayor a cero.",
        ),
    ]

    def action_generate_token(self):
        self.ensure_one()

        token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        self.write(
            {
                "token_hash": token_hash,
                "token_last4": token[-4:],
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("TOKEN API GENERADO"),
                "message": _(
                    "Copia este token ahora. "
                    "Por seguridad no volvera a mostrarse.\n\n%s"
                )
                % token,
                "type": "warning",
                "sticky": True,
            },
        }

    def action_revoke_token(self):
        self.ensure_one()

        self.write(
            {
                "token_hash": False,
                "token_last4": False,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Token revocado"),
                "message": _("El token anterior dejo de ser valido."),
                "type": "success",
                "sticky": False,
            },
        }


class L7StockApiLog(models.Model):
    _name = "l7.stock.api.log"
    _description = "Bitacora L7 Stock API"
    _order = "requested_at desc, id desc"

    client_id = fields.Many2one(
        "l7.stock.api.client",
        string="Cliente API",
        required=True,
        ondelete="cascade",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        related="client_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    requested_at = fields.Datetime(
        string="Fecha",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )

    remote_ip = fields.Char(
        string="IP",
        readonly=True,
    )

    method = fields.Char(
        string="Metodo",
        readonly=True,
    )

    path = fields.Char(
        string="Ruta",
        readonly=True,
    )

    query_string = fields.Char(
        string="Parametros",
        readonly=True,
    )

    status_code = fields.Integer(
        string="HTTP",
        readonly=True,
    )

    result_count = fields.Integer(
        string="Resultados",
        readonly=True,
    )

    duration_ms = fields.Integer(
        string="Duracion ms",
        readonly=True,
    )

    user_agent = fields.Char(
        string="User Agent",
        readonly=True,
    )
