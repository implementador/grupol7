odoo.define('grupol7_liquidacion_qr.qr_button_dom_and_action', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');
    const rpc = require('web.rpc');

    // Reemplaza el texto (sin concatenar), pone ícono y marca el botón
    function patchCouponButton() {
        const area = document.querySelector('.control-buttons');
        if (!area) return;

        const btn = [...area.querySelectorAll('.control-button')].find(
            b => /Nota\s+de\s+cliente/i.test(b.textContent.trim())
        );
        if (!btn || btn.dataset.g7CouponButton === '1') return;

        btn.dataset.g7CouponButton = '1';
        btn.classList.add('g7-coupon-button');

        const icon = btn.querySelector('i') || btn.querySelector('.fa');
        if (icon) icon.className = 'fa fa-qrcode';

        const label = btn.querySelector('span') || btn;
        label.textContent = 'Cupón QR';
    }

    // Clic del botón: bloquea la acción original y valida el cupón
    async function onGlobalClick(ev) {
        const btn = ev.target.closest('.control-buttons .control-button[data-g7CouponButton="1"]');
        if (!btn) return;

        ev.preventDefault();
        ev.stopPropagation();

        // Pedimos el código (por ahora prompt; después conectamos cámara/lector)
        const code = window.prompt('Escanee o capture el código del cupón:');
        if (!code) return;

        // Lee config_id del URL (ej: /pos/ui?config_id=1)
        const m = /[?&]config_id=(\d+)/.exec(window.location.search);
        const pos_config_id = m ? parseInt(m[1]) : false;

        try {
            const res = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [code, pos_config_id],
            });
            window.alert(
                `Cupón OK\nPrecio: ${res.price}\n${res.info}\n\n(El producto no pudo añadirse automáticamente)`
            );
        } catch (err) {
            const msg = (err && err.data && err.data.message) || err.message || 'Error al validar';
            window.alert(msg);
        }
    }

    function start() {
        // Intenta varias veces (por si el POS tarda en renderizar)
        patchCouponButton();
        setTimeout(patchCouponButton, 300);
        setTimeout(patchCouponButton, 1000);
        setTimeout(patchCouponButton, 2000);

        // Observa todo el documento (evita "MutationObserver parameter 1..." usando un Node real)
        const root = document.documentElement || document.body;
        const obs = new MutationObserver(() => patchCouponButton());
        obs.observe(root, { childList: true, subtree: true });

        // Captura global del clic para bloquear la acción original
        document.addEventListener('click', onGlobalClick, { capture: true });
    }

    domReady(start);
});
