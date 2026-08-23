# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


ALFREDO_LOGIN = "a.zuniga@grupolinea7.com"


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    group = env.ref(
        "l7_consignacion_price_report.group_consignacion_price_report"
    )

    # El permiso inicia sin usuarios.
    group.write({
        "users": [(5, 0, 0)],
    })

    # Se agrega exclusivamente Alfredo Zuñiga.
    alfredo = env["res.users"].with_context(active_test=False).search(
        [
            ("login", "=", ALFREDO_LOGIN),
        ],
        limit=1,
    )

    if not alfredo:
        alfredo = env["res.users"].with_context(active_test=False).search(
            [
                ("name", "ilike", "Alfredo Zu"),
            ],
            limit=1,
        )

    if alfredo:
        group.write({
            "users": [(4, alfredo.id)],
        })
