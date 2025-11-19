/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET */
(function () {
  const LOG = (...a) => console.log('[G7][POS-Coupon]', ...a);

  function patchButton() {
    const holder = document.querySelector('.control-buttons');
    if (!holder) return;

    // Buscar el botón original (Nota de cliente) o el que ya se haya renombrado
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

    // Evitar parches duplicados
    if (btn.dataset.g7Patched === '1') return;
    btn.dataset.g7Patched = '1';

    // Marcar con atributo para el click
    btn.setAttribute('data-g7-coupon-button', '1');

    // Icono QR
    let icon = btn.querySelector('i.fa, i');
    if (!icon) {
      icon = document.createElement('i');
      btn.prepend(icon);
    }
    icon.className = 'fa fa-qrcode';

    // Texto "Cupón QR"
    let label = btn.querySelector('span');
    if (!label) {
      label = document.createElement('span');
      btn.appendChild(label);
    }
    label.textContent = 'Cupón QR';

    LOG('Botón parcheado');
  }

  // Observar re-render del POS
  const mo = new MutationObserver(function () {
    patchButton();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('load', patchButton);
  setTimeout(patchButton, 50);
  setTimeout(patchButton, 300);
  setTimeout(patchButton, 1200);

  // Capturar clic en el botón
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
      alert('Cupón QR: click capturado (sonda)');
    },
    { capture: true }
  );

  window.G7_POS_COUPON_ASSET = 'OK';
  LOG('Asset cargado (G7_PROBE simple)');
})();
