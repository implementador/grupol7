/** @odoo-module **/

// Renombra "Nota de cliente" -> "Cupón QR" sin concatenar (una vez)
odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    "use strict";

    const LABEL = "Cupón QR";
    const ICON_CLASS = "fa fa-qrcode"; // si FontAwesome está disponible en POS

    function patchOnce() {
        const container = document.querySelector('.control-buttons');
        if (!container) return;

        // Busca el botón por texto (nota / note) para Odoo 16
        const btn = [...container.querySelectorAll('.control-button')].find((b) => {
            const t = (b.querySelector('span')?.textContent || '').trim().toLowerCase();
            return /nota|note/.test(t);
        });
        if (!btn || btn.dataset.g7Patched === "1") return;

        // Sustituir el contenido de texto SIN concatenar
        const span = btn.querySelector('span');
        if (span) span.textContent = LABEL;

        // (Opcional) icono QR al inicio si no existe
        if (!btn.querySelector('i')) {
            const i = document.createElement('i');
            i.className = ICON_CLASS;
            i.style.marginRight = '6px';
            btn.insertBefore(i, btn.firstChild);
        }

        // Marca para no repetir
        btn.dataset.g7Patched = "1";
    }

    // Intenta ya y observa cambios futuros del DOM
    function start() {
        patchOnce();
        const root = document.querySelector('.pos-content') || document.body;
        const obs = new MutationObserver(() => patchOnce());
        obs.observe(root, { childList: true, subtree: true });
    }

    if (document.readyState !== 'loading') start();
    else window.addEventListener('DOMContentLoaded', start);
});
