odoo.define('grupol7_liquidacion_qr.qr_dom_patch', function (require) {
    'use strict';
    function patch() {
        try {
            const icon = document.querySelector('.control-button i.fa-sticky-note');
            if (!icon) return;
            const btn = icon.closest('.control-button');
            if (!btn) return;

            // Icono a QR
            try { icon.classList.remove('fa-sticky-note'); icon.classList.add('fa-qrcode'); } catch(e){}

            // Quitar cualquier etiqueta previa (todo hijo directo que NO sea el contenedor del icono)
            Array.from(btn.children).forEach(ch => {
                if (!ch.querySelector || !ch.querySelector('i')) {
                    btn.removeChild(ch);
                }
            });

            // Poner nuestro label desde cero
            const label = document.createElement('span');
            label.className = 'label';
            label.textContent = 'Cupón QR';
            btn.appendChild(label);

            // Click seguro: sólo alterna modo (aún sin validar cupon)
            if (!btn.dataset.qrBound) {
                btn.dataset.qrBound = '1';
                btn.addEventListener('click', () => {
                    window.__qr_mode = !window.__qr_mode;
                    alert(window.__qr_mode ? 'Modo Cupón QR ACTIVADO' : 'Modo Cupón QR DESACTIVADO');
                });
            }
        } catch (e) {}
    }
    document.addEventListener('DOMContentLoaded', patch);
    new MutationObserver(patch).observe(document.documentElement, {childList:true, subtree:true});
});
