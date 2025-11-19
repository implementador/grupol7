odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');

    function patchOnce(area) {
        // Busca el botón "Nota de cliente"
        const btn = [...area.querySelectorAll('.control-button')].find(
            (b) => /Nota\s+de\s+cliente/i.test(b.textContent.trim())
        );
        if (!btn || btn.dataset.g7CouponButton === '1') {
            return;
        }
        // Marcas internas para que no se repita
        btn.dataset.g7CouponButton = '1';
        btn.classList.add('g7-coupon-button');

        // Ícono
        const icon = btn.querySelector('i') || btn.querySelector('.fa');
        if (icon) icon.className = 'fa fa-qrcode';

        // Texto (REEMPLAZO, NO concatenar)
        // El texto suele ir en un <span>, pero si no, usamos el botón directo
        const label = btn.querySelector('span') || btn;
        label.textContent = 'Cupón QR';
    }

    function init() {
        const area = document.querySelector('.control-buttons');
        if (!area) return;
        // Primer intento inmediato
        patchOnce(area);
        // Y observar cambios del DOM
        const obs = new MutationObserver(() => patchOnce(area));
        obs.observe(area, { childList: true, subtree: true });
    }

    domReady(init);
});
