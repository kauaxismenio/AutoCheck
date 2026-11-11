/* Área de assinatura com dedo, caneta ou mouse. O servidor valida a imagem recebida. */
(function () {
  var form = document.querySelector("[data-signature-form]");
  if (!form) return;
  var canvas = form.querySelector("[data-signature-canvas]");
  var area = form.querySelector("[data-signature-area]");
  var output = form.querySelector("[data-signature-data]");
  var refused = form.querySelector("[data-signature-refused]");
  var refusalText = form.querySelector("[data-refusal-text]");
  var context = canvas.getContext("2d");
  var strokes = [];
  var current = null;

  function redraw() {
    var ratio = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    if (!rect.width) return;
    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.lineWidth = 2.4;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.strokeStyle = "#16202e";
    strokes.forEach(function (stroke) {
      context.beginPath();
      stroke.forEach(function (point, index) {
        var x = point[0] * rect.width, y = point[1] * rect.height;
        if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
      });
      if (stroke.length === 1) context.lineTo(stroke[0][0] * rect.width + 0.1, stroke[0][1] * rect.height);
      context.stroke();
    });
  }

  function position(event) {
    var rect = canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height];
  }

  canvas.addEventListener("pointerdown", function (event) {
    event.preventDefault();
    canvas.setPointerCapture(event.pointerId);
    current = [position(event)];
    strokes.push(current);
  });
  canvas.addEventListener("pointermove", function (event) {
    if (!current) return;
    event.preventDefault();
    current.push(position(event));
    redraw();
  });
  function finish() { current = null; redraw(); }
  canvas.addEventListener("pointerup", finish);
  canvas.addEventListener("pointercancel", finish);

  form.querySelector("[data-signature-clear]").addEventListener("click", function () {
    strokes = [];
    redraw();
  });

  function refreshRefusal() {
    area.classList.toggle("is-hidden", refused.checked);
    refusalText.classList.toggle("is-hidden", !refused.checked);
    if (!refused.checked) redraw();
  }
  refused.addEventListener("change", refreshRefusal);

  // Girar o aparelho muda o tamanho da área: redesenha sem perder o traço.
  window.addEventListener("resize", redraw);

  form.addEventListener("submit", function () {
    output.value = (!refused.checked && strokes.length) ? canvas.toDataURL("image/png") : "";
  });

  redraw();
})();
