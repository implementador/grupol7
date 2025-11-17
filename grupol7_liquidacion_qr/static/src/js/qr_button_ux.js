/**
 * G7 Cupón QR: renombra el botón "Nota" a "Cupón QR" con ícono
 * y captura el click para abrir el prompt del cupón sin disparar la acción original.
 */
(function () {
  const LABEL = 'Cupón QR';
  const ICON_HTML = '<i class="fa fa-qrcode" style="margin-right:6px"></i>';

  // Encuentra candidatos al botón "Nota" (es robusto a traducciones “Nota/Note”)
  function findNoteButtons() {
    const buttons = Array.from(document.querySelectorAll('.control-buttons .control-button, .control-button'));
    return buttons.filter(btn => {
      const txt = (btn.textContent || '').trim().toLowerCase();
      // texto típico en PdV: "Nota", "Nota de cliente", "Note"
      return txt.startsWith('nota') || txt === 'note' || txt.includes('nota de cliente');
    });
  }

  // Aplica el parche a un botón, dejando el DOM limpio (sin concatenaciones)
  function patchButton(btn) {
    if (!btn || btn.dataset.g7QrPatched === '1') return;

    // Evita que se ejecute la acción original (nota)
    btn.addEventListener('click', function (ev) {
      ev.stopImmediatePropagation();
      ev.stopPropagation();
      ev.preventDefault();
      // Prompt súper simple para prueba; si cancelan, no hace nada
      const code = window.prompt('Escanee o escriba el código del cupón:');
      if (!code) return;

      // Marcador: aquí ya puedes llamar a tu RPC de validación como lo teníamos
      // (pos_validate_coupon y luego pos_redeem_coupon). Dejo un alert para que
      // validemos el flujo visual; cuando me digas, lo vuelvo a conectar al RPC.
      alert('Cupón leído: ' + code + '\n(Validación RPC pendiente de re-conectar)');
    }, { capture: true });

    // Limpia cualquier contenido previo y coloca nuestro HTML
    btn.innerHTML = ICON_HTML + '<span class="g7-qr-label">' + LABEL + '</span>';
    btn.title = LABEL;
    btn.dataset.g7QrPatched = '1';
  }

  // Parchea todos los botones candidatos
  function patchAll() {
    const buttons = findNoteButtons();
    if (buttons.length) buttons.forEach(patchButton);
  }

  // 1) Intenta al inicio
  patchAll();

  // 2) Reintentos cortos para cubrir re-render inicial del POS
  let tries = 0;
  const t = setInterval(() => {
    patchAll();
    if (++tries >= 20) clearInterval(t);
  }, 300);

  // 3) Observa cambios grandes en el contenedor del POS (sin romper)
  const root = document.body;
  if (root && window.MutationObserver) {
    const mo = new MutationObserver(() => patchAll());
    mo.observe(root, { childList: true, subtree: true });
  }
})();
