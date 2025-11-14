odoo.define('grupol7_liquidacion_qr.qr_button_ux', function (require) {
    'use strict';

    function desenhar() {
        // Toma el botón original (icono de nota)
        const noteIcon = document.querySelector('.control-button i.fa-sticky-note');
        const btn = noteIcon ? noteIcon.closest('.control-button') : null;
        if (!btn || btn.dataset.qrDecorated === '1') return;

        // Reemplaza el contenido por icono + texto (sin concatenaciones residuales)
        btn.innerHTML = '<i class="fa fa-qrcode"></i><span>Cupón QR</span>';
        btn.title = 'Leer cupón QR';
        btn.dataset.qrDecorated = '1';
    }

    document.addEventListener('DOMContentLoaded', desenhar);
    new MutationObserver(desenhar).observe(document.documentElement, { childList: true, subtree: true });
});
