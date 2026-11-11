/* Grava cada avaliação assim que muda e atualiza o progresso. O servidor decide se pode avançar. */
(function () {
  var form = document.querySelector("[data-checklist-form]");
  if (!form) return;
  var url = form.dataset.autosaveUrl;

  function token() { return form.querySelector("[name=csrfmiddlewaretoken]").value; }

  function updateProgress() {
    var box = document.querySelector("[data-check-progress]");
    var total = Number(box.dataset.total);
    var done = 0;
    form.querySelectorAll("[data-check-item]").forEach(function (row) {
      if (row.querySelector('.evaluate input:checked')) done += 1;
    });
    box.querySelector("[data-check-done]").textContent = done;
    box.querySelector("[data-check-bar]").style.width = total ? (done * 100 / total) + "%" : "0";
  }

  function setState(row, text, isError) {
    var el = row.querySelector("[data-save-state]");
    el.textContent = text || "";
    el.classList.toggle("is-error", Boolean(isError));
  }

  function payload(row) {
    var body = new URLSearchParams();
    body.append("kind", row.dataset.kind);
    body.append("id", row.dataset.id);
    var checked = row.querySelector(".evaluate input:checked");
    if (row.dataset.kind === "item") {
      if (checked) body.append("result", checked.value);
      var notes = row.querySelector("[data-notes]");
      if (notes) body.append("notes", notes.value);
    } else {
      if (checked) body.append("condition", checked.value);
      body.append("psi", row.querySelector('[data-tire-field="psi"]').value);
      body.append("twi", row.querySelector('[data-tire-field="twi"]').value);
    }
    return body;
  }

  // As gravações saem em fila: a última escolha do usuário é sempre a última a chegar ao servidor.
  var queue = Promise.resolve();
  var pending = 0;
  var submitting = false;

  function save(row) {
    pending += 1;
    setState(row, "Salvando...");
    queue = queue.then(function () { return send(row); }).then(function () { pending -= 1; });
    return queue;
  }

  // Envio final só depois da fila: o formulário completo fica sendo a última gravação.
  form.addEventListener("submit", function (event) {
    if (pending === 0 || submitting) return;
    event.preventDefault();
    submitting = true;
    queue.then(function () { form.submit(); });
  });

  function send(row) {
    return fetch(url, {
      method: "POST", body: payload(row), credentials: "same-origin",
      headers: { "X-CSRFToken": token() },
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw new Error(data.error || "Não foi possível salvar.");
        setState(row, "Salvo");
        setTimeout(function () { if (row.querySelector("[data-save-state]").textContent === "Salvo") setState(row, ""); }, 1500);
      });
    }).catch(function (error) {
      // O formulário continua preenchido: o botão "Salvar e avançar" reenvia tudo.
      setState(row, error.message.indexOf("fetch") >= 0 ? "Sem conexão. Será enviado ao salvar." : error.message, true);
    });
  }

  function toggleTirePhoto(row) {
    var box = row.querySelector("[data-tire-photo]");
    if (!box) return;
    var checked = row.querySelector(".evaluate input:checked");
    var replace = Boolean(checked) && checked.value === "substituir";
    box.classList.toggle("is-hidden", !replace);
    var slot = box.querySelector("[data-photo-slot]");
    if (replace) slot.setAttribute("data-required", "");
    else slot.removeAttribute("data-required");
    var hasPhoto = slot.querySelector("[data-photo-thumb]") !== null;
    slot.classList.toggle("photo-slot--missing", replace && !hasPhoto);
  }

  form.addEventListener("change", function (event) {
    if (event.target.matches("[data-photo-input]")) return;
    var row = event.target.closest("[data-check-item]");
    if (!row) return;
    toggleTirePhoto(row);
    updateProgress();
    save(row);
  });

  // O botão de foto não pode enviar o formulário ao pressionar Enter nos campos numéricos.
  form.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && event.target.matches('input[type="text"]')) event.preventDefault();
  });

  updateProgress();
})();
