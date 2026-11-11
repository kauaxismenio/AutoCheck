/* Alterna entre escolher um mecânico da lista e digitar um novo. O servidor valida e grava. */
(function () {
  var box = document.querySelector("[data-mechanic-field]");
  if (!box) return;
  var select = box.querySelector("select");
  var toggle = box.querySelector("[data-mechanic-toggle]");
  var wrapper = box.querySelector(".mechanic-field__new");
  var input = wrapper.querySelector("input");
  var listField = select.closest(".field");
  var hasChoices = select.options.length > 1;

  function show(adding, focus) {
    wrapper.classList.toggle("is-hidden", !adding);
    listField.classList.toggle("is-hidden", adding && !hasChoices);
    select.disabled = adding;
    toggle.textContent = adding ? toggle.dataset.labelList : toggle.dataset.labelAdd;
    toggle.classList.toggle("is-hidden", !hasChoices);
    if (adding && focus) input.focus();
    if (!adding) input.value = "";
  }

  toggle.addEventListener("click", function () {
    show(wrapper.classList.contains("is-hidden"), true);
  });
  // Sem nenhum mecânico cadastrado, ou com nome já digitado, o campo de nome já começa aberto.
  show(!hasChoices || input.value !== "" || wrapper.classList.contains("field--error"), false);
})();
