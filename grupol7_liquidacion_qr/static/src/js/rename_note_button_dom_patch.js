odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';

    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');

    const RenameNoteButtonPatch = (ProductScreen) => class extends ProductScreen {
        mounted() {
            super.mounted(...arguments);
            this._applyRename();
            // Observa cambios en el DOM para re-aplicar si OWL re-renderiza
            this._qrObserver = new MutationObserver(() => this._applyRename());
            this._qrObserver.observe(this.el, { childList: true, subtree: true });
        }
        willUnmount() {
            if (this._qrObserver) this._qrObserver.disconnect();
            super.willUnmount(...arguments);
        }
        _applyRename() {
            const root = this.el;
            if (!root) return;
            // Busca el botón por sus atributos originales
            const candidates = root.querySelectorAll('div.control-button[title], div.control-button[aria-label]');
            for (const btn of candidates) {
                const label = ((btn.getAttribute('title') || btn.getAttribute('aria-label') || '') + '').toLowerCase();
                if (label.includes('customer note') || label.includes('nota de cliente')) {
                    // Cambia texto
                    const span = btn.querySelector('span');
                    if (span && span.textContent !== 'Cupón QR') span.textContent = 'Cupón QR';
                    // Cambia ícono
                    const ico = btn.querySelector('i');
                    if (ico && !ico.classList.contains('fa-qrcode')) {
                        ico.className = 'fa fa-qrcode';
                    }
                    // Cambia atributos accesibles
                    btn.setAttribute('title', 'Cupón QR');
                    btn.setAttribute('aria-label', 'Cupón QR');
                }
            }
        }
    };

    Registries.Component.extend(ProductScreen, RenameNoteButtonPatch);
});
