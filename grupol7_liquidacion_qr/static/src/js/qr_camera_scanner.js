odoo.define('grupol7_liquidacion_qr.qr_camera_scanner', function (require) {
    'use strict';

    // Utilidad: obtener config_id desde la URL (POS)
    function getPosConfigIdFromUrl() {
        try { return Number(new URLSearchParams(location.search).get('config_id')) || null; }
        catch(_) { return null; }
    }

    // Overlay simple de cámara
    function createOverlay() {
        const wrap = document.createElement('div');
        wrap.id = 'g7qr-overlay';
        wrap.style.cssText = `
            position:fixed; inset:0; background:rgba(0,0,0,.75); z-index:99999;
            display:flex; align-items:center; justify-content:center;`;
        wrap.innerHTML = `
          <div style="position:relative; width:min(92vw,560px); max-width:560px; background:#111; border-radius:12px; padding:12px;">
            <video id="g7qr-video" autoplay playsinline style="width:100%; border-radius:8px; background:#000;"></video>
            <div style="position:absolute; top:20px; right:20px;">
              <button id="g7qr-close" class="btn btn-secondary" style="cursor:pointer">Cerrar</button>
            </div>
            <div style="color:#fff; opacity:.8; margin-top:8px; text-align:center;">Apunta la cámara al código QR…</div>
          </div>`;
        document.body.appendChild(wrap);
        return wrap;
    }

    async function openScanner() {
        return new Promise(async (resolve) => {
            // Fallback a entrada manual si no hay soporte
            const hasBarcode = 'BarcodeDetector' in window;
            if (!hasBarcode) {
                const manual = window.prompt('Lector no disponible en este navegador. Escribe/pega el código del cupón:');
                return resolve((manual || '').trim() || null);
            }

            const overlay = createOverlay();
            const video = overlay.querySelector('#g7qr-video');
            const btnClose = overlay.querySelector('#g7qr-close');

            let stream;
            let stop = () => {};

            btnClose.onclick = () => { stop(); resolve(null); };

            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
                video.srcObject = stream;

                const detector = new window.BarcodeDetector({ formats: ['qr_code'] });

                let cancelled = false;
                stop = () => {
                    cancelled = true;
                    try { stream?.getTracks()?.forEach(t => t.stop()); } catch(_){}
                    overlay.remove();
                };

                const scanLoop = async () => {
                    if (cancelled) return;
                    try {
                        const codes = await detector.detect(video);
                        if (codes && codes.length) {
                            const code = (codes[0].rawValue || '').trim();
                            stop();
                            return resolve(code || null);
                        }
                    } catch (_){ /* ignore frame errors */ }
                    requestAnimationFrame(scanLoop);
                };
                requestAnimationFrame(scanLoop);
            } catch (err) {
                // Sin cámara o permisos denegados: pedir manual
                overlay.remove();
                const manual = window.prompt('No se pudo abrir la cámara. Escribe/pega el código del cupón:');
                resolve((manual || '').trim() || null);
            }
        });
    }

    // Validación contra el backend (misma que el flujo anterior) vía /web/dataset/call_kw
    async function validateCoupon(code, pos_config_id) {
        const payload = {
            jsonrpc: '2.0',
            method: 'call',
            params: {
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [code, pos_config_id],
                kwargs: {},
            },
            id: Date.now()
        };
        const resp = await fetch('/web/dataset/call_kw/liquidation.coupon/pos_validate_coupon', {
            method: 'POST',
            headers: { 'Content-Type':'application/json' },
            body: JSON.stringify(payload),
            credentials: 'same-origin',
        });
        const data = await resp.json();
        if (data.error) throw new Error(data.error.data?.message || 'Error de validación');
        return data.result;
    }

    async function onCouponClick(ev) {
        const btn = ev.target.closest('.control-buttons .control-button[data-g7CouponButton="1"]');
        if (!btn) return;

        // Bloquear acción original
        ev.preventDefault();
        ev.stopImmediatePropagation();

        const code = await openScanner();
        if (!code) return;

        const pos_config_id = getPosConfigIdFromUrl();
        try {
            const info = await validateCoupon(code, pos_config_id);
            // Aquí sólo informamos (agregar automático puede depender del stock/ubicación)
            const lines = [
                `Cupón OK: ${code}`,
                info?.info ? String(info.info) : '',
                info?.price != null ? `Precio: ${info.price}` : '',
            ].filter(Boolean);
            window.alert(lines.join('\n') || 'Cupón validado.');
            // Si más adelante quieres auto-agregar la línea al ticket, lo conectamos.
        } catch (e) {
            window.alert(e.message || 'Cupón inválido.');
        }
    }

    function bindHandler() {
        if (window.__g7CouponBound) return;
        window.__g7CouponBound = true;
        // Captura en fase de captura para adelantarnos a otros listeners
        document.addEventListener('click', onCouponClick, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindHandler, { once:true });
    } else {
        bindHandler();
    }
});
