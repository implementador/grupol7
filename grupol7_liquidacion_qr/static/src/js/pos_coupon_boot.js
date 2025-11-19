/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET */
(function () {
  const LOG = (...a) => console.log('[G7][POS-Coupon]', ...a);

  function patchButton() {
    const holder = document.querySelector('.control-buttons');
    if (!holder) return;

    // Ubicar el botón original (antes "Nota de cliente")
    const btn = [...holder.querySelectorAll('.control-button')]
      .find(b => /Nota\s+de\s+cliente/i.test(b.textContent || ''));
    if (!btn) return;

    // Evitar parches duplicados
    if (btn.dataset.g7Patched === '1') return;
    btn.dataset.g7Patched = '1';

    // Marcar con atributo visible en el DOM
    btn.setAttribute('data-g7-coupon-button', '1');
    btn.dataset.g7CouponButton = '1';

    // Icono QR
    let icon = btn.querySelector('i.fa, i');
    if (!icon) {
      icon = document.createElement('i');
      btn.prepend(icon);
    }
    icon.className = 'fa fa-qrcode';

    // Texto exacto
    let label = btn.querySelector('span');
    if (!label) {
      label = document.createElement('span');
      btn.appendChild(label);
    }
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

  // Capturar clic del botón
  document.addEventListener('click', function (e) {
    const el = e.target && e.target.closest('.control-buttons .control-button[data-g7-coupon-button="1"]');
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();
    LOG('CLICK Cupón QR capturado');
    alert('Cupón QR: click capturado (sonda)');
  }, { capture: true });

  window.G7_POS_COUPON_ASSET = 'OK';
  LOG('Asset cargado (G7_PROBE)');
})();
