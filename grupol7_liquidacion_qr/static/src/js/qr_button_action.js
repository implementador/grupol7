odoo.define('grupol7_liquidacion_qr.qr_button_action', function (require) {
    'use strict';

    const rpc = require('web.rpc');
    const Registries = require('point_of_sale.Registries');

    let extendedOK = false;

    // 1) Intento “oficial”: extender el componente del botón del POS
    try {
        const OrderlineCustomerNoteButton = require('point_of_sale.OrderlineCustomerNoteButton');

        const G7CouponPatch = (OrderlineCustomerNoteButton_) => class extends OrderlineCustomerNoteButton_ {
            async onClick() {
                const code = window.prompt('Escanee o teclee el código del cupón');
                if (!code) return;

                const config_id = this.env.pos && this.env.pos.config && this.env.pos.config.id;
                try {
                    const res = await rpc.query({
                        model: 'liquidation.coupon',
                        method: 'pos_validate_coupon',
                        args: [[], code, config_id],
                    });
                    const msg = 'Cupón OK: ' + (res.info || 'Cupón') +
                                '\nPrecio: ' + res.price +
                                (res.auto_added ? '' : '\n(El producto no pudo añadirse automáticamente)');
                    this.showPopup('ConfirmPopup', { title: 'Cupón QR', body: msg });
                } catch (err) {
                    this.showPopup('ErrorPopup', { title: 'Cupón QR', body: err && err.message ? err.message : String(err) });
                }
            }
        };

        Registries.Component.extend(OrderlineCustomerNoteButton, G7CouponPatch);
        extendedOK = true;
    } catch (e) {
        console.warn('G7 Coupon: fallback DOM listener (no se pudo extender el componente):', e);
    }

    // 2) Fallback: listener por DOM solo si no se pudo extender
    if (!extendedOK) {
        const once = () => {
            const btn = document.querySelector('.control-buttons button[aria-label="Cupón QR"]');
            if (!btn || btn.dataset.g7Bound) return;
            btn.dataset.g7Bound = '1';
            btn.addEventListener('click', async (ev) => {
                ev.stopImmediatePropagation();
                ev.stopPropagation();
                ev.preventDefault();

                const code = window.prompt('Escanee o teclee el código del cupón');
                if (!code) return;

                let config_id = null;
                try { if (odoo.pos && odoo.pos.config) config_id = odoo.pos.config.id; } catch (e) {}
                try {
                    const res = await rpc.query({
                        model: 'liquidation.coupon',
                        method: 'pos_validate_coupon',
                        args: [[], code, config_id],
                    });
                    window.alert(
                        'Cupón OK: ' + (res.info || 'Cupón') +
                        '\nPrecio: ' + res.price +
                        (res.auto_added ? '' : '\n(El producto no pudo añadirse automáticamente)')
                    );
                } catch (err) {
                    window.alert(err && err.message ? err.message : String(err));
                }
            }, { capture: true });
        };

        const arm = () => {
            once();
            if (window.MutationObserver && document.body) {
                try {
                    const mo = new MutationObserver(() => once());
                    mo.observe(document.body, { childList: true, subtree: true });
                } catch (_) {}
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', arm, { once: true });
        } else {
            arm();
        }
    }
});
