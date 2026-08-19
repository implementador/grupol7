import base64
import logging
import os
import tempfile
import traceback
from datetime import date, datetime

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class ProductExportXlsx(models.Model):
    _name = "product.export.xlsx"
    _description = "Exportacion XLSX de Productos"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reporte",
        required=True,
        readonly=True,
        default=lambda self: self._default_name(),
    )

    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("processing", "Procesando"),
            ("done", "Listo"),
            ("error", "Error"),
        ],
        string="Estado",
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )

    requested_by = fields.Many2one(
        "res.users",
        string="Solicitado por",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )

    requested_at = fields.Datetime(
        string="Solicitado",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )

    started_at = fields.Datetime(
        string="Inicio",
        readonly=True,
    )

    finished_at = fields.Datetime(
        string="Fin",
        readonly=True,
    )

    product_count = fields.Integer(
        string="Productos exportados",
        readonly=True,
    )

    user_column_count = fields.Integer(
        string="Columnas Productos",
        readonly=True,
    )

    technical_column_count = fields.Integer(
        string="Columnas tecnicas",
        readonly=True,
    )

    studio_product_count = fields.Integer(
        string="Studio product.product",
        readonly=True,
    )

    studio_template_count = fields.Integer(
        string="Studio product.template",
        readonly=True,
    )

    missing_count = fields.Integer(
        string="Productos faltantes",
        readonly=True,
    )

    file_size_mb = fields.Float(
        string="Tamano MB",
        digits=(16, 2),
        readonly=True,
    )

    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo XLSX",
        readonly=True,
        ondelete="set null",
    )

    progress_message = fields.Char(
        string="Progreso",
        readonly=True,
    )

    error_message = fields.Text(
        string="Error",
        readonly=True,
    )

    @api.model
    def _default_name(self):
        now = fields.Datetime.context_timestamp(
            self,
            fields.Datetime.now(),
        )
        return "Productos %s" % now.strftime("%Y-%m-%d %H:%M:%S")

    def action_download(self):
        self.ensure_one()

        if self.state != "done" or not self.attachment_id:
            raise UserError(_("El reporte aun no esta listo."))

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % self.attachment_id.id,
            "target": "self",
        }

    def action_retry(self):
        self.ensure_one()

        if self.state != "error":
            raise UserError(_("Solo puede reintentarse un reporte con error."))

        other = self.search(
            [
                ("id", "!=", self.id),
                ("state", "in", ["pending", "processing"]),
            ],
            limit=1,
        )

        if other:
            raise UserError(
                _("Ya existe otra exportacion pendiente o en proceso.")
            )

        self.write({
            "state": "pending",
            "started_at": False,
            "finished_at": False,
            "error_message": False,
            "progress_message": "Pendiente de procesamiento",
            "missing_count": 0,
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
            "type": "ir.actions.client",
            "tag": "reload",
        }

    @api.model
    def _cron_process_pending(self):
        job = self.sudo().search(
            [("state", "=", "pending")],
            order="create_date asc, id asc",
            limit=1,
        )

        if not job:
            return

        try:
            with self.env.cr.savepoint():
                job._generate_xlsx()

        except Exception as exc:
            _logger.exception(
                "Error en exportacion XLSX de productos ID %s",
                job.id,
            )

            job.write({
                "state": "error",
                "finished_at": fields.Datetime.now(),
                "progress_message": "Error",
                "error_message": "%s\n\n%s" % (
                    exc,
                    traceback.format_exc(),
                ),
            })

    def _get_table_columns(self, table_name):
        self.env.cr.execute(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            [table_name],
        )

        return [
            {
                "name": column_name,
                "data_type": data_type,
                "udt_name": udt_name,
            }
            for column_name, data_type, udt_name
            in self.env.cr.fetchall()
            if udt_name != "bytea"
        ]

    def _clean_text(self, value):
        if value is None:
            return ""

        text = str(value)

        if len(text) > 32700:
            text = text[:32700]

        return text

    def _selection_label(self, field, value):
        if value in (None, False, ""):
            return ""

        try:
            selection = dict(
                field._description_selection(self.env)
            )

            return selection.get(
                value,
                value,
            )

        except Exception:
            return value

    def _normalize_value(self, field, value):
        if field and field.type == "boolean":
            return "SI" if bool(value) else "NO"

        if value in (None, False):
            return ""

        if field and field.type == "selection":
            return self._selection_label(
                field,
                value,
            )

        if isinstance(value, tuple) and len(value) >= 2:
            return "%s | %s" % (
                value[0],
                value[1],
            )

        if isinstance(value, list):
            return ",".join(
                str(x)
                for x in value
            )

        return value

    def _write_value(
        self,
        sheet,
        row,
        col,
        value,
        formats,
        field=None,
        field_name=None,
        humanize=False,
    ):
        if humanize:
            value = self._normalize_value(
                field,
                value,
            )

        elif field and field.type == "boolean":
            value = "SI" if bool(value) else "NO"

        if value is None or value is False:
            return

        if isinstance(value, bool):
            sheet.write(
                row,
                col,
                "SI" if value else "NO",
                formats["text"],
            )
            return

        if isinstance(value, int):
            sheet.write_number(
                row,
                col,
                value,
                formats["integer"],
            )
            return

        if isinstance(value, float):
            fmt = (
                formats["money"]
                if field_name in ("list_price", "standard_price")
                else formats["decimal"]
            )

            sheet.write_number(
                row,
                col,
                value,
                fmt,
            )
            return

        if isinstance(value, (datetime, date)):
            sheet.write(
                row,
                col,
                str(value),
                formats["text"],
            )
            return

        sheet.write(
            row,
            col,
            self._clean_text(value),
            formats["text"],
        )

    def _generate_xlsx(self):
        self.ensure_one()

        Product = (
            self.env["product.product"]
            .sudo()
            .with_context(active_test=False)
        )

        Template = (
            self.env["product.template"]
            .sudo()
            .with_context(active_test=False)
        )

        self.write({
            "state": "processing",
            "started_at": fields.Datetime.now(),
            "finished_at": False,
            "error_message": False,
            "progress_message": "Preparando exportacion",
        })

        product_ids = Product.search(
            [],
            order="id",
        ).ids

        total = len(product_ids)

        if not total:
            raise UserError(
                _("No existen productos para exportar.")
            )

        pp_columns = self._get_table_columns(
            "product_product"
        )

        pt_columns = self._get_table_columns(
            "product_template"
        )

        friendly_candidates = [
            "id",
            "default_code",
            "name",
            "barcode",
            "active",
            "categ_id",
            "detailed_type",
            "sale_ok",
            "purchase_ok",
            "available_in_pos",
            "pos_categ_id",
            "list_price",
            "standard_price",
            "uom_id",
            "uom_po_id",
            "company_id",
            "branch_id",
            "qty_available",
            "free_qty",
            "incoming_qty",
            "outgoing_qty",
            "virtual_available",
            "hs_code",
            "country_of_origin",
            "l10n_mx_edi_tariff_fraction_id",
            "create_date",
            "write_date",
        ]

        friendly_fields = [
            f
            for f in friendly_candidates
            if f == "id" or f in Product._fields
        ]

        studio_product_fields = sorted([
            name
            for name, field in Product._fields.items()
            if (
                name.startswith("x_studio_")
                and getattr(field, "store", False)
                and field.type not in (
                    "binary",
                    "one2many",
                    "many2many",
                )
                and name not in friendly_fields
            )
        ])

        studio_template_fields = sorted([
            name
            for name, field in Template._fields.items()
            if (
                name.startswith("x_studio_")
                and getattr(field, "store", False)
                and field.type not in (
                    "binary",
                    "one2many",
                    "many2many",
                )
                and name not in friendly_fields
                and name not in studio_product_fields
            )
        ])

        computed_fields = [
            f
            for f in [
                "display_name",
                "list_price",
                "standard_price",
                "qty_available",
                "free_qty",
                "virtual_available",
                "incoming_qty",
                "outgoing_qty",
            ]
            if f in Product._fields
        ]

        friendly_labels = {
            "id": "ID Producto",
            "default_code": "Referencia interna",
            "name": "Nombre",
            "barcode": "Codigo de barras",
            "active": "Activo",
            "categ_id": "Categoria",
            "detailed_type": "Tipo de producto",
            "sale_ok": "Disponible para venta",
            "purchase_ok": "Disponible para compra",
            "available_in_pos": "Disponible en Punto de Venta",
            "pos_categ_id": "Categoria Punto de Venta",
            "list_price": "Precio de venta",
            "standard_price": "Costo",
            "uom_id": "Unidad de medida",
            "uom_po_id": "Unidad de compra",
            "company_id": "Empresa",
            "branch_id": "Sucursal",
            "qty_available": "Existencia",
            "free_qty": "Existencia disponible",
            "incoming_qty": "Entradas pendientes",
            "outgoing_qty": "Salidas pendientes",
            "virtual_available": "Existencia prevista",
            "hs_code": "Codigo HS",
            "country_of_origin": "Pais de origen",
            "l10n_mx_edi_tariff_fraction_id": "Fraccion arancelaria",
            "create_date": "Fecha de creacion",
            "write_date": "Ultima modificacion",
        }

        user_columns = []

        for fname in friendly_fields:
            if fname == "id":
                user_columns.append({
                    "source": "product",
                    "field": "id",
                    "label": "ID Producto",
                    "field_object": False,
                })
                continue

            field = Product._fields[fname]

            user_columns.append({
                "source": "product",
                "field": fname,
                "label": friendly_labels.get(
                    fname,
                    field.string or fname,
                ),
                "field_object": field,
            })

        for fname in studio_product_fields:
            field = Product._fields[fname]

            user_columns.append({
                "source": "product",
                "field": fname,
                "label": field.string or fname,
                "field_object": field,
            })

        for fname in studio_template_fields:
            field = Template._fields[fname]

            user_columns.append({
                "source": "template",
                "field": fname,
                "label": field.string or fname,
                "field_object": field,
            })

        def field_label(Model, fname):
            field = Model._fields.get(fname)

            if field:
                return field.string or fname

            return fname

        all_headers = [{
            "technical": "PRODUCT_ID",
            "label": "ID Producto",
        }]

        for item in pp_columns:
            fname = item["name"]

            all_headers.append({
                "technical": "product.product.%s" % fname,
                "label": "%s [%s]" % (
                    field_label(Product, fname),
                    fname,
                ),
            })

        for item in pt_columns:
            fname = item["name"]

            all_headers.append({
                "technical": "product.template.%s" % fname,
                "label": "%s [%s]" % (
                    field_label(Template, fname),
                    fname,
                ),
            })

        for fname in computed_fields:
            all_headers.append({
                "technical": "calculado.%s" % fname,
                "label": "%s [%s]" % (
                    Product._fields[fname].string or fname,
                    fname,
                ),
            })

        fd, filepath = tempfile.mkstemp(
            prefix="productos_export_",
            suffix=".xlsx",
        )
        os.close(fd)

        workbook = None

        try:
            workbook = xlsxwriter.Workbook(
                filepath,
                {
                    "constant_memory": True,
                },
            )

            user_sheet = workbook.add_worksheet(
                "Productos"
            )

            all_sheet = workbook.add_worksheet(
                "Todos los campos"
            )

            dict_sheet = workbook.add_worksheet(
                "Diccionario campos"
            )

            summary_sheet = workbook.add_worksheet(
                "Resumen"
            )

            formats = {
                "header": workbook.add_format({
                    "bold": True,
                    "border": 1,
                    "text_wrap": True,
                    "valign": "top",
                }),
                "text": workbook.add_format({
                    "valign": "top",
                }),
                "integer": workbook.add_format({
                    "num_format": "0",
                }),
                "decimal": workbook.add_format({
                    "num_format": "#,##0.00",
                }),
                "money": workbook.add_format({
                    "num_format": "$#,##0.00",
                }),
            }

            for col, info in enumerate(user_columns):
                user_sheet.write(
                    0,
                    col,
                    info["label"],
                    formats["header"],
                )

            for col, info in enumerate(user_columns):
                user_sheet.write(
                    1,
                    col,
                    info["field"],
                    formats["header"],
                )

            user_sheet.freeze_panes(
                2,
                0,
            )

            user_sheet.autofilter(
                1,
                0,
                1,
                len(user_columns) - 1,
            )

            for col, info in enumerate(all_headers):
                all_sheet.write(
                    0,
                    col,
                    info["label"],
                    formats["header"],
                )

            for col, info in enumerate(all_headers):
                all_sheet.write(
                    1,
                    col,
                    info["technical"],
                    formats["header"],
                )

            all_sheet.freeze_panes(
                2,
                0,
            )

            all_sheet.autofilter(
                1,
                0,
                1,
                len(all_headers) - 1,
            )

            pp_select = [
                'pp."%s"' % item["name"]
                for item in pp_columns
            ]

            pt_select = [
                'pt."%s"' % item["name"]
                for item in pt_columns
            ]

            select_parts = [
                "pp.id AS product_id"
            ]

            select_parts += pp_select
            select_parts += pt_select

            sql_batch = """
                SELECT
                    %s
                FROM product_product pp
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id
                WHERE pp.id IN %%s
                ORDER BY pp.id
            """ % ",\n".join(select_parts)

            product_read_fields = sorted({
                info["field"]
                for info in user_columns
                if (
                    info["source"] == "product"
                    and info["field"] != "id"
                )
            })

            physical_specs = (
                [
                    (Product, item["name"])
                    for item in pp_columns
                ]
                +
                [
                    (Template, item["name"])
                    for item in pt_columns
                ]
            )

            processed_user = 0
            processed_all = 0
            user_row = 2
            all_row = 2
            exported_ids = set()

            batch_size = 200

            for start in range(
                0,
                total,
                batch_size,
            ):
                batch_ids = product_ids[
                    start:start + batch_size
                ]

                end_number = min(
                    start + len(batch_ids),
                    total,
                )

                _logger.info(
                    "Product XLSX %s: %s a %s de %s",
                    self.id,
                    start + 1,
                    end_number,
                    total,
                )

                products = Product.browse(
                    batch_ids
                )

                read_fields = list(
                    product_read_fields
                )

                if "product_tmpl_id" not in read_fields:
                    read_fields.append(
                        "product_tmpl_id"
                    )

                product_values = products.read(
                    ["id"] + read_fields
                )

                product_by_id = {
                    row["id"]: row
                    for row in product_values
                }

                template_ids = []

                for row in product_values:
                    tmpl = row.get(
                        "product_tmpl_id"
                    )

                    if (
                        isinstance(tmpl, tuple)
                        and tmpl
                    ):
                        template_ids.append(
                            tmpl[0]
                        )

                template_by_id = {}

                if (
                    studio_template_fields
                    and template_ids
                ):
                    template_values = (
                        Template.browse(
                            list(set(template_ids))
                        ).read(
                            ["id"]
                            + studio_template_fields
                        )
                    )

                    template_by_id = {
                        row["id"]: row
                        for row in template_values
                    }

                self.env.cr.execute(
                    sql_batch,
                    [tuple(batch_ids)],
                )

                db_rows = self.env.cr.fetchall()

                calc_values = products.read(
                    ["id"] + computed_fields
                )

                calc_by_id = {
                    row["id"]: row
                    for row in calc_values
                }

                for product_id in batch_ids:
                    values = product_by_id.get(
                        product_id,
                        {},
                    )

                    tmpl = values.get(
                        "product_tmpl_id"
                    )

                    template_id = (
                        tmpl[0]
                        if isinstance(tmpl, tuple) and tmpl
                        else False
                    )

                    template_values = template_by_id.get(
                        template_id,
                        {},
                    )

                    for col, info in enumerate(
                        user_columns
                    ):
                        fname = info["field"]

                        if fname == "id":
                            value = product_id

                        elif info["source"] == "product":
                            value = values.get(
                                fname
                            )

                        else:
                            value = template_values.get(
                                fname
                            )

                        self._write_value(
                            user_sheet,
                            user_row,
                            col,
                            value,
                            formats,
                            field=info["field_object"],
                            field_name=fname,
                            humanize=True,
                        )

                    user_row += 1
                    processed_user += 1

                for db_row in db_rows:
                    product_id = db_row[0]

                    if product_id in exported_ids:
                        raise UserError(
                            _("Producto duplicado: %s")
                            % product_id
                        )

                    exported_ids.add(
                        product_id
                    )

                    col = 0

                    self._write_value(
                        all_sheet,
                        all_row,
                        col,
                        product_id,
                        formats,
                        field_name="id",
                    )

                    col += 1

                    for position, value in enumerate(
                        db_row[1:]
                    ):
                        Model, fname = physical_specs[
                            position
                        ]

                        field = Model._fields.get(
                            fname
                        )

                        self._write_value(
                            all_sheet,
                            all_row,
                            col,
                            value,
                            formats,
                            field=field,
                            field_name=fname,
                        )

                        col += 1

                    calculated = calc_by_id.get(
                        product_id,
                        {},
                    )

                    for fname in computed_fields:
                        self._write_value(
                            all_sheet,
                            all_row,
                            col,
                            calculated.get(fname),
                            formats,
                            field=Product._fields[fname],
                            field_name=fname,
                        )

                        col += 1

                    all_row += 1
                    processed_all += 1

            missing_ids = (
                set(product_ids)
                - exported_ids
            )

            if (
                processed_user != total
                or processed_all != total
                or len(exported_ids) != total
                or missing_ids
            ):
                raise UserError(
                    _(
                        "Exportacion incompleta. "
                        "Esperados=%s Productos=%s "
                        "Tecnicos=%s IDs=%s Faltantes=%s"
                    )
                    % (
                        total,
                        processed_user,
                        processed_all,
                        len(exported_ids),
                        len(missing_ids),
                    )
                )

            dictionary_headers = [
                "Modelo",
                "Nombre tecnico",
                "Etiqueta",
                "Tipo",
                "Store",
                "Studio",
                "Compute",
                "Related",
                "Relacion",
                "Columna fisica",
                "Vista Productos",
                "Observacion",
            ]

            for col, text in enumerate(
                dictionary_headers
            ):
                dict_sheet.write(
                    0,
                    col,
                    text,
                    formats["header"],
                )

            dict_row = 1

            pp_physical = {
                item["name"]
                for item in pp_columns
            }

            pt_physical = {
                item["name"]
                for item in pt_columns
            }

            for model_name, Model, physical in [
                (
                    "product.product",
                    Product,
                    pp_physical,
                ),
                (
                    "product.template",
                    Template,
                    pt_physical,
                ),
            ]:
                for fname in sorted(
                    Model._fields
                ):
                    field = Model._fields[
                        fname
                    ]

                    is_studio = fname.startswith(
                        "x_studio_"
                    )

                    physical_column = (
                        fname in physical
                    )

                    in_user = any(
                        info["field"] == fname
                        and (
                            (
                                model_name
                                == "product.product"
                                and info["source"]
                                == "product"
                            )
                            or
                            (
                                model_name
                                == "product.template"
                                and info["source"]
                                == "template"
                            )
                        )
                        for info in user_columns
                    )

                    if physical_column:
                        observation = (
                            "Columna fisica exportada"
                        )

                    elif (
                        model_name
                        == "product.product"
                        and fname in computed_fields
                    ):
                        observation = (
                            "Campo calculado incluido"
                        )

                    elif field.type == "binary":
                        observation = (
                            "Binario / imagen no incluido"
                        )

                    elif field.type in (
                        "one2many",
                        "many2many",
                    ):
                        observation = (
                            "Relacion multiple no incluida directamente"
                        )

                    elif not getattr(
                        field,
                        "store",
                        False,
                    ):
                        observation = (
                            "Calculado / relacionado no almacenado"
                        )

                    else:
                        observation = (
                            "Sin columna fisica directa"
                        )

                    values = [
                        model_name,
                        fname,
                        field.string or "",
                        field.type or "",
                        "SI"
                        if getattr(
                            field,
                            "store",
                            False,
                        )
                        else "NO",
                        "SI"
                        if is_studio
                        else "NO",
                        str(
                            getattr(
                                field,
                                "compute",
                                False,
                            )
                            or ""
                        ),
                        str(
                            getattr(
                                field,
                                "related",
                                False,
                            )
                            or ""
                        ),
                        str(
                            getattr(
                                field,
                                "comodel_name",
                                False,
                            )
                            or ""
                        ),
                        "SI"
                        if physical_column
                        else "NO",
                        "SI"
                        if in_user
                        else "NO",
                        observation,
                    ]

                    for col, value in enumerate(
                        values
                    ):
                        dict_sheet.write(
                            dict_row,
                            col,
                            self._clean_text(value),
                            formats["text"],
                        )

                    dict_row += 1

            dict_sheet.freeze_panes(
                1,
                0,
            )

            dict_sheet.autofilter(
                0,
                0,
                dict_row - 1,
                len(dictionary_headers) - 1,
            )

            summary = [
                (
                    "Fecha generacion",
                    str(fields.Datetime.now()),
                ),
                (
                    "Productos encontrados",
                    total,
                ),
                (
                    "Filas Productos",
                    processed_user,
                ),
                (
                    "Filas Todos los campos",
                    processed_all,
                ),
                (
                    "IDs unicos",
                    len(exported_ids),
                ),
                (
                    "Faltantes",
                    len(missing_ids),
                ),
                (
                    "Columnas Productos",
                    len(user_columns),
                ),
                (
                    "Studio product.product",
                    len(studio_product_fields),
                ),
                (
                    "Studio product.template",
                    len(studio_template_fields),
                ),
                (
                    "Columnas tecnicas",
                    len(all_headers),
                ),
                (
                    "Validacion",
                    "OK",
                ),
            ]

            summary_sheet.write(
                0,
                0,
                "Concepto",
                formats["header"],
            )

            summary_sheet.write(
                0,
                1,
                "Valor",
                formats["header"],
            )

            for row, (
                label,
                value,
            ) in enumerate(
                summary,
                start=1,
            ):
                summary_sheet.write(
                    row,
                    0,
                    label,
                    formats["text"],
                )

                self._write_value(
                    summary_sheet,
                    row,
                    1,
                    value,
                    formats,
                )

            user_sheet.set_column(
                0,
                len(user_columns) - 1,
                20,
            )

            all_sheet.set_column(
                0,
                len(all_headers) - 1,
                18,
            )

            dict_sheet.set_column(
                0,
                0,
                20,
            )

            dict_sheet.set_column(
                1,
                1,
                32,
            )

            dict_sheet.set_column(
                2,
                2,
                35,
            )

            dict_sheet.set_column(
                3,
                10,
                18,
            )

            dict_sheet.set_column(
                11,
                11,
                45,
            )

            summary_sheet.set_column(
                0,
                0,
                40,
            )

            summary_sheet.set_column(
                1,
                1,
                55,
            )

            workbook.close()
            workbook = None

            file_size = os.path.getsize(
                filepath
            )

            filename = (
                "Productos_%s.xlsx"
                % datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                )
            )

            with open(
                filepath,
                "rb",
            ) as fh:
                binary_data = fh.read()

            if self.attachment_id:
                self.attachment_id.sudo().unlink()

            attachment = (
                self.env["ir.attachment"]
                .sudo()
                .create({
                    "name": filename,
                    "type": "binary",
                    "datas": base64.b64encode(
                        binary_data
                    ),
                    "mimetype": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "res_model": self._name,
                    "res_id": self.id,
                })
            )

            self.write({
                "state": "done",
                "finished_at": fields.Datetime.now(),
                "product_count": total,
                "user_column_count": len(
                    user_columns
                ),
                "technical_column_count": len(
                    all_headers
                ),
                "studio_product_count": len(
                    studio_product_fields
                ),
                "studio_template_count": len(
                    studio_template_fields
                ),
                "missing_count": len(
                    missing_ids
                ),
                "file_size_mb": (
                    file_size
                    / 1024
                    / 1024
                ),
                "attachment_id": attachment.id,
                "progress_message": (
                    "Finalizado correctamente"
                ),
                "error_message": False,
            })

        finally:
            if workbook is not None:
                try:
                    workbook.close()
                except Exception:
                    pass

            if os.path.exists(filepath):
                try:
                    os.unlink(filepath)
                except Exception:
                    pass
