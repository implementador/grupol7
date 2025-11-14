odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');

    function applyRename(root = document) {
        const candidates = root.querySelectorAll('div.control-button[title], div.control-button[aria-label]');
        for (const btn of candidates) {
            const label = ((btn.getAttribute('title') || btn.getAttribute('aria-label') || '') + '').toLowerCase();
            if (label.includes('customer note') || label.includes('nota de cliente')) {
                // Texto visible
                const span = btn.querySelector('span');
                if (span && span.textContent !== 'Cupón QR') span.textContent = 'Cupón QR';
                // Ícono
                const ico = btn.querySelector('i');
                if (ico && !ico.classList.contains('fa-qrcode')) ico.className = 'fa fa-qrcode';
                // A11y/tooltip
                btn.setAttribute('title', 'Cupón QR');
                btn.setAttribute('aria-label', 'Cupón QR');
            }
        }
    }

    function start() {
        // Espera a que exista la app del POS en el DOM
        const root = document.querySelector('.pos');
        if (!root) { setTimeout(start, 300); return; }
        applyRename(root);
        // Reaplica cuando OWL re-renderiza
        const obs = new MutationObserver(() => applyRename(root));
        obs.observe(root, { childList: true, subtree: true });
    }

    domReady(start);
});
