/* Cartões CPF/CNPJ/Ambos, dispensas e consultas automáticas.
   Valores digitados continuam nos campos ao alternar: apenas se escondem.
   O servidor ignora o que estiver oculto e faz a validação definitiva. */
(function () {
  var form = document.querySelector("[data-person-form]");
  if (!form) return;
  var masks = window.AutoCheckMasks;

  function field(name) { return form.elements[name] || null; }
  function wrap(input) { return input ? input.closest(".field") : null; }

  function hint(input, text, kind) {
    var box = wrap(input);
    var el = box && box.querySelector("[data-field-hint]");
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("is-error", kind === "error");
    el.classList.toggle("is-ok", kind === "ok");
    el.classList.toggle("is-loading", kind === "loading");
  }

  /* ---- Cartões e dispensas ---- */
  var typeInput = field("person_type");
  var cards = form.querySelectorAll("[data-person-card]");

  function refreshVisibility() {
    var kind = typeInput.value;
    cards.forEach(function (card) {
      card.setAttribute("aria-pressed", card.dataset.personCard === kind ? "true" : "false");
    });
    form.querySelector('[data-person-section="pf"]').classList.toggle("is-hidden", kind === "pj");
    form.querySelector('[data-person-section="pj"]').classList.toggle("is-hidden", kind === "pf");
    [["cpf_not_informed", "cpf"], ["cnpj_not_informed", "cnpj"], ["email_opt_out", "email"]].forEach(function (pair) {
      var check = field(pair[0]), target = wrap(field(pair[1]));
      if (check && target) target.classList.toggle("is-hidden", check.checked);
    });
  }

  cards.forEach(function (card) {
    card.addEventListener("click", function () {
      typeInput.value = card.dataset.personCard;
      refreshVisibility();
    });
  });
  ["cpf_not_informed", "cnpj_not_informed", "email_opt_out"].forEach(function (name) {
    var check = field(name);
    if (check) check.addEventListener("change", refreshVisibility);
  });
  refreshVisibility();

  /* ---- Consultas (sempre pelo backend, com debounce) ---- */
  function setIfAllowed(input, value) {
    // Só substitui campo vazio ou preenchido pela consulta anterior; o que foi digitado fica.
    if (!input || value === undefined || value === null || value === "") return;
    if (input.value && input.value !== input.dataset.autofilled) return;
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dataset.autofilled = input.value; // depois da máscara de maiúsculas
  }

  function clearAutofilled(input) {
    if (input && input.value && input.value === input.dataset.autofilled) input.value = "";
  }

  function lookup(options) {
    var timer = null, controller = null, lastQuery = "";
    options.input.addEventListener("input", function () {
      clearTimeout(timer);
      if (controller) controller.abort();
      var value = options.input.value;
      if (!options.isComplete(value)) {
        lastQuery = "";
        hint(options.input, "");
        return;
      }
      if (options.isValid && !options.isValid(value)) {
        lastQuery = "";
        hint(options.input, options.invalidText, "error");
        return;
      }
      if (value === lastQuery) return;
      hint(options.input, "");
      timer = setTimeout(function () {
        lastQuery = value;
        controller = new AbortController();
        hint(options.input, "Consultando...", "loading");
        var url = options.url + "?" + options.param + "=" + encodeURIComponent(value);
        fetch(url, { signal: controller.signal, credentials: "same-origin", headers: { Accept: "application/json" } })
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (data.found) {
              options.fill(data);
              hint(options.input, data.message, "ok");
            } else {
              hint(options.input, data.message || "");
            }
          })
          .catch(function (error) {
            if (error.name === "AbortError") return;
            lastQuery = "";
            hint(options.input, "Não foi possível consultar agora. Preencha manualmente.");
          });
      }, 500);
    });
  }

  /* CPF e CNPJ são independentes: cada consulta preenche apenas os seus próprios campos. */
  function fillPerson(data) {
    setIfAllowed(field("full_name"), data.full_name);
    setIfAllowed(field("phone"), data.phone);
    setIfAllowed(field("email"), data.email);
  }

  function fillCompany(data) {
    // Empresa sem nome fantasia não pode herdar o da consulta anterior.
    if (!data.trade_name) clearAutofilled(field("trade_name"));
    setIfAllowed(field("legal_name"), data.legal_name);
    setIfAllowed(field("trade_name"), data.trade_name);
  }

  if (field("cnpj") && form.dataset.cnpjUrl) {
    lookup({
      input: field("cnpj"), url: form.dataset.cnpjUrl, param: "cnpj",
      isComplete: function (v) { return v.replace(/[^A-Za-z0-9]/g, "").length === 14; },
      isValid: masks.cnpjValid, invalidText: "CNPJ inválido. Confira os caracteres.", fill: fillCompany,
    });
  }
  if (field("cpf") && form.dataset.cpfUrl) {
    lookup({
      input: field("cpf"), url: form.dataset.cpfUrl, param: "cpf",
      isComplete: function (v) { return v.replace(/\D/g, "").length === 11; },
      isValid: masks.cpfValid, invalidText: "CPF inválido. Confira os números.", fill: fillPerson,
    });
  }
  if (field("plate") && form.dataset.plateUrl) {
    lookup({
      input: field("plate"), url: form.dataset.plateUrl, param: "placa",
      isComplete: function (v) { return v.replace(/[^A-Za-z0-9]/g, "").length === 7; },
      isValid: function (v) {
        var raw = v.replace(/-/g, "");
        return /^[A-Z]{3}\d{4}$/.test(raw) || /^[A-Z]{3}\d[A-Z]\d{2}$/.test(raw);
      },
      invalidText: "Placa inválida. Use ABC-1234 ou ABC1D23.",
      fill: function (data) {
        setIfAllowed(field("brand"), data.brand);
        setIfAllowed(field("model"), data.model);
        setIfAllowed(field("year"), String(data.year || ""));
        setIfAllowed(field("color"), data.color);
      },
    });
  }
})();
