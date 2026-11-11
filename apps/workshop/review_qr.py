"""QR Code do link de avaliação. Gerado a cada pedido, a partir do link salvo, sem guardar arquivo."""
import io

import segno

# Módulos ampliados o suficiente para impressão; a margem de 4 módulos é a exigida pela norma.
PNG_SCALE = 16
PNG_BORDER = 4


def build_png(url):
    buffer = io.BytesIO()
    segno.make(url, error="m", micro=False).save(buffer, kind="png", scale=PNG_SCALE, border=PNG_BORDER)
    return buffer.getvalue()
