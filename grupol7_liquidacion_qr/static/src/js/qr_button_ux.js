odoo.define('grupol7_liquidacion_qr.qr_button_dom', function (require) {
    'use strict';
    var rpc = require('web.rpc');

    function findNoteBtn() {
        var sels = [
            '.control-buttons button[aria-label="Customer Note"]',
            '.control-buttons button[aria-label="Nota de cliente"]',
            '.control-buttons i.fa-sticky-note'
        ];
        for (var i = 0; i < sels.length; i++) {
            var el = document.querySelector(sels[i]);
            if (el) return el.closest('button') || el;
        }
        return null;
    }

    function patchOnce() {
        var btn = findNoteBtn();
        if (!btn) {
            requestAnimationFrame(patchOnce);
            return;
        }
        if (btn.dataset.g7CouponBound) return;

        btn.dataset.g7CouponBound = '1';
        btn.id = 'g7-coupon-btn';
        btn.setAttribute('aria-label', 'Cupón QR');
        var lbl = btn.querySelector('.control-button-label, .button-label, span');
        if (lbl) lbl.textContent = 'Cupón QR';

        btn.addEventListener('click', async function () {
            try {
                var code = window.prompt('Escanee o teclee el código del cupón');
                if (!code) return;

                var config_id = null;
                try {
                    if (odoo.pos && odoo.pos.config) config_id = odoo.pos.config.id;
                    else if (odoo.__DEBUG__ && odoo.__DEBUG__.services && odoo.__DEBUG__.services.pos)
                        config_id = odoo.__DEBUG__.services.pos.config_id;
                } catch (_) {}

                var res = await rpc.query({
                    model: 'liquidation.coupon',
                    method: 'pos_validate_coupon',
                    args: [[], code, config_id],
                });

                var msg = 'Cupón OK: ' + (res.info || 'Cupón') +
                          '\nPrecio: ' + res.price +
                          (res.auto_added ? '' : '\n(El producto no pudo añadirse automáticamente)');
                window.alert(msg);
            } catch (e) {
                window.alert(e && e.message ? e.message : String(e));
            }
        });
    }

    patchOnce();
});
