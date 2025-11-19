/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET */
(function () {
  const LOG = (...a) => console.log('[G7][POS-Coupon]', ...a);

  // Aquí centralizamos qué hacer con el texto leído del QR
  function handleQrText(qrText) {
    LOG('QR detectado (handleQrText):', qrText);
    alert('QR leído:\n\n' + qrText);
    // TODO: aplicar cupón al pedido actual usando el texto del QR.
  }

  function startQrScan() {
    LOG('Iniciando escaneo QR');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Este navegador no permite usar la cámara (getUserMedia). Prueba en Chrome/Edge actualizados.');
      return;
    }

    const video = document.createElement('video');
    video.setAttribute('autoplay', '');
    video.setAttribute('playsinline', '');

    // Overlay oscuro encima del POS
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

    const label = document.createElement('div');
    label.textContent = 'Apunta la cámara al código QR';
    label.style.color = 'white';
    label.style.marginBottom = '12px';
    label.style.fontSize = '18px';

    const closeBtn = document.createElement('button');
    closeBtn.textContent = 'Cancelar';
    closeBtn.style.marginTop = '12px';
    closeBtn.style.padding = '6px 16px';
    closeBtn.style.fontSize = '16px';

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

      const hasNativeDetector = 'BarcodeDetector' in window;
      let detector = null;
      if (hasNativeDetector) {
        try {
          detector = new BarcodeDetector({ formats: ['qr_code'] });
        } catch (e) {
          console.error('[G7][POS-Coupon] Error creando BarcodeDetector:', e);
          detector = null;
        }
      }

      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');

      // Escaneo usando la API nativa (si existe)
      const scanLoopNative = function () {
        if (!scanning || !detector) {
          return;
        }
        detector.detect(video).then(function (barcodes) {
          if (barcodes && barcodes.length > 0) {
            const qrText = barcodes[0].rawValue || '';
            handleQrText(qrText);
            stopScanning();
            return;
          }
          requestAnimationFrame(scanLoopNative);
        }).catch(function (err) {
          console.error('[G7][POS-Coupon] Error en detector QR (nativo):', err);
          requestAnimationFrame(scanLoopNative);
        });
      };

      // Escaneo usando jsQR (fallback cuando no hay BarcodeDetector)
      const scanLoopJsQr = function () {
        if (!scanning || !window.jsQR) {
          return;
        }

        try {
          if (video.readyState !== video.HAVE_ENOUGH_DATA) {
            requestAnimationFrame(scanLoopJsQr);
            return;
          }

          const vw = video.videoWidth || 640;
          const vh = video.videoHeight || 480;
          if (!vw || !vh) {
            requestAnimationFrame(scanLoopJsQr);
            return;
          }

          canvas.width = vw;
          canvas.height = vh;
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

          const code = window.jsQR(imageData.data, canvas.width, canvas.height);
          if (code && code.data) {
            const qrText = code.data;
            handleQrText(qrText);
            stopScanning();
            return;
          }
        } catch (err) {
          console.error('[G7][POS-Coupon] Error en scanLoopJsQr:', err);
        }

        requestAnimationFrame(scanLoopJsQr);
      };

      const startScanning = function () {
        if (detector) {
          LOG('Usando BarcodeDetector nativo para QR');
          requestAnimationFrame(scanLoopNative);
        } else if (window.jsQR) {
          LOG('Usando jsQR ya cargado');
          requestAnimationFrame(scanLoopJsQr);
        } else {
          LOG('Cargando librería jsQR desde CDN');
          const script = document.createElement('script');
          script.src = 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js';
          script.async = true;
          script.onload = function () {
            LOG('Librería jsQR cargada');
            if (!scanning) {
              return;
            }
            requestAnimationFrame(scanLoopJsQr);
          };
          script.onerror = function () {
            console.error('[G7][POS-Coupon] No se pudo cargar jsQR');
            alert('No se pudo cargar la librería de lectura QR (jsQR).');
            stopScanning();
          };
          document.head.appendChild(script);
        }
      };

      video.onloadedmetadata = function () {
        video.play();
        startScanning();
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

    const btn = [].slice.call(holder.querySelectorAll('.control-button'))
      .find(function (b) {
        return /Nota\s+de\s+cliente/i.test((b.textContent || '').trim());
      });
    if (!btn) return;

    if (btn.dataset.g7Patched === '1') return;
    btn.dataset.g7Patched = '1';

    btn.setAttribute('data-g7-coupon-button', '1');
    btn.dataset.g7CouponButton = '1';

    let icon = btn.querySelector('i.fa, i');
    if (!icon) {
      icon = document.createElement('i');
      btn.prepend(icon);
    }
    icon.className = 'fa fa-qrcode';

    let label = btn.querySelector('span');
    if (!label) {
      label = document.createElement('span');
      btn.appendChild(label);
    }
    label.textContent = 'Cupón QR';

    LOG('Botón parcheado');
  }

  // Re-parchar en re-render
  const mo = new MutationObserver(function () {
    patchButton();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('load', patchButton);
  setTimeout(patchButton, 50);
  setTimeout(patchButton, 300);
  setTimeout(patchButton, 1200);

  // Capturar clic del botón
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
