odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';

    function patchOnce() {
        const buttons = document.querySelectorAll('.control-buttons .control-button');
        for (const btn of buttons) {
            const label = btn.querySelector('.button-text');
            if (!label) continue;

            const text = (label.textContent || '').trim();
            const isNote = /^nota de cliente$/i.test(text);
            const isAlready = /^cupón qr$/i.test(text);

            if (isNote || isAlready) {
                // Texto y icono
                label.textContent = 'Cupón QR';
                const icon = btn.querySelector('i');
                if (icon) icon.className = 'fa fa-qrcode';

                // Marca que este es nuestro botón
                btn.dataset.g7CouponButton = '1';
                btn.setAttribute('title', 'Escanear cupón QR');
            }
        }
    }

    function start() {
        // Ejecuta ya y durante unos segundos (por si POS re-renderiza)
        patchOnce();
        const id = setInterval(patchOnce, 800);
        setTimeout(() => clearInterval(id), 15000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
});
