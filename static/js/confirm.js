/* Confirmação simples para formulários destrutivos: <form data-confirm="Pergunta?">. */
document.addEventListener("submit", function (event) {
  var message = event.target.getAttribute && event.target.getAttribute("data-confirm");
  if (message && !window.confirm(message)) event.preventDefault();
});
