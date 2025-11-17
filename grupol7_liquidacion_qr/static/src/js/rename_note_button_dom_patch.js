/**
 * Renombra el botón "Nota de cliente" -> "Cupón QR" sin concatenar.
 * Seguro ante recargas/OWL re-renders gracias a MutationObserver.
 * No toca la acción ni los handlers originales.
 */
(function () {
  function renameOnce(root) {
    (root || document).querySelectorAll('.control-buttons .control-button').forEach((btn) => {
      const label = btn.querySelector('span') || btn.querySelector('.control-button-label');
      if (!label) return;

      const txt = (label.textContent || '').trim();
      const isNote = txt === 'Nota de cliente' || txt === 'Note';

      if (isNote && btn.dataset.g7renamed !== '1') {
        label.textContent = 'Cupón QR';   // <-- REEMPLAZA (no "+=")
        btn.dataset.g7renamed = '1';
      }
    });
  }

  // Al cargar
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => renameOnce(document));
  } else {
    renameOnce(document);
  }

  // Ante cambios en el DOM del POS
  try {
    const mo = new MutationObserver(() => renameOnce(document));
    mo.observe(document.body, { childList: true, subtree: true });
  } catch (e) {
    // En caso extremo, un fallback cada 1.5s (no debería ser necesario)
    setInterval(() => renameOnce(document), 1500);
  }
})();
