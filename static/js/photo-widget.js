/* Envio de fotografias com pré-visualização. O servidor valida fase, categoria e arquivo.
   A foto vai para o armazenamento privado do sistema; nada é gravado na galeria do aparelho. */
window.AutoCheckPhotos = (function () {
  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function iconsHref() {
    var use = document.querySelector('.photo-add use');
    return use ? use.getAttribute("href").split("#")[0] : "";
  }

  function refresh(slot) {
    var count = slot.querySelectorAll("[data-photo-thumb]").length;
    var required = slot.hasAttribute("data-required");
    slot.classList.toggle("photo-slot--done", count > 0);
    slot.classList.toggle("photo-slot--missing", required && count === 0);
    var badge = slot.querySelector("[data-photo-badge]");
    if (badge) badge.textContent = count > 0 ? "Enviada" : "Obrigatória";
    slot.dispatchEvent(new CustomEvent("autocheck:photos-changed", { bubbles: true, detail: { count: count } }));
  }

  function status(slot, text, isError) {
    var el = slot.querySelector("[data-photo-status]");
    el.textContent = text || "";
    el.classList.toggle("is-error", Boolean(isError));
  }

  function addThumb(slot, data) {
    var label = slot.querySelector(".photo-slot__head span");
    var thumb = document.createElement("div");
    thumb.className = "photo-thumb";
    thumb.setAttribute("data-photo-thumb", "");
    var link = document.createElement("a");
    link.href = data.url;
    link.target = "_blank";
    link.rel = "noopener";
    var img = document.createElement("img");
    img.src = data.url;
    img.alt = label ? label.textContent : "Foto";
    link.appendChild(img);
    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "photo-thumb__remove";
    remove.setAttribute("data-photo-remove", data.delete_url);
    remove.setAttribute("aria-label", "Excluir foto");
    remove.innerHTML = '<svg aria-hidden="true" width="16" height="16"><use href="' + iconsHref() + '#x"></use></svg>';
    thumb.appendChild(link);
    thumb.appendChild(remove);
    slot.querySelector("[data-photo-thumbs]").appendChild(thumb);
  }

  function responseJson(response) {
    return response.json().catch(function () { return {}; }).then(function (data) {
      return { ok: response.ok, data: data };
    });
  }

  function upload(slot, file) {
    var body = new FormData();
    body.append("image", file);
    body.append("phase", slot.dataset.phase);
    body.append("category", slot.dataset.category);
    body.append("target", slot.dataset.target);
    status(slot, "Enviando foto...");
    return fetch(slot.dataset.uploadUrl, {
      method: "POST", body: body, credentials: "same-origin", headers: { "X-CSRFToken": csrf() },
    }).then(responseJson).then(function (result) {
      if (!result.ok) throw new Error(result.data.error || "Não foi possível enviar a foto.");
      addThumb(slot, result.data);
      status(slot, "");
      refresh(slot);
    }).catch(function (error) {
      status(slot, error.message.indexOf("fetch") >= 0 ? "Falha de conexão. Tente de novo." : error.message, true);
    });
  }

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input.matches || !input.matches("[data-photo-input]")) return;
    var slot = input.closest("[data-photo-slot]");
    var files = Array.prototype.slice.call(input.files || []);
    input.disabled = true;
    files.reduce(function (chain, file) {
      return chain.then(function () { return upload(slot, file); });
    }, Promise.resolve()).then(function () {
      input.disabled = false;
      input.value = "";
    });
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-photo-remove]");
    if (!button) return;
    if (!window.confirm("Excluir esta foto?")) return;
    var slot = button.closest("[data-photo-slot]");
    button.disabled = true;
    fetch(button.getAttribute("data-photo-remove"), {
      method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrf() },
    }).then(responseJson).then(function (result) {
      if (!result.ok) throw new Error(result.data.error || "Não foi possível excluir.");
      button.closest("[data-photo-thumb]").remove();
      status(slot, "");
      refresh(slot);
    }).catch(function (error) {
      button.disabled = false;
      status(slot, error.message, true);
    });
  });

  return { csrf: csrf };
})();
