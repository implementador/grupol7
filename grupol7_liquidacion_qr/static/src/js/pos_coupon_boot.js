/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET */
(function () {
  const LOG = (...a) => console.log('[G7][POS-Coupon]', ...a);

  // Lógica de escaneo QR con la cámara
  function startQrScan() {
    LOG('Iniciando escaneo QR');

    // Verificamos soporte de cámara
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Este navegador no permite usar la cámara (getUserMedia). Prueba en Chrome/Edge actualizados.');
      return;
    }

    // Verificamos soporte de BarcodeDetector para QR
    if (!('BarcodeDetector' in window)) {
      alert('Tu navegador no soporta BarcodeDetector para leer QR. Prueba en Chrome/Edge actualizados.');
      return;
    }

    const video = document.createElement('video');
    video.setAttribute('autoplay', '');
    video.setAttribute('playsinline', '');

    // Contenedor oscuro encima del POS
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100vw';
    overlay.style.height = '100vh';
    overlay.style.background = 'rgba(0, 0, 0, 0.75)';
    overlay.style.zIndex = '999999';
    overlay.style.display = 'flex';
    overlay.style.flexDirection = 'column';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';

    // Texto de ayuda
    const label = document.createElement('div');
    label.textContent = 'Apunta la cámara al código QR';
    label.style.color = 'white';
    label.style.marginBottom = '12px';
    label.style.fontSize = '18px';

    // Botón de cerrar
    const closeBtn = document.createElement('button');
    closeBtn.textContent = 'Cancelar';
    closeBtn.style.marginTop = '12px';
    closeBtn.style.padding = '6px 16px';
    closeBtn.style.fontSize = '16px';

    // Estilos de video
    video.style.maxWidth = '90vw';
    video.style.maxHeight = '60vh';
    video.style.borderRadius = '8px';
    video.style.background = 'black';

    overlay.appendChild(label);
    overlay.appendChild(video);
    overlay.appendChild(closeBtn);
    document.body.appendChild(overlay);

    let stream = null;
    let scanning = true;

    const stopScanning = function () {
      scanning = false;
      if (stream) {
        try {
          stream.getTracks().forEach(function (t) { t.stop(); });
        } catch (e) {
          console.error('[G7][POS-Coupon] Error al detener la cámara:', e);
        }
      }
      overlay.remove();
    };

    closeBtn.addEventListener('click', function () {
      LOG('Escaneo cancelado por el usuario');
      stopScanning();
    });

    navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' }
    }).then(function (s) {
      stream = s;
      video.srcObject = stream;

      const detector = new BarcodeDetector({ formats: ['qr_code'] });

      const scanLoop = function () {
        if (!scanning) {
          return;
        }

        detector.detect(video).then(function (barcodes) {
          if (barcodes && barcodes.length > 0) {
            const qrText = barcodes[0].rawValue || '';
            LOG('QR detectado:', qrText);

            // Por ahora sólo mostramos el contenido del QR
            alert('QR leído:\n\n' + qrText);

            // TODO: aquí luego aplicamos el cupón en el pedido actual

            stopScanning();
            return;
          }
          requestAnimationFrame(scanLoop);
        }).catch(function (err) {
          console.error('[G7][POS-Coupon] Error en detector QR:', err);
          requestAnimationFrame(scanLoop);
        });
      };

      video.onloadedmetadata = function () {
        video.play();
        requestAnimationFrame(scanLoop);
      };
    }).catch(function (err) {
      console.error('[G7][POS-Coupon] Error al acceder a la cámara:', err);
      alert('No se pudo abrir la cámara: ' + (err && err.message ? err.message : err));
      stopScanning();
    });
  }

  // Parchear el botón del POS (antes "Nota de cliente")
  function patchButton() {
    const holder = document.querySelector('.control-buttons');
    if (!holder) return;

    const btn = [...holder.querySelectorAll('.control-button')]
      .find(b => /Nota\s+de\s+cliente/i.test(b.textContent || ''));
    if (!btn) return;

    if (btn.dataset.g7Patched === '1') return;
    btn.dataset.g7Patched = '1';

    btn.setAttribute('data-g7-coupon-button', '1');
    btn.dataset.g7CouponButton = '1';

    let icon = btn.querySelector('i.fa, i');
    if (!icon) { icon = document.createElement('i'); btn.prepend(icon); }
    icon.className = 'fa fa-qrcode';

    let label = btn.querySelector('span');
    if (!label) { label = document.createElement('span'); btn.appendChild(label); }
    label.textContent = 'Cupón QR';

    LOG('Botón parcheado');
  }

  // Re-parchar en re-render
  const mo = new MutationObserver(() => patchButton());
  mo.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('load', patchButton);
  setTimeout(patchButton, 50);
  setTimeout(patchButton, 300);
  setTimeout(patchButton, 1200);

  // Capturar clic del botón usando el atributo correcto
  document.addEventListener('click', function (e) {
    const el = e.target && e.target.closest('.control-buttons .control-button[data-g7-coupon-button="1"]');
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();
    LOG('CLICK Cupón QR capturado');
    startQrScan();
  }, { capture: true });

  window.G7_POS_COUPON_ASSET = 'OK';
  LOG('Asset cargado (G7_PROBE)');
})();
