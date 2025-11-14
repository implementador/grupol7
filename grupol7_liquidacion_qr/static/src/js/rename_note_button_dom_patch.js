odoo.define('grupol7_liquidacion_qr.rename_note_button_dom_patch', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');
    const rpc = require('web.rpc');

    let couponMode = false;
    let buffer = '';
    let timer = null;
    const INTERVAL_MS = 50; // tiempo máximo entre teclas para considerar “escáner”
    const posConfigId = (new URLSearchParams(location.search)).get('config_id');

    function setCouponMode(on) {
        couponMode = !!on;
        const btn = findNoteButton();
        if (btn) {
            btn.classList.toggle('coupon-mode-on', couponMode);
        }
        notify(couponMode ? 'Modo Cupón QR: ACTIVADO' : 'Modo Cupón QR: DESACTIVADO');
        buffer = '';
        if (!couponMode && timer) { clearTimeout(timer); timer = null; }
    }

    function notify(msg) {
        try {
            // pequeño aviso no intrusivo
            let n = document.getElementById('g7-coupon-hint');
            if (!n) {
                n = document.createElement('div');
                n.id = 'g7-coupon-hint';
                n.style.cssText = 'position:fixed;left:12px;bottom:12px;background:#262626;color:#fff;padding:8px 12px;border-radius:8px;z-index:99999;font:12px/14px sans-serif;opacity:.95';
                document.body.appendChild(n);
            }
            n.textContent = msg;
            n.style.display = 'block';
            setTimeout(()=>{ n.style.display='none'; }, 2000);
        } catch(e){ /* no-op */ }
    }

    function findNoteButton(root=document) {
        // localiza el botón “Nota de cliente” por su icono o texto
        const btns = root.querySelectorAll('div.control-button');
        for (const b of btns) {
            const icon = b.querySelector('i');
            const txt = (b.textContent || '').trim();
            const title = (b.getAttribute('title') || '') + ' ' + (b.getAttribute('aria-label') || '');
            const looksLikeNote = (icon && icon.classList.contains('fa-sticky-note'))
                               || /nota de cliente|customer note/i.test(txt)
                               || /nota de cliente|customer note/i.test(title);
            if (looksLikeNote) return b;
        }
        return null;
    }

    function renameAndWire(root=document) {
        const btn = findNoteButton(root);
        if (!btn) return;

        // sobrescribe el label (no concatena)
        const icon = btn.querySelector('i');
        const labelEl = btn.querySelector('span');
        if (icon) icon.className = 'fa fa-qrcode';
        if (labelEl) labelEl.textContent = 'Cupón QR';
        btn.setAttribute('title', 'Cupón QR');
        btn.setAttribute('aria-label', 'Cupón QR');

        // Click = toggle modo cupón
        if (!btn.dataset.g7CouponBound) {
            btn.addEventListener('click', (ev) => {
                ev.preventDefault();
                setCouponMode(!couponMode);
            });
            btn.dataset.g7CouponBound = '1';
        }
    }

    function handleKeypress(e) {
        if (!couponMode) return;

        const ch = e.key || '';
        // Enter finaliza
        if (ch === 'Enter') {
            const code = buffer.trim();
            buffer = '';
            if (timer) { clearTimeout(timer); timer = null; }
            if (code) validateCoupon(code);
            return;
        }

        // Solo caracteres “visibles”
        if (ch.length === 1) {
            buffer += ch;
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => { buffer = ''; }, INTERVAL_MS * 3);
        }
    }

    async function validateCoupon(code) {
        try {
            notify('Validando cupón…');
            const res = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [code, Number(posConfigId)],
            });
            // res: {product_id, price, name, ...}
            notify(`Válido: ${res.name} - $${Number(res.price).toFixed(2)}`);
            // Próximo paso (siguiente iteración): agregar a la orden y bloquear precio
            // usando res.product_id y res.price
        } catch (err) {
            const msg = (err && err.message) ? err.message : (''+err);
            notify(`Cupón inválido: ${msg}`);
        } finally {
            // si quieres apagar el modo tras un escaneo correcto, descomenta:
            // setCouponMode(false);
        }
    }

    function start() {
        const posRoot = document.querySelector('.pos');
        if (!posRoot) { setTimeout(start, 300); return; }
        renameAndWire(posRoot);

        // reintenta por si el layout re-renderiza
        const mo = new MutationObserver(() => renameAndWire(posRoot));
        mo.observe(posRoot, { childList: true, subtree: true });

        // escucha el escáner (teclas)
        window.addEventListener('keydown', handleKeypress, true);
    }

    domReady(start);
});
