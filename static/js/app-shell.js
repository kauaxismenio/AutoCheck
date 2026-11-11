/* Menu lateral: computador inicia aberto e guarda a preferência; celular e tablet iniciam fechados. */
(function () {
  var root = document.documentElement;
  var toggle = document.querySelector("[data-sidebar-toggle]");
  if (!toggle) return;
  var query = window.matchMedia("(max-width: 1023px), (pointer: coarse)");

  function sync() {
    toggle.setAttribute("aria-expanded", root.getAttribute("data-sidebar") === "open" ? "true" : "false");
  }

  function setState(state) {
    root.setAttribute("data-sidebar", state);
    if (!query.matches) {
      try { localStorage.setItem("autocheck.sidebar", state); } catch (e) { /* sem armazenamento */ }
    }
    sync();
  }

  toggle.addEventListener("click", function () {
    setState(root.getAttribute("data-sidebar") === "open" ? "closed" : "open");
  });
  document.querySelectorAll("[data-sidebar-close]").forEach(function (el) {
    el.addEventListener("click", function () { setState("closed"); });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && query.matches) setState("closed");
  });
  query.addEventListener("change", function () {
    var state = "closed";
    if (!query.matches) {
      try { state = localStorage.getItem("autocheck.sidebar") || "open"; } catch (e) { state = "open"; }
    }
    root.setAttribute("data-sidebar", state);
    sync();
  });
  sync();
})();
