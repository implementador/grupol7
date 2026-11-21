odoo.define('grupol7_liquidacion_qr.qr_button_dom', function (require) {
    'use strict';
    const rpc = require('web.rpc');

    function getNoteButton() {
        // ¿ya fue renombrado?
        const already = document.getElementById('g7-coupon-btn');
        if (already) return already;

        // candidatos por aria-label o ícono sticky-note
        const selectors = [
            '.control-buttons button[aria-label="Customer Note"]',
            '.control-buttons button[aria-label="Nota de cliente"]',
            '.control-buttons i.fa-sticky-note'
        ];
        for (let s of selectors) {
            const el = document.querySelector(s);
            if (el) return el.closest('button') || el;
        }
        // por texto visible
        const btns = document.querySelectorAll('.control-buttons button, .control-buttons .button');
        for (const b of btns) {
            const t = ((b.innerText||'') + ' ' + (b.getAttribute('aria-label')||'')).toLowerCase();
            if (t.includes('nota de cliente') || t.includes('customer note')) return b;
        }
        return null;
    }

    function bind(btn) {
        if (!btn || btn.dataset.g7CouponBound) return;
        btn.dataset.g7CouponBound = '1';
        btn.id = 'g7-coupon-btn';

        // etiqueta
        const label = btn.querySelector('.control-button-label, .button-label, span') || btn;
        label.textContent = 'Cupón QR';

        // ícono
        let icon = btn.querySelector('i');
        if (!icon) { icon = document.createElement('i'); btn.prepend(icon); }
        icon.className = 'fa fa-qrcode';

        // acción
        btn.addEventListener('click', async (ev) => {
            ev.stopPropagation();
            try {
                const code = window.prompt('Escanee o teclee el código del cupón');
                if (!code) return;

                let config_id = null;
                try { if (odoo.pos && odoo.pos.config) config_id = odoo.pos.config.id; } catch (e) {}

                const res = await rpc.query({
                    model: 'liquidation.coupon',
                    method: 'pos_validate_coupon',
                    args: [[], code, config_id],
                });

                const msg = 'Cupón OK: ' + (res.info || 'Cupón') +
                            '\nPrecio: ' + res.price +
                            (res.auto_added ? '' : '\n(El producto no pudo añadirse automáticamente)');
                window.alert(msg);
            } catch (e) {
                window.alert(e && e.message ? e.message : String(e));
            }
        }, { capture: true });
    }

    function tryPatch() {
        const btn = getNoteButton();
        if (btn) { bind(btn); return true; }
        return false;
    }

    function start() {
        // Espera segura a que exista document.body
        const kick = () => {
            if (!document || !document.body) {
                setTimeout(kick, 100);
                return;
            }
            // Reintentos rápidos al cargar
            let tries = 0;
            const iv = setInterval(() => {
                if (tryPatch() || ++tries > 150) clearInterval(iv);
            }, 100);

            // Observer solo si existe body y el API está disponible
            if (window.MutationObserver) {
                try {
                    const mo = new MutationObserver(() => tryPatch());
                    mo.observe(document.body, { childList: true, subtree: true });
                } catch (e) {
                    // Silencioso si el body aún no estuviera listo
                    // (los reintentos de arriba lo cubrirán)
                }
            }
        };
        kick();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
});
