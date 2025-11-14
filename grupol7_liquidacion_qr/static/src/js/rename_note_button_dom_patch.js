odoo.define('grupol7_liquidacion_qr.qr_dom_patch', function (require) {
    'use strict';
    function safePatch() {
        try {
            // Busca el botón de Nota de cliente por su icono de "sticky-note"
            const icon = document.querySelector('.control-button i.fa-sticky-note');
            if (!icon) return;
            const btn = icon.closest('.control-button');
            if (!btn || btn.dataset.__qr_patched) return;
            btn.dataset.__qr_patched = '1';

            // Cambia icono y texto (sin romper si no existen nodos)
            try { icon.classList.remove('fa-sticky-note'); icon.classList.add('fa-qrcode'); } catch(e){}
            const label = btn.querySelector('.label, span, div');
            if (label) label.textContent = 'Cupón QR';

            // Click: sólo alterna un flag y avisa (nunca revienta)
            btn.addEventListener('click', () => {
                try {
                    window.__qr_mode = !window.__qr_mode;
                    alert(window.__qr_mode ? 'Modo Cupón QR ACTIVADO' : 'Modo Cupón QR DESACTIVADO');
                } catch(e){}
            });
        } catch(e) { /* swallow */ }
    }
    document.addEventListener('DOMContentLoaded', safePatch);
    // Reintenta cuando el DOM cambia (cargas Owl)
    new MutationObserver(safePatch).observe(document.documentElement, {childList:true, subtree:true});
});
