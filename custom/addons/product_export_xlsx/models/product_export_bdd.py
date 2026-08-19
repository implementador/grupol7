import base64
import logging
import os
import re
import tempfile
import unicodedata
from datetime import datetime

import xlsxwriter

from odoo import fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class ProductExportXlsxBDD(models.Model):
    _inherit = "product.export.xlsx"

    BDD_HEADERS = [
        "Referencia", "Producto", "Código de Barras", "Marca",
        "Categoria 1", "Categoria 2", "Categoria 3", "Categoria 4",
        "Condicionado", "Catalogo", "Categoría de UNSPSC", "Grupo",
        "Piezas", "UXE", "Imagen", "Costo",
        "Precio Intertienda", "Precio Mayoreo", "Precio Publico", "Precio Lista",
        "Precio Intertienda s/IVA", "Precio Mayoreo s/IVA",
        "Precio Publico s/IVA", "Precio Lista s/IVA",
    ]

    IVA_FACTOR = 1.16

    def _bdd_norm(self, value):
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def _bdd_resolve_field(self, Model, labels=(), technical=()):
        excluded = {"binary", "one2many", "many2many"}

        for fname in technical:
            field = Model._fields.get(fname)
            if field and field.type not in excluded:
                return fname

        aliases = [self._bdd_norm(value) for value in labels if value]
        candidates = []

        for fname, field in Model._fields.items():
            if field.type in excluded:
                continue
            label = self._bdd_norm(field.string)
            tech = self._bdd_norm(fname)
            score = 0
            for alias in aliases:
                if label == alias:
                    score = max(score, 1000)
                elif tech == alias:
                    score = max(score, 950)
                elif alias and alias in label:
                    score = max(score, 750)
                elif alias and alias in tech:
                    score = max(score, 700)
            if score:
                if getattr(field, "store", False):
                    score += 20
                if re.search(r"_[123]$", fname):
                    score -= 30
                candidates.append((score, -len(fname), fname))

        if not candidates:
            return False
        candidates.sort(reverse=True)
        return candidates[0][2]

    def _bdd_resolve_specs(self, Product, Template):
        definitions = {
            "marca": (("Marca", "Brand"), ("product_brand_id", "brand_id", "x_studio_marca")),
            "condicionado": (("Condicionado",), ("x_studio_condicionado",)),
            "catalogo": (("Catalogo", "Catálogo"), ("x_studio_catalogo", "x_studio_catlogo")),
            "unspsc": (
                ("Categoría de UNSPSC", "Categoria de UNSPSC", "UNSPSC Category", "UNSPSC"),
                ("unspsc_code_id", "unspsc_category_id"),
            ),
            "grupo": (("Grupo",), ("x_studio_grupo",)),
            "uxe": (
                ("UXE", "UXE de Compra", "UXE de compra"),
                ("x_studio_uxe", "x_studio_uxe_de_compra"),
            ),
        }
        result = {}
        for key, (labels, technical) in definitions.items():
            fname = self._bdd_resolve_field(Template, labels=labels, technical=technical)
            source = "template"
            if not fname:
                fname = self._bdd_resolve_field(Product, labels=labels, technical=technical)
                source = "product"
            result[key] = (source, fname)
        return result

    def _bdd_human_value(self, field, value):
        if value in (None, False, ""):
            return ""
        if field and field.type == "many2one":
            if isinstance(value, (tuple, list)) and len(value) >= 2:
                return value[1]
            return value
        if field and field.type == "boolean":
            return "Si" if bool(value) else "No"
        if field and field.type == "selection":
            try:
                return dict(field._description_selection(self.env)).get(value, value)
            except Exception:
                return value
        return value

    def _bdd_find_pricelist(self, keyword, aliases=(), exclude=()):
        Pricelist = self.env["product.pricelist"].sudo().with_context(active_test=False)
        pricelists = Pricelist.search([("active", "=", True)])
        terms = [self._bdd_norm(keyword)] + [self._bdd_norm(x) for x in aliases]
        excluded = [self._bdd_norm(x) for x in exclude]
        scored = []

        for pricelist in pricelists:
            name = self._bdd_norm(pricelist.name)
            if excluded and any(term and term in name for term in excluded):
                continue
            score = 0
            for term in terms:
                if not term:
                    continue
                if name == term:
                    score = max(score, 1000)
                elif name.startswith(term + " ") or name.endswith(" " + term):
                    score = max(score, 850)
                elif term in name:
                    score = max(score, 700)
            if not score:
                continue
            if pricelist.active:
                score += 50
            if not pricelist.company_id:
                score += 20
            elif pricelist.company_id == self.env.company:
                score += 40
            else:
                score -= 20
            scored.append((score, pricelist.id, pricelist))

        if not scored:
            raise UserError(
                _("No se encontro lista de precios '%s'. Disponibles: %s")
                % (keyword, ", ".join(pricelists.mapped("name")[:80]))
            )
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2]

    def _bdd_category_maps(self):
        Category = self.env["product.category"].sudo().with_context(active_test=False)
        rows = Category.search([]).read(["name", "parent_id"])
        names = {}
        parents = {}
        for row in rows:
            names[row["id"]] = row.get("name") or ""
            parent = row.get("parent_id")
            parents[row["id"]] = parent[0] if isinstance(parent, (tuple, list)) and parent else False
        return names, parents

    def _bdd_category_levels(self, categ_id, names, parents):
        if not categ_id:
            return ["", "", "", ""]
        path = []
        seen = set()
        current = categ_id
        while current and current not in seen:
            seen.add(current)
            if names.get(current):
                path.append(names[current])
            current = parents.get(current)
        path.reverse()
        if not path:
            return ["", "", "", ""]
        path = path[:4]
        while len(path) < 4:
            path.append(path[-1])
        return path

    def _bdd_write(self, sheet, row, col, value):
        if value is None or value is False:
            return
        if isinstance(value, bool):
            sheet.write(row, col, "Si" if value else "No")
        elif isinstance(value, (int, float)):
            sheet.write_number(row, col, value)
        else:
            sheet.write(row, col, self._clean_text(value))

    def _generate_bdd_attachment(self):
        self.ensure_one()

        Product = self.env["product.product"].sudo().with_context(active_test=False)
        Template = self.env["product.template"].sudo().with_context(active_test=False)
        products_all = Product.search([], order="id")
        product_ids = products_all.ids
        total = len(product_ids)
        if not total:
            raise UserError(_("No existen productos para exportar."))

        specs = self._bdd_resolve_specs(Product, Template)
        intertienda = self._bdd_find_pricelist(
            "intertienda", aliases=("inter tienda", "precio intertienda")
        )
        mayoreo = self._bdd_find_pricelist("mayoreo", aliases=("precio mayoreo",))
        lista = self._bdd_find_pricelist(
            "lista",
            aliases=("precio lista",),
            exclude=("intertienda", "mayoreo", "publico", "public"),
        )
        pricelists = {
            "intertienda": intertienda,
            "mayoreo": mayoreo,
            "lista": lista,
        }
        category_names, category_parents = self._bdd_category_maps()

        product_fields = {
            "default_code", "name", "barcode", "categ_id", "list_price",
            "standard_price", "qty_available", "product_tmpl_id",
        }
        template_fields = set()
        for source, fname in specs.values():
            if not fname:
                continue
            if source == "product":
                product_fields.add(fname)
            else:
                template_fields.add(fname)
        product_fields = sorted(f for f in product_fields if f in Product._fields)
        template_fields = sorted(f for f in template_fields if f in Template._fields)

        fd, filepath = tempfile.mkstemp(prefix="bdd_productos_", suffix=".xlsx")
        os.close(fd)
        workbook = None

        try:
            workbook = xlsxwriter.Workbook(filepath, {"constant_memory": True})
            sheet = workbook.add_worksheet("BDD")
            header = workbook.add_format({
                "bg_color": "#002060",
                "font_color": "#FFFFFF",
            })
            for col, value in enumerate(self.BDD_HEADERS):
                sheet.write(0, col, value, header)
            sheet.freeze_panes(1, 0)
            sheet.set_column(0, 0, 13)
            sheet.set_column(1, 1, 57.14)
            sheet.set_column(2, len(self.BDD_HEADERS) - 1, 13)

            row_number = 1
            processed = 0
            batch_size = 200
            selected_fields_log = {}
            for key, (source, fname) in specs.items():
                selected_fields_log[key] = "%s.%s" % (source, fname) if fname else "NO ENCONTRADO"

            for start in range(0, total, batch_size):
                batch_ids = product_ids[start:start + batch_size]
                products = Product.browse(batch_ids)
                values_list = products.read(["id"] + product_fields)
                values_by_id = {row["id"]: row for row in values_list}

                template_ids = []
                product_to_template = {}
                for row in values_list:
                    tmpl = row.get("product_tmpl_id")
                    tmpl_id = tmpl[0] if isinstance(tmpl, (tuple, list)) and tmpl else False
                    if tmpl_id:
                        template_ids.append(tmpl_id)
                        product_to_template[row["id"]] = tmpl_id

                template_by_id = {}
                if template_ids and template_fields:
                    rows = Template.browse(list(set(template_ids))).read(["id"] + template_fields)
                    template_by_id = {row["id"]: row for row in rows}

                price_results = {}
                price_date = fields.Datetime.now()
                for key, pricelist in pricelists.items():
                    price_results[key] = pricelist._compute_price_rule(
                        products, 1.0, date=price_date
                    )

                image_product_ids = set()
                image_template_ids = set()
                self.env.cr.execute(
                    """
                    SELECT res_model, res_id
                    FROM ir_attachment
                    WHERE res_field IN ('image_1920','image_1024','image_512','image_256','image_128')
                      AND (
                          (res_model = 'product.product' AND res_id IN %s)
                          OR
                          (res_model = 'product.template' AND res_id IN %s)
                      )
                    """,
                    [tuple(batch_ids or [0]), tuple(template_ids or [0])],
                )
                for model_name, res_id in self.env.cr.fetchall():
                    if model_name == "product.product":
                        image_product_ids.add(res_id)
                    elif model_name == "product.template":
                        image_template_ids.add(res_id)

                for product_id in batch_ids:
                    values = values_by_id.get(product_id, {})
                    tmpl_id = product_to_template.get(product_id)
                    tvalues = template_by_id.get(tmpl_id, {})
                    categ = values.get("categ_id")
                    categ_id = categ[0] if isinstance(categ, (tuple, list)) and categ else False
                    categories = self._bdd_category_levels(
                        categ_id, category_names, category_parents
                    )

                    def custom_value(key):
                        source, fname = specs.get(key, (False, False))
                        if not fname:
                            return ""
                        Model = Template if source == "template" else Product
                        raw = (tvalues if source == "template" else values).get(fname)
                        return self._bdd_human_value(Model._fields[fname], raw)

                    def computed_price(key):
                        price, rule_id = price_results[key].get(product_id, (0.0, False))
                        if not rule_id:
                            return "NA", 0.0
                        price = price or 0.0
                        return price, round(price / self.IVA_FACTOR, 2)

                    inter_price, inter_no_tax = computed_price("intertienda")
                    may_price, may_no_tax = computed_price("mayoreo")
                    lista_price, lista_no_tax = computed_price("lista")
                    public_price = values.get("list_price") or 0.0
                    public_no_tax = round(public_price / self.IVA_FACTOR, 2) if public_price else 0.0
                    qty = values.get("qty_available") or 0.0
                    pieces = qty if abs(qty) > 0.0000001 else ""
                    has_image = (
                        product_id in image_product_ids
                        or (tmpl_id and tmpl_id in image_template_ids)
                    )

                    row_values = [
                        values.get("default_code") or "",
                        values.get("name") or "",
                        values.get("barcode") or "",
                        custom_value("marca"),
                        categories[0], categories[1], categories[2], categories[3],
                        custom_value("condicionado"),
                        custom_value("catalogo"),
                        custom_value("unspsc"),
                        custom_value("grupo"),
                        pieces,
                        custom_value("uxe"),
                        "Si" if has_image else "No",
                        values.get("standard_price") or 0.0,
                        inter_price, may_price, public_price, lista_price,
                        inter_no_tax, may_no_tax, public_no_tax, lista_no_tax,
                    ]
                    for col, value in enumerate(row_values):
                        self._bdd_write(sheet, row_number, col, value)
                    row_number += 1
                    processed += 1

                self.write({
                    "progress_message": "BDD %s de %s" % (min(start + batch_size, total), total)
                })

            if processed != total:
                raise UserError(
                    _("BDD incompleta. Esperados=%s Procesados=%s") % (total, processed)
                )

            workbook.close()
            workbook = None

            filename = "BDD_Productos_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(filepath, "rb") as fh:
                data = fh.read()

            attachment = self.env["ir.attachment"].sudo().create({
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(data),
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "res_model": self._name,
                "res_id": self.id,
            })

            return attachment, {
                "processed": processed,
                "size_mb": os.path.getsize(filepath) / 1024 / 1024,
                "intertienda": "%s | ID %s" % (intertienda.name, intertienda.id),
                "mayoreo": "%s | ID %s" % (mayoreo.name, mayoreo.id),
                "lista": "%s | ID %s" % (lista.name, lista.id),
                "fields": selected_fields_log,
            }

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
                    _logger.warning("No fue posible eliminar temporal BDD %s", filepath)

    def _generate_xlsx(self):
        self.ensure_one()

        # Conserva el Excel completo ya validado por la V1.
        super()._generate_xlsx()
        self.invalidate_recordset()
        complete_attachment = self.attachment_id

        self.write({
            "state": "processing",
            "progress_message": "Generando formato BDD y listas de precios",
        })

        bdd_attachment, meta = self._generate_bdd_attachment()

        self.write({
            "state": "done",
            "finished_at": fields.Datetime.now(),
            "product_count": meta["processed"],
            "user_column_count": len(self.BDD_HEADERS),
            "missing_count": 0,
            "file_size_mb": meta["size_mb"],
            "attachment_id": bdd_attachment.id,
            "progress_message": (
                "BDD lista | Intertienda: %s | Mayoreo: %s | Lista: %s | Completo Attachment: %s"
                % (meta["intertienda"], meta["mayoreo"], meta["lista"], complete_attachment.id)
            ),
            "error_message": False,
        })
