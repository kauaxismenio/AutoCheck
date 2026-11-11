"""Utilitários de data sem dependência do Django."""
import calendar


def add_months(value, months):
    """Soma meses de calendário a um date/datetime.

    Quando o dia não existe no mês de destino, usa o último dia do mês
    (31/08 + 6 meses → 28/02 ou 29/02). Preserva hora e fuso de datetimes.
    Não é uma aproximação de 180 dias.
    """
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
