odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';

    const NEW_LABEL = 'Cupón QR';

    function looksLikeNoteLabel(text) {
        const t = (text || '').trim().toLowerCase();
        // Variantes comunes en varios idiomas
        return /^nota de cliente$|^customer note$|^note client$|kundenhinweis|cliente note|nota.*cliente|customer.*note/.test(t);
    }

    function renameOnce() {
        document.querySelectorAll('.control-buttons .control-button').forEach((btn) => {
            if (btn.dataset.g7Renamed === '1') return;

            const label = btn.querySelector('.label') || btn;
            if (!label) return;

            const txt = (label.textContent || '').trim();
            if (looksLikeNoteLabel(txt)) {
                // Limpiar para evitar concatenación
                while (label.firstChild) label.removeChild(label.firstChild);
                label.appendChild(document.createTextNode(NEW_LABEL));
                btn.dataset.g7Renamed = '1';
            }
        });
    }

    function start() {
        renameOnce();
        // Reafirmar cada 1s por si Odoo re-renderiza
        if (!window.__g7CouponRenameInterval) {
            window.__g7CouponRenameInterval = setInterval(renameOnce, 1000);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
});
