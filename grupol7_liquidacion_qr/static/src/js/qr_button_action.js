odoo.define('grupol7_liquidacion_qr.qr_button_action', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');
    const rpc = require('web.rpc');

    function getConfigId() {
        // Lee config_id del querystring (ej: /pos/ui?config_id=1)
        const m = /[?&]config_id=(\d+)/.exec(window.location.search);
        return m ? parseInt(m[1]) : false;
    }

    async function onCouponClick(ev) {
        const target = ev.target.closest('.control-buttons .control-button[data-g7CouponButton="1"]');
        if (!target) return;

        // Bloquea la acción original de "Nota de cliente"
        ev.preventDefault();
        ev.stopPropagation();

        const code = window.prompt('Escanee o capture el código del cupón:');
        if (!code) return;
        const pos_config_id = getConfigId();

        try {
            const res = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [code, pos_config_id],
            });
            // Igual que antes: informamos y listo (sin auto-agregar producto)
            window.alert(
                `Cupón OK\nPrecio: ${res.price}\n${res.info}\n\n(El producto no pudo añadirse automáticamente)`
            );
        } catch (err) {
            const msg = (err && err.data && err.data.message) || err.message || 'Error al validar';
            window.alert(msg);
        }
    }

    function init() {
        // Capturamos el clic en CAPTURA para bloquear el handler original
        document.addEventListener('click', onCouponClick, { capture: true });
    }

    domReady(init);
});
