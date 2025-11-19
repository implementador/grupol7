/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET */
(function () {
  const LOG = (...a) => console.log('[G7][POS-Coupon]', ...a);

  // ---------------------------------------------------------------------------
  // BACKEND: detectar el cupón de liquidación abierto y guardarlo en localStorage
  // ---------------------------------------------------------------------------
  function captureCouponFromBackend() {
    const form = document.querySelector('.o_form_view');
    if (!form) return;

    // Evitar repetir en el mismo formulario
    if (form.dataset.g7CouponPrepared === '1') return;

    // Heurística: sólo si estamos en "Cupones de liquidación"
    const breadcrumb = document.querySelector('.o_breadcrumb');
    const bcText = (breadcrumb && breadcrumb.textContent) ? breadcrumb.textContent.trim() : '';
    if (!/Cupon(es)?\s+de\s+liquid/i.test(bcText)) {
      return;
    }

    // Tomar el código: normalmente será name o code
    const codeEl = form.querySelector('[name="code"], [name="name"]');
    if (!codeEl) {
      LOG('No se encontró campo [name="code"] ni [name="name"] en el formulario.');
      return;
    }

    const rawCode = (codeEl.textContent || codeEl.value || '').trim();
    if (!rawCode) {
      LOG('El campo de código está vacío.');
      return;
    }

    const resId = form.getAttribute('data-res-id') || null;
    const payload = {
      id: resId ? parseInt(resId, 10) || resId : null,
      code: rawCode,
      ts: Date.now(),
    };

    try {
      localStorage.setItem('g7_liquidation_coupon', JSON.stringify(payload));
      form.dataset.g7CouponPrepared = '1';
      LOG('Cupón de liquidación preparado para POS:', payload);
    } catch (e) {
      console.error('[G7][POS-Coupon] Error guardando en localStorage:', e);
    }
  }

  function initBackendWatcher() {
    const body = document.body;
    if (!body) return;

    if (body.dataset.g7CouponBackendWatcher === '1') return;
    body.dataset.g7CouponBackendWatcher = '1';

    const mo = new MutationObserver(() => {
      captureCouponFromBackend();
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });

    window.addEventListener('load', captureCouponFromBackend);
    setTimeout(captureCouponFromBackend, 50);
    setTimeout(captureCouponFromBackend, 300);
    setTimeout(captureCouponFromBackend, 1200);

    LOG('Observador backend de cupones iniciado');
  }

  // ---------------------------------------------------------------------------
  // POS: leer el cupón guardado en localStorage y usarlo al hacer clic en Cupón QR
  // ---------------------------------------------------------------------------
  function getPreparedCoupon() {
    try {
      const raw = localStorage.getItem('g7_liquidation_coupon');
      if (!raw) {
        LOG('No hay "g7_liquidation_coupon" en localStorage.');
        return null;
      }
      const data = JSON.parse(raw);
      if (!data || !data.code) {
        LOG('Dato de cupón inválido en localStorage:', data);
        return null;
      }
      return data;
    } catch (e) {
      console.error('[G7][POS-Coupon] Error leyendo localStorage:', e);
      return null;
    }
  }

  function useCouponInPos() {
    const coupon = getPreparedCoupon();
    if (!coupon) {
      alert(
        'No hay ningún Cupón de liquidación preparado.\n\n' +
        'Abre primero el cupón en Odoo (menú de "Cupones de liquidación"), ' +
        'espera a que cargue y luego vuelve a este POS.'
      );
      return;
    }

    const lines = [
      'Cupón de liquidación encontrado',
      '',
      'Código: ' + coupon.code,
    ];
    if (coupon.id) {
      lines.push('ID: ' + coupon.id);
    }
    if (coupon.ts) {
      const fecha = new Date(coupon.ts);
      lines.push('Preparado: ' + fecha.toLocaleString());
    }

    // Por ahora sólo mostramos la info.
    // Después aquí aplicaremos el cupón a la orden del POS.
    alert(lines.join('\n'));

    LOG('Cupón utilizado en POS:', coupon);
  }

  // ---------------------------------------------------------------------------
  // POS: parchear el botón "Nota de cliente" -> "Cupón QR" y enganchar clic
  // ---------------------------------------------------------------------------
  function patchPosButton() {
    const holder = document.querySelector('.control-buttons');
    if (!holder) return;

    const btn = [].slice.call(holder.querySelectorAll('.control-button')).find(function (b) {
      const txt = (b.textContent || '').trim();
      return /Nota\s+de\s+cliente/i.test(txt) || /Cup[oó]n\s*QR/i.test(txt);
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

    LOG('Botón POS parcheado');
  }

  function initPosButtonWatcher() {
    const mo = new MutationObserver(() => patchPosButton());
    mo.observe(document.documentElement, { childList: true, subtree: true });

    window.addEventListener('load', patchPosButton);
    setTimeout(patchPosButton, 50);
    setTimeout(patchPosButton, 300);
    setTimeout(patchPosButton, 1200);

    document.addEventListener('click', function (e) {
      const el = e.target && e.target.closest('.control-buttons .control-button[data-g7-coupon-button="1"]');
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      LOG('CLICK Cupón QR capturado');
      useCouponInPos();
    }, { capture: true });
  }

  // ---------------------------------------------------------------------------
  // Inicialización
  // ---------------------------------------------------------------------------
  try {
    initBackendWatcher();
  } catch (e) {
    console.error('[G7][POS-Coupon] Error iniciando watcher backend:', e);
  }

  try {
    initPosButtonWatcher();
  } catch (e) {
    console.error('[G7][POS-Coupon] Error iniciando watcher POS:', e);
  }

  window.G7_POS_COUPON_ASSET = 'OK';
  LOG('Asset cargado (G7_PROBE v-backend-bridge)');
})();
