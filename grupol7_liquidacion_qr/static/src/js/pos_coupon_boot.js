/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET */
(function () {
  const LOG = (...a) => console.log('[G7][POS-Coupon]', ...a);

  function patchButton() {
    const holder = document.querySelector('.control-buttons');
    if (!holder) return;

    // Buscar el botón por su label original (Nota de cliente)
    const btn = [...holder.querySelectorAll('.control-button')]
      .find(b => /Nota\s+de\s+cliente/i.test(b.textContent || ''));

    if (!btn || btn.dataset.g7Patched === '1') return;

    // Marcar para no parchar 2 veces
    btn.dataset.g7Patched = '1';
    btn.dataset.g7CouponButton = '1';

    // Icono QR
    let icon = btn.querySelector('i.fa, .fa') || btn.querySelector('i');
    if (!icon) { icon = document.createElement('i'); btn.prepend(icon); }
    icon.className = 'fa fa-qrcode';

    // Texto exacto (reemplaza, no concatena)
    let label = btn.querySelector('span');
    if (!label) { label = document.createElement('span'); btn.appendChild(label); }
    label.textContent = 'Cupón QR';

    LOG('Botón parcheado');
  }

  // Observar el DOM para re-parchar si Odoo re-renderiza
  const mo = new MutationObserver(() => patchButton());
  mo.observe(document.documentElement, { childList:true, subtree:true });

  // Intentos iniciales
  window.addEventListener('load', patchButton);
  setTimeout(patchButton, 50);
  setTimeout(patchButton, 300);
  setTimeout(patchButton, 1200);

  // Capturar el clic del botón
  document.addEventListener('click', function (e) {
    const el = e.target && e.target.closest('.control-buttons .control-button[data-g7CouponButton="1"]');
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();
    LOG('CLICK Cupón QR capturado');
    // Aquí luego llamamos a lectura/validación real:
    alert('Cupón QR: click capturado (sonda)');
  }, { capture:true });

  // Dejar una marca global para verificar carga
  window.G7_POS_COUPON_ASSET = 'OK';
  LOG('Asset cargado (G7_PROBE)');
})();
