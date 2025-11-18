// Parche DOM: reemplaza el texto del botón "Nota de cliente" por "Cupón QR" (sin concatenar)
odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';

    const desired = 'Cupón QR';

    // Detecta el botón por su texto original (multi-idioma) y lo renombra SIN concatenar
    function isNoteButton(el) {
        const t = (el.textContent || '').trim().toLowerCase();
        return /nota de cliente|customer note|note client|kundenhinweis|cliente nota|cliente note/.test(t);
    }

    function rewrite(btn) {
        if (!btn || btn.dataset.g7Renamed === '1') return;
        // Usa el contenedor de la etiqueta si existe
        const label = btn.querySelector('.label') || btn;

        // Limpia cualquier texto previo (evita concatenación)
        while (label.firstChild) label.removeChild(label.firstChild);

        // Escribe SOLO el nuevo texto
        label.appendChild(document.createTextNode(desired));

        // Marca para no repetir
        btn.dataset.g7Renamed = '1';
    }

    function scan() {
        document.querySelectorAll('.control-buttons .control-button').forEach((btn) => {
            if (isNoteButton(btn)) rewrite(btn);
        });
    }

    // 1) Primer intento cuando carga
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scan, { once: true });
    } else {
        scan();
    }

    // 2) Observa re-renderizados del POS y reaplica si aparece de nuevo
    const mo = new MutationObserver(() => scan());
    mo.observe(document.body, { childList: true, subtree: true });
});
