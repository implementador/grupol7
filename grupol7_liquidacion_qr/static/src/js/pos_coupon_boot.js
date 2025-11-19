/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET (POS) */
(function () {
  const LOG = (...args) => console.log('[G7][POS-Coupon][POS]', ...args);

  // -------------------------------------------------------------
  // RPC helper: buscar cupón por código
  // -------------------------------------------------------------
  async function searchCouponByCode(code) {
    const payload = {
      jsonrpc: "2.0",
      method: "call",
      params: {
        model: "liquidation.coupon",
        method: "search_read",
        args: [],
        kwargs: {
          domain: ["|", ["name", "=", code], ["code", "=", code]],
          fields: [
            "name",
            "code",
            "product_id",
            "price_liquidation",
            "liquidation_price",
            "price",
            "state",
            "pos_ids",
            "location_id",
            "redeemed",
            "is_redeemed",
            "canjeado",
          ],
          limit: 1,
        },
      },
      id: Date.now(),
    };

    const resp = await fetch("/web/dataset/call_kw/liquidation.coupon/search_read", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      throw new Error("HTTP " + resp.status);
    }
    const json = await resp.json();
    if (json.error) {
      const msg =
        (json.error.data && json.error.data.message) || json.error.message || "Error RPC";
      throw new Error(msg);
    }
    return json.result || [];
  }

  // -------------------------------------------------------------
  // Ventana para capturar / escanear código de cupón
  // -------------------------------------------------------------
  function openCouponDialog() {
    LOG("Abriendo ventana de Cupón de liquidación");

    const overlay = document.createElement("div");
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100vw";
    overlay.style.height = "100vh";
    overlay.style.background = "rgba(0, 0, 0, 0.75)";
    overlay.style.zIndex = "999999";
    overlay.style.display = "flex";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";

    const box = document.createElement("div");
    box.style.background = "white";
    box.style.borderRadius = "8px";
    box.style.padding = "16px 20px";
    box.style.minWidth = "360px";
    box.style.maxWidth = "480px";
    box.style.boxShadow = "0 4px 12px rgba(0,0,0,0.4)";
    box.style.display = "flex";
    box.style.flexDirection = "column";
    box.style.gap = "8px";

    const title = document.createElement("div");
    title.textContent = "Cupón de liquidación";
    title.style.fontSize = "18px";
    title.style.fontWeight = "bold";
    title.style.marginBottom = "6px";

    const subtitle = document.createElement("div");
    subtitle.textContent = "Escanea o escribe el código del cupón:";
    subtitle.style.fontSize = "14px";

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Ej. sY3WlyUJP19KLA";
    input.autocomplete = "off";
    input.style.padding = "6px 8px";
    input.style.fontSize = "16px";
    input.style.width = "100%";
    input.style.boxSizing = "border-box";

    const msg = document.createElement("div");
    msg.style.fontSize = "13px";
    msg.style.minHeight = "18px";

    const buttonsRow = document.createElement("div");
    buttonsRow.style.display = "flex";
    buttonsRow.style.justifyContent = "flex-end";
    buttonsRow.style.gap = "8px";
    buttonsRow.style.marginTop = "8px";

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancelar";
    cancelBtn.style.padding = "4px 10px";
    cancelBtn.style.fontSize = "14px";

    const okBtn = document.createElement("button");
    okBtn.textContent = "Buscar cupón";
    okBtn.style.padding = "4px 10px";
    okBtn.style.fontSize = "14px";

    buttonsRow.appendChild(cancelBtn);
    buttonsRow.appendChild(okBtn);

    box.appendChild(title);
    box.appendChild(subtitle);
    box.appendChild(input);
    box.appendChild(msg);
    box.appendChild(buttonsRow);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    function closeDialog() {
      overlay.remove();
    }

    cancelBtn.addEventListener("click", function () {
      LOG("Ventana de cupón cancelada por el usuario");
      closeDialog();
    });

    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        okBtn.click();
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        closeDialog();
      }
    });

    okBtn.addEventListener("click", async function () {
      const code = (input.value || "").trim();
      if (!code) {
        msg.textContent = "Captura o escanea un código primero.";
        msg.style.color = "red";
        return;
      }
      msg.textContent = "Buscando cupón...";
      msg.style.color = "#333";

      // id del PdV actual, para validar PdV permitidos
      const urlParams = new URLSearchParams(window.location.search || "");
      const posConfigId = parseInt(urlParams.get("config_id") || "0", 10) || 0;

      let records = [];
      try {
        records = await searchCouponByCode(code);
      } catch (err) {
        console.error("[G7][POS-Coupon][POS] Error RPC:", err);
        msg.textContent = "Error al consultar el cupón. Revisa la consola.";
        msg.style.color = "red";
        return;
      }

      if (!records || !records.length) {
        msg.textContent = "No se encontró ningún cupón con ese código.";
        msg.style.color = "red";
        return;
      }

      const coupon = records[0];
      LOG("Cupón encontrado:", coupon);

      // -------- Validar que NO esté canjeado --------
      const redeemedFlag =
        coupon.redeemed || coupon.is_redeemed || coupon.canjeado;
      const badStates = ["used", "done", "cancel", "expired"];
      if (redeemedFlag) {
        msg.textContent = "Este cupón ya fue canjeado.";
        msg.style.color = "red";
        return;
      }
      if (coupon.state && badStates.indexOf(coupon.state) !== -1) {
        msg.textContent =
          "Este cupón no está disponible (estado: " + coupon.state + ").";
        msg.style.color = "red";
        return;
      }

      // -------- Validar PdV permitidos (campo pos_ids) --------
      if (posConfigId && Array.isArray(coupon.pos_ids) && coupon.pos_ids.length) {
        const allowedIds = coupon.pos_ids.map(function (p) {
          return Array.isArray(p) ? p[0] : p;
        });
        if (allowedIds.indexOf(posConfigId) === -1) {
          msg.textContent = "Este cupón no es válido para este Punto de Venta.";
          msg.style.color = "red";
          return;
        }
      }

      // -------- Mostrar información del cupón (por ahora) --------
      let detail = "Cupón válido.\n\n";
      const codeText = coupon.code || coupon.name || code;
      detail += "Código: " + codeText + "\n";

      if (coupon.product_id) {
        const prodName = Array.isArray(coupon.product_id)
          ? coupon.product_id[1]
          : coupon.product_id;
        detail += "Producto: " + prodName + "\n";
      }

      const price =
        coupon.price_liquidation ||
        coupon.liquidation_price ||
        coupon.price ||
        "";
      if (price !== "") {
        detail += "Precio liquidación: " + price + "\n";
      }

      if (coupon.location_id) {
        const locName = Array.isArray(coupon.location_id)
          ? coupon.location_id[1]
          : coupon.location_id;
        detail += "Ubicación POS: " + locName + "\n";
      }

      alert(detail);
      closeDialog();

      // TODO: aquí, en lugar del alert, agregaremos el producto a la orden
      // con el precio de liquidación y marcaremos el cupón como canjeado.
    });

    setTimeout(() => {
      input.focus();
      input.select();
    }, 50);
  }

  // -------------------------------------------------------------
  // Parchear el botón del POS (Nota de cliente -> Cupón QR)
  // -------------------------------------------------------------
  function patchButton() {
    const holder = document.querySelector(".control-buttons");
    if (!holder) return;

    const buttons = holder.querySelectorAll(".control-button");
    let btn = null;
    for (let i = 0; i < buttons.length; i++) {
      const b = buttons[i];
      const txt = (b.textContent || "").trim();
      if (/Nota\s+de\s+cliente/i.test(txt) || /Cup[oó]n\s*QR/i.test(txt)) {
        btn = b;
        break;
      }
    }
    if (!btn) return;

    if (btn.dataset.g7Patched === "1") return;
    btn.dataset.g7Patched = "1";

    btn.setAttribute("data-g7-coupon-button", "1");

    let icon = btn.querySelector("i.fa, i");
    if (!icon) {
      icon = document.createElement("i");
      btn.prepend(icon);
    }
    icon.className = "fa fa-qrcode";

    let label = btn.querySelector("span");
    if (!label) {
      label = document.createElement("span");
      btn.appendChild(label);
    }
    label.textContent = "Cupón QR";

    LOG("Botón POS parcheado");
  }

  const mo = new MutationObserver(() => {
    patchButton();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener("load", patchButton);
  setTimeout(patchButton, 50);
  setTimeout(patchButton, 300);
  setTimeout(patchButton, 1200);

  document.addEventListener(
    "click",
    function (e) {
      const el =
        e.target &&
        e.target.closest(
          '.control-buttons .control-button[data-g7-coupon-button="1"]'
        );
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      LOG("CLICK Cupón QR capturado");
      openCouponDialog();
    },
    { capture: true }
  );

  window.G7_POS_COUPON_ASSET = "OK";
  LOG("Asset POS cargado (ventana + búsqueda cupón vía fetch)");
})();
