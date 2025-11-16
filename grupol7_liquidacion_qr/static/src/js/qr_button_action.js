odoo.define('grupol7_liquidacion_qr.qr_button_action', function (require) {
    'use strict';

    const rpc = require('web.rpc');

    // --- utilidades para localizar el POS en Odoo 16 (OWL) ---
    function getPos() {
        const dbg = (window.odoo && odoo.__DEBUG__ && odoo.__DEBUG__.services) || {};
        return (
            (window.odoo && (odoo.pos || (odoo.env && odoo.env.pos))) ||
            dbg['point_of_sale.PosGlobalState'] ||
            dbg['point_of_sale.PosService'] ||
            dbg['point_of_sale.pos'] ||
            null
        );
    }
    function getOrder(pos) {
        return (pos && (
            pos.get_order?.() ||
            (pos.env && pos.env.pos && pos.env.pos.get_order?.())
        )) || null;
    }
    function getProductById(pos, id) {
        // Soporta varias formas de cache interna según build
        return (
            pos?.db?.get_product_by_id?.(id) ||
            (pos?.db?.product_by_id && pos.db.product_by_id[id]) ||
            pos?.env?.pos?.db?.get_product_by_id?.(id) ||
            (pos?.env?.pos?.db?.product_by_id && pos.env.pos.db.product_by_id[id]) ||
            null
        );
    }
    function getConfigId() {
        const m = /[?&]config_id=(\d+)/.exec(location.search);
        return m ? parseInt(m[1]) : null;
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

            // Normaliza campos por si vienen de forma distinta
            const price = Number(data.price);
            const productId = Array.isArray(data.product_id) ? data.product_id[0] : data.product_id;
            const couponName = data.name || (Array.isArray(data.product_id) ? data.product_id[1] : '') || 'Cupón';

            const pos = getPos();
            const product = pos ? getProductById(pos, productId) : null;

            if (pos && product) {
                const order = getOrder(pos);
                if (order) {
                    order.add_product(product, { price, merge: false });
                    const line = order.get_last_orderline?.();
                    if (line) {
                        line.set_unit_price?.(price);
                        line.price_manually_set = true;          // para que no recalculen listas
                        line.liq_coupon_id = data.coupon_id || data.coupon || null;
                    }
                    return;
                }
            }

            // Fallback: si no se añadió automáticamente
            alert(`Cupón OK: ${couponName}\nPrecio: ${price}\n(El producto no pudo añadirse automáticamente)`);
        } catch (e) {
            const msg =
                (e && e.message) ||
                (e && e.data && (e.data.message || e.data.debug)) ||
                'Cupón inválido o no autorizado.';
            alert(msg);
        }
    }

    function bindButton() {
        // Nuestro botón con icono QR
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
