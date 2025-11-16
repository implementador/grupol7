odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';

    function patchOnce() {
        const btns = document.querySelectorAll('.control-buttons button');
        for (const btn of btns) {
            if (btn.dataset.g7Renamed) continue;

            // Botón original: icono .fa-sticky-note + span.control-button-label
            const icon = btn.querySelector('i.fa-sticky-note, i.fa.fa-sticky-note');
            const label = btn.querySelector('span.control-button-label');

            // Aseguramos que sea el botón de Nota de cliente
            const isNote = !!icon || (label && /nota de cliente|customer note/i.test(label.textContent || ''));
            if (!isNote) continue;

            // Renombrar SIN concatenar (reemplazamos contenido exacto)
            if (icon) {
                icon.className = 'fa fa-qrcode';
                icon.setAttribute('aria-label', 'Cupón QR');
            }
            if (label) {
                label.textContent = 'Cupón QR';
            }
            btn.setAttribute('aria-label', 'Cupón QR');

            // Marcar para que no se repita
            btn.dataset.g7Renamed = '1';
        }
    }

    function arm() {
        patchOnce();
        if (window.MutationObserver && document.body) {
            try {
                const mo = new MutationObserver(() => patchOnce());
                mo.observe(document.body, { childList: true, subtree: true });
            } catch (_) {}
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arm, { once: true });
    } else if (document.body) {
        arm();
    } else {
        window.addEventListener('load', arm, { once: true });
    }
});
