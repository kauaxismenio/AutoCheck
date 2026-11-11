/* Registra a apresentação do QR Code sem recarregar, para não perder a assinatura já desenhada. */
(function () {
  var box = document.querySelector("[data-review-qr]");
  if (!box) return;
  var pending = box.querySelector("[data-review-qr-pending]");
  var done = box.querySelector("[data-review-qr-done]");
  var note = box.querySelector("[data-review-qr-note]");
  var error = box.querySelector("[data-review-qr-error]");

  document.querySelectorAll("[data-review-qr-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      error.classList.add("is-hidden");
      fetch(form.getAttribute("action"), {
        method: "POST", body: new FormData(form), credentials: "same-origin",
        headers: { Accept: "application/json" },
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok) throw new Error(data.error || "Não foi possível registrar. Tente de novo.");
          pending.classList.toggle("is-hidden", data.presented);
          done.classList.toggle("is-hidden", !data.presented);
          note.textContent = data.note;
        });
      }).catch(function (failure) {
        error.textContent = failure.message;
        error.classList.remove("is-hidden");
      });
    });
  });
})();
