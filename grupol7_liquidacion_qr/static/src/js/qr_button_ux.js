odoo.define('grupol7_liquidacion_qr.qr_button_dom', function (require) {
    'use strict';
    const rpc = require('web.rpc');

    function getNoteButton() {
        const already = document.getElementById('g7-coupon-btn');
        if (already) return already;

        const selectors = [
            '.control-buttons button[aria-label="Customer Note"]',
            '.control-buttons button[aria-label="Nota de cliente"]',
            '.control-buttons i.fa-sticky-note'
        ];
        for (let s of selectors) {
            const el = document.querySelector(s);
            if (el) return el.closest('button') || el;
        }
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

        // Normaliza completamente el contenido para evitar concatenaciones
        while (btn.firstChild) btn.removeChild(btn.firstChild);
        btn.insertAdjacentHTML('afterbegin',
            '<i class="fa fa-qrcode" aria-hidden="true"></i>' +
            '<span class="control-button-label">Cupón QR</span>'
        );
        btn.setAttribute('aria-label', 'Cupón QR');
        btn.title = 'Cupón QR';

        // Quita clases/residuos visuales si existieran
        btn.classList.remove('o_pos_button_note');

        // Acción: cancela cualquier handler previo de "Nota de cliente"
        btn.addEventListener('click', async (ev) => {
            ev.stopImmediatePropagation();
            ev.stopPropagation();
            ev.preventDefault();

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
        const kick = () => {
            if (!document || !document.body) { setTimeout(kick, 100); return; }
            let tries = 0;
            const iv = setInterval(() => {
                if (tryPatch() || ++tries > 150) clearInterval(iv);
            }, 100);
            if (window.MutationObserver) {
                try {
                    const mo = new MutationObserver(() => tryPatch());
                    mo.observe(document.body, { childList: true, subtree: true });
                } catch (e) {}
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
