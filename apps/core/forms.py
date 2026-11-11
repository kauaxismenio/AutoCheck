"""Ajustes de formulário reaproveitados pelos módulos."""

# Tratado por static/js/masks.js. A padronização definitiva acontece no save() dos modelos.
UPPERCASE_ATTRS = {"data-mask": "upper", "autocapitalize": "characters"}


def mark_uppercase(form, *field_names):
    for name in field_names:
        form.fields[name].widget.attrs.update(UPPERCASE_ATTRS)
