/** @odoo-module **/
/* G7_PROBE_COUPON_ASSET (POS) */
(function () {
  const LOG = (...args) => console.log('[G7][POS-Coupon][POS]', ...args);

  // -------------------------------------------------------------
  // Helpers para acceder al POS y al producto
  // -------------------------------------------------------------
  function findPosService() {
    const o = window.odoo;
    if (!o || !o.__DEBUG__ || !o.__DEBUG__.services) {
      return null;
    }
    const services = o.__DEBUG__.services;
    for (const name in services) {
      const srv = services[name];
      if (!srv) continue;
      // OWL POS suele tener env.services.pos
      if (srv.env && srv.env.services && srv.env.services.pos) {
        return srv.env.services.pos;
      }
      // Por si algún servicio expone directamente .pos
      if (srv.pos && typeof srv.pos.get_order === "function") {
        return srv.pos;
      }
    }
    return null;
  }

  function findProductInPos(pos, productId) {
    if (!pos) return null;

    // POS clásico: pos.db.get_product_by_id
    if (pos.db && typeof pos.db.get_product_by_id === "function") {
      const p = pos.db.get_product_by_id(productId);
      if (p) return p;
    }

    // Otros casos: lista de productos en alguna propiedad
    if (Array.isArray(pos.products)) {
      const found = pos.products.find((p) => p && p.id === productId);
      if (found) return found;
    }

    return null;
  }

  function applyCouponToCurrentOrder(coupon) {
    const pos = findPosService();
    if (!pos) {
      alert(
        "Cupón válido, pero no se pudo acceder al POS internamente.\n" +
          "Reporta este mensaje al administrador."
      );
      LOG("No se encontró servicio POS en odoo.__DEBUG__.services");
      return;
    }

    const order = pos.get_order && pos.get_order();
    if (!order) {
      alert("Cupón válido, pero no hay una orden activa.");
      return;
    }

    const productField = coupon.product_id || coupon.product;
    let productId = null;
    let productName = "";
    if (Array.isArray(productField)) {
      productId = productField[0];
      productName = productField[1] || "";
    }

    if (!productId) {
      alert("Cupón válido, pero no tiene producto asociado.");
      return;
    }

    const price =
      coupon.price_liquidation ||
      coupon.liquidation_price ||
      coupon.price ||
      coupon.clearance_price ||
      coupon.public_clearance_price ||
      0;

    const product = findProductInPos(pos, productId);
    if (!product) {
      alert(
        "Cupón válido, pero el producto no está cargado en este POS.\n" +
          "Id de producto: " +
          productId
      );
      return;
    }

    LOG("Aplicando cupón sobre producto", productId, "precio", price);

    try {
      // Intento 1: pasar precio directamente
      order.add_product(product, { quantity: 1, price: price });
    } catch (err1) {
      console.warn(
        "[G7][POS-Coupon][POS] add_product con price falló, probamos set_unit_price:",
        err1
      );
      try {
        order.add_product(product, { quantity: 1 });
        const line =
          order.get_last_orderline && order.get_last_orderline();
        if (line && typeof line.set_unit_price === "function") {
          line.set_unit_price(price);
        }
      } catch (err2) {
        console.error(
          "[G7][POS-Coupon][POS] Error al agregar producto a la orden:",
          err2
        );
        alert(
          "Error al agregar el producto del cupón al carrito.\n" +
            "Revisa la consola del navegador."
        );
        return;
      }
    }

    const lastLine = order.get_last_orderline && order.get_last_orderline();
    try {
      if (lastLine && typeof lastLine.set_note === "function") {
        const prev =
          (typeof lastLine.get_note === "function" &&
            lastLine.get_note()) ||
          "";
        const note =
          (prev ? prev + " | " : "") +
          "Cupón liquidación: " +
          (coupon.name || coupon.code || "");
        lastLine.set_note(note);
      }
    } catch (e) {
      console.warn("[G7][POS-Coupon][POS] No se pudo poner nota en la línea:", e);
    }

    const displayName =
      productName ||
      product.display_name ||
      product.name ||
      "Producto " + productId;

    alert(
      "Cupón aplicado.\n\n" +
        "Producto: " +
        displayName +
        "\n" +
        "Precio liquidación: " +
        price
    );
  }

  // -------------------------------------------------------------
  // Helpers para detectar PdV permitidos en el registro del cupón
  // -------------------------------------------------------------
  function extractMany2ManyIds(value) {
    if (!Array.isArray(value) || !value.length) return null;

    // Formato típico: [[id, "Nombre"], [id2, "Nombre2"], ...]
    if (Array.isArray(value[0]) && value[0].length) {
      const ids = value
        .map((v) => (Array.isArray(v) ? v[0] : null))
        .filter((id) => typeof id === "number");
      return ids.length ? ids : null;
    }

    // Por si viniera como [id1, id2, ...]
    if (typeof value[0] === "number") {
      return value;
    }

    return null;
  }

  function getAllowedPosIds(coupon) {
    if (!coupon || typeof coupon !== "object") return [];

    // 1) Intentar con el nombre clásico pos_ids
    if (coupon.pos_ids) {
      const ids = extractMany2ManyIds(coupon.pos_ids);
      if (ids) return ids;
    }

    // 2) Buscar el primer campo que "parezca" Many2many (Studio, etc.)
    for (const key in coupon) {
      if (!Object.prototype.hasOwnProperty.call(coupon, key)) continue;
      const ids = extractMany2ManyIds(coupon[key]);
      if (ids) {
        LOG("Detectado campo PdV para cupón:", key, "=>", ids);
        return ids;
      }
    }

    return [];
  }

  // -------------------------------------------------------------
  // RPC helper: buscar cupón por código (campo name)
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
          domain: [["name", "=", code]],
          limit: 1,
        },
      },
      id: Date.now(),
    };

    const resp = await fetch(
      "/web/dataset/call_kw/liquidation.coupon/search_read",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(payload),
      }
    );

    if (!resp.ok) {
      throw new Error("HTTP " + resp.status);
    }
    const json = await resp.json();
    if (json.error) {
      const msg =
        (json.error.data && json.error.data.message) ||
        json.error.message ||
        "Error RPC";
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

      // -------- Validar PdV permitidos (cualquier campo M2M de PdV) --------
      const allowedIds = getAllowedPosIds(coupon);
      LOG("PdV actual:", posConfigId, "PdV permitidos detectados:", allowedIds);

      if (posConfigId && allowedIds.length && allowedIds.indexOf(posConfigId) === -1) {
        msg.textContent = "Este cupón no es válido para este Punto de Venta.";
        msg.style.color = "red";
        return;
      }

      // Cupón válido: cerramos ventana y aplicamos sobre la orden
      closeDialog();
      applyCouponToCurrentOrder(coupon);
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

    // Limpiamos el contenido para evitar “Cupón QRNota de cliente”
    btn.innerHTML = "";
    btn.setAttribute("data-g7-coupon-button", "1");

    const icon = document.createElement("i");
    icon.className = "fa fa-qrcode";
    btn.appendChild(icon);

    const label = document.createElement("span");
    label.textContent = "Cupón QR";
    btn.appendChild(label);

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
  LOG("Asset POS cargado (aplica cupón en la orden)");
})();
