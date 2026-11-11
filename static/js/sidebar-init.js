/* Define o estado do menu antes da primeira pintura, para não "piscar" entre páginas. */
(function () {
  var compact = window.matchMedia("(max-width: 1023px), (pointer: coarse)").matches;
  var state = "closed";
  if (!compact) {
    state = "open";
    try {
      state = localStorage.getItem("autocheck.sidebar") || "open";
    } catch (e) { /* armazenamento indisponível: mantém o padrão */ }
  }
  document.documentElement.setAttribute("data-sidebar", state);
})();
