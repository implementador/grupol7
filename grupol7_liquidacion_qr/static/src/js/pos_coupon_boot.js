/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET (POS) */
(function () {
  const LOG = (...args) => console.log('[G7][POS-Coupon][POS]', ...args);

  // -------------------------------------------------------------
  // Leer el cupón preparado por el backend desde localStorage
  // -------------------------------------------------------------
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
      console.error('[G7][POS-Coupon][POS] Error leyendo localStorage:', e);
      return null;
    }
  }

  // Acción cuando el cajero pulsa "Cupón QR"
  function useCouponInPos() {
    const coupon = getPreparedCoupon();
    if (!coupon) {
      alert(
        'No hay ningún Cupón de liquidación preparado.\n\n' +
        '1) En otra pestaña, abre el menú "Cupones de liquidación".\n' +
        '2) Abre el cupón que quieres usar.\n' +
        '3) Regresa a este POS y vuelve a pulsar "Cupón QR".'
      );
      return;
    }

    const lines = [
      'Cupón de liquidación encontrado:',
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

    alert(lines.join('\n'));

    LOG('Cupón utilizado en POS:', coupon);

    // TODO: aquí, en vez del alert, aplicaremos el descuento / producto en el pedido.
  }

  // -------------------------------------------------------------
  // Parchear el botón del POS (Nota de cliente -> Cupón QR)
  // -------------------------------------------------------------
  function patchButton() {
    const holder = document.querySelector('.control-buttons');
    if (!holder) return;

    const buttons = holder.querySelectorAll('.control-button');
    let btn = null;
    for (let i = 0; i < buttons.length; i++) {
      const b = buttons[i];
      const txt = (b.textContent || '').trim();
      if (/Nota\s+de\s+cliente/i.test(txt) || /Cup[oó]n\s*QR/i.test(txt)) {
        btn = b;
        break;
      }
    }
    if (!btn) return;

    if (btn.dataset.g7Patched === '1') return;
    btn.dataset.g7Patched = '1';

    btn.setAttribute('data-g7-coupon-button', '1');

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

  // Observar re-render del POS y aplicar patch
  const mo = new MutationObserver(() => {
    patchButton();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('load', patchButton);
  setTimeout(patchButton, 50);
  setTimeout(patchButton, 300);
  setTimeout(patchButton, 1200);

  // Capturar clic del botón
  document.addEventListener(
    'click',
    function (e) {
      const el =
        e.target &&
        e.target.closest('.control-buttons .control-button[data-g7-coupon-button="1"]');
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      LOG('CLICK Cupón QR capturado');
      useCouponInPos();
    },
    { capture: true }
  );

  window.G7_POS_COUPON_ASSET = 'OK';
  LOG('Asset POS cargado (bridge localStorage)');
})();
