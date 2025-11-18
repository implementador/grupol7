odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';

    const NEW_LABEL = 'Cupón QR';

    function looksLikeNoteLabel(text) {
        const t = (text || '').trim().toLowerCase();
        return /^nota de cliente$|^customer note$|^note client$|kundenhinweis|cliente note|nota.*cliente|customer.*note/.test(t);
    }

    function decorateButton(btn) {
        if (!btn || btn.dataset.g7Renamed === '1') return;
        const label = btn.querySelector('.label') || btn;

        // 1) Texto exacto (sin concatenar)
        while (label.firstChild) label.removeChild(label.firstChild);
        const icon = document.createElement('i');
        icon.className = 'fa fa-qrcode';
        icon.style.marginRight = '6px';
        label.appendChild(icon);
        label.appendChild(document.createTextNode(NEW_LABEL));

        // 2) Marcar para nuestro handler
        btn.dataset.g7Renamed = '1';
        btn.dataset.g7CouponButton = '1';
        // Evitar que el "nota de cliente" original se dispare
        btn.onclick = null;
    }

    function renameOnce() {
        document.querySelectorAll('.control-buttons .control-button').forEach((btn) => {
            const label = btn.querySelector('.label') || btn;
            const txt = (label.textContent || '').trim();
            if (looksLikeNoteLabel(txt) || btn.dataset.g7CouponButton === '1') {
                decorateButton(btn);
            }
        });
    }

    function start() {
        renameOnce();
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
