odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');

    function rename(root=document) {
        const btns = root.querySelectorAll('div.control-button');
        for (const btn of btns) {
            const icon = btn.querySelector('i');
            if (!icon) continue;

            const isNote =
                icon.classList.contains('fa-sticky-note') ||           // botón de “Nota de cliente”
                /customer note|nota de cliente/i.test(btn.getAttribute('title')||'') ||
                /customer note|nota de cliente/i.test(btn.getAttribute('aria-label')||'');

            if (isNote) {
                const labelEl = btn.querySelector('span');
                if (labelEl && labelEl.textContent !== 'Cupón QR') labelEl.textContent = 'Cupón QR';
                icon.className = 'fa fa-qrcode';
                btn.setAttribute('title', 'Cupón QR');
                btn.setAttribute('aria-label', 'Cupón QR');
            }
        }
    }

    function start() {
        const posRoot = document.querySelector('.pos');
        if (!posRoot) { setTimeout(start, 300); return; }
        rename(posRoot);
        const mo = new MutationObserver(() => rename(posRoot));
        mo.observe(posRoot, { childList: true, subtree: true });
    }

    domReady(start);
});
