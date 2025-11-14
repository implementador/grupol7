odoo.define('grupol7_liquidacion_qr.qr_button_action', function (require) {
    'use strict';
    const rpc = require('web.rpc');

    function getPos() {
        // intenta varias rutas según la versión/servicio
        return (window.odoo && (odoo.pos || (odoo.__DEBUG__ && odoo.__DEBUG__.services && (odoo.__DEBUG__.services['point_of_sale.pos'] || odoo.__DEBUG__.services['point_of_sale.PosService'])))) || null;
    }
    function getConfigId() {
        const m = /[?&]config_id=(\d+)/.exec(location.search);
        const id = m ? parseInt(m[1]) : null;
        const pos = getPos();
        return id || (pos && (pos.config_id || (pos.config && pos.config.id))) || null;
    }
    async function handleCoupon() {
        const code = (window.prompt('Escanea o pega el código del cupón:') || '').trim();
        if (!code) return;

        const pos_config_id = getConfigId();
        try {
            const data = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [code, pos_config_id],
            });
            // data esperado: { product_id, price, name, coupon_id, ... }

            const pos = getPos();
            // Intenta localizar el producto en caché del POS (varía según build)
            let product = null;
            if (pos) {
                product =
                    (pos.db && pos.db.get_product_by_id && pos.db.get_product_by_id(data.product_id)) ||
                    (pos.get_product_by_id && pos.get_product_by_id(data.product_id)) ||
                    null;
            }

            if (pos && product && (pos.get_order || (pos.env && pos.env.pos && pos.env.pos.get_order))) {
                const order = pos.get_order ? pos.get_order() : pos.env.pos.get_order();
                order.add_product(product, { price: data.price, merge: false });
                const line = order.get_last_orderline && order.get_last_orderline();
                if (line) {
                    // Forzamos precio y marcamos como “bloqueado” para tu script liq_lock_price.js
                    line.set_unit_price && line.set_unit_price(data.price);
                    line.price_manually_set = true;
                    line.liq_coupon_id = data.coupon_id || data.coupon || null;
                }
            } else {
                // Fallback: mostrar confirmación si no se pudo añadir automáticamente
                alert(`Cupón OK: ${data.name}\nPrecio: ${data.price}\n(El producto no pudo añadirse automáticamente)`);
            }
        } catch (e) {
            const msg =
                (e && e.message) ||
                (e && e.data && (e.data.message || e.data.debug)) ||
                'Cupón inválido o no autorizado.';
            alert(msg);
        }
    }

    function bindButton() {
        // Toma el botón (el que renombramos antes)
        const btn =
            document.querySelector('.control-button i.fa-qrcode')?.closest('.control-button') ||
            document.querySelector('.control-button i.fa-sticky-note')?.closest('.control-button');
        if (!btn || btn.dataset.couponBound === '1') return;

        btn.dataset.couponBound = '1';
        btn.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            handleCoupon();
        });
    }

    document.addEventListener('DOMContentLoaded', bindButton);
    new MutationObserver(bindButton).observe(document.documentElement, { childList: true, subtree: true });
});
