/** @odoo-module **/
/* G7_PROBE_COUPON_BACKEND */
(function () {
  const LOG = (...args) => console.log('[G7][POS-Coupon][BACKEND]', ...args);

  function captureCouponFromBackend() {
    const form = document.querySelector('.o_form_view');
    if (!form) {
      return;
    }

    // Evitar repetir en el mismo formulario
    if (form.dataset.g7CouponPrepared === '1') {
      return;
    }

    // Comprobar que de verdad estamos en "Cupones de liquidación"
    const breadcrumb = document.querySelector('.o_breadcrumb');
    const bcText = (breadcrumb && breadcrumb.textContent) ? breadcrumb.textContent.replace(/\s+/g, ' ').trim() : '';
    if (!/Cupon(es)?\s+de\s+liquid/i.test(bcText)) {
      return;
    }

    // Tomar el código del cupón (campo code o name)
    const codeEl = form.querySelector('[name="code"], [name="name"]');
    if (!codeEl) {
      LOG('No se encontró campo [name="code"] ni [name="name"].');
      return;
    }
    const rawCode = (codeEl.value || codeEl.textContent || '').trim();
    if (!rawCode) {
      LOG('Campo de código vacío.');
      return;
    }

    const resId = form.getAttribute('data-res-id') || null;
    const payload = {
      id: resId ? (parseInt(resId, 10) || resId) : null,
      code: rawCode,
      ts: Date.now(),
    };

    try {
      localStorage.setItem('g7_liquidation_coupon', JSON.stringify(payload));
      form.dataset.g7CouponPrepared = '1';
      LOG('Cupón de liquidación preparado para POS:', payload);
    } catch (e) {
      console.error('[G7][POS-Coupon][BACKEND] Error guardando en localStorage:', e);
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

  try {
    initBackendWatcher();
  } catch (e) {
    console.error('[G7][POS-Coupon][BACKEND] Error iniciando watcher:', e);
  }
})();
