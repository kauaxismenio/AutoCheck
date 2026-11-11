/* Registra o service worker para permitir a instalação do aplicativo. */
(function () {
  var script = document.currentScript;
  if (!("serviceWorker" in navigator) || !script) return;
  var url = script.getAttribute("data-sw-url");
  window.addEventListener("load", function () {
    navigator.serviceWorker.register(url, { scope: "/" }).catch(function () {
      /* Sem HTTPS (fora de localhost) o navegador recusa: o sistema segue funcionando, só não instala. */
    });
  });
})();
