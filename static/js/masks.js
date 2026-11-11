/* Máscaras e retorno imediato. A decisão final é sempre do backend.
   Atua no evento "input", que dispara tanto ao digitar quanto ao colar. */
window.AutoCheckMasks = (function () {
  function digits(value) { return value.replace(/\D/g, ""); }

  function cpf(value) {
    var d = digits(value).slice(0, 11);
    return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/^(\d{3})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3-$4");
  }

  function cnpj(value) {
    var raw = value.toUpperCase().replace(/[^A-Z0-9]/g, "");
    // 12 primeiras posições alfanuméricas; as 2 últimas (DVs) somente numéricas.
    var base = raw.slice(0, 12);
    var dv = digits(raw.slice(12)).slice(0, 2);
    var out = base.slice(0, 2);
    if (base.length > 2) out += "." + base.slice(2, 5);
    if (base.length > 5) out += "." + base.slice(5, 8);
    if (base.length > 8) out += "/" + base.slice(8, 12);
    if (dv) out += "-" + dv;
    return out;
  }

  function phone(value) {
    var d = digits(value);
    if ((d.length === 12 || d.length === 13) && d.indexOf("55") === 0) d = d.slice(2);
    d = d.slice(0, 11);
    if (d.length <= 2) return d.length ? "(" + d : "";
    var ddd = "(" + d.slice(0, 2) + ") ";
    var rest = d.slice(2);
    if (rest.charAt(0) === "9") {
      var out = ddd + rest.charAt(0);
      if (rest.length > 1) out += " " + rest.slice(1, 5);
      if (rest.length > 5) out += "-" + rest.slice(5, 9);
      return out;
    }
    return ddd + rest.slice(0, 4) + (rest.length > 4 ? "-" + rest.slice(4, 8) : "");
  }

  function plate(value) {
    var raw = value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 7);
    // Formato antigo: ABC-1234. Mercosul (ABC1D23) não tem hífen.
    if (/^[A-Z]{3}\d{1,4}$/.test(raw) && !/^[A-Z]{3}\d[A-Z]/.test(raw) && raw.length > 4) {
      return raw.slice(0, 3) + "-" + raw.slice(3);
    }
    return raw;
  }

  function number(value) { return digits(value); }

  // Mantém acentos e não remove nada: só muda a caixa. O backend padroniza de novo ao salvar.
  function upper(value) { return value.toLocaleUpperCase("pt-BR"); }

  function cpfValid(value) {
    var d = digits(value);
    if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
    function dv(length) {
      var sum = 0;
      for (var i = 0; i < length; i++) sum += Number(d.charAt(i)) * (length + 1 - i);
      var rest = sum % 11;
      return rest < 2 ? 0 : 11 - rest;
    }
    return dv(9) === Number(d.charAt(9)) && dv(10) === Number(d.charAt(10));
  }

  function cnpjValid(value) {
    var c = value.toUpperCase().replace(/[.\-\/\s]/g, "");
    if (!/^[A-Z0-9]{12}\d{2}$/.test(c) || /^(.)\1{13}$/.test(c)) return false;
    var weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    function dv(length) {
      var offset = 13 - length, sum = 0;
      for (var i = 0; i < length; i++) sum += (c.charCodeAt(i) - 48) * weights[i + offset];
      var rest = sum % 11;
      return rest < 2 ? 0 : 11 - rest;
    }
    return dv(12) === Number(c.charAt(12)) && dv(13) === Number(c.charAt(13));
  }

  var masks = { cpf: cpf, cnpj: cnpj, phone: phone, plate: plate, number: number, upper: upper };

  function apply(input) {
    var mask = masks[input.getAttribute("data-mask")];
    if (!mask) return;
    var before = input.value;
    var after = mask(before);
    if (after === before) return;
    var fromEnd = before.length - (input.selectionStart === null ? before.length : input.selectionStart);
    input.value = after;
    if (document.activeElement === input && input.setSelectionRange) {
      var position = Math.max(0, after.length - fromEnd);
      input.setSelectionRange(position, position);
    }
  }

  function bind(scope) {
    (scope || document).querySelectorAll("[data-mask]").forEach(function (input) {
      if (input.dataset.maskBound) return;
      input.dataset.maskBound = "1";
      // Trocar o valor durante a composição do teclado Android duplica letras; aplica ao terminar.
      input.addEventListener("input", function (event) { if (!event.isComposing) apply(input); });
      input.addEventListener("compositionend", function () { apply(input); });
      apply(input);
    });
  }

  if (document.readyState !== "loading") bind();
  else document.addEventListener("DOMContentLoaded", function () { bind(); });

  return { cpf: cpf, cnpj: cnpj, phone: phone, plate: plate, cpfValid: cpfValid, cnpjValid: cnpjValid, bind: bind };
})();
