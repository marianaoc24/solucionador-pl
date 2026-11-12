"""Exportar la solución paso a paso a PDF y guardar/cargar problemas en JSON."""
from __future__ import annotations

import io
import json
import os
from fractions import Fraction

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from simplex import fmt

# Fuente con soporte para x₁, ≤, ≥, ⁻¹ (viene incluida con matplotlib)
_FUENTES = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_FUENTES, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_FUENTES, "DejaVuSans-Bold.ttf")))

SIGNO_TXT = {"<=": "≤", ">=": "≥", "=": "="}


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------
def problema_a_json(datos: dict) -> str:
    """datos: {'sentido', 'c', 'A', 'signos', 'b'} con números como texto."""
    salida = {
        "sentido": datos["sentido"],
        "c": [str(v) for v in datos["c"]],
        "A": [[str(v) for v in fila] for fila in datos["A"]],
        "signos": [SIGNO_TXT.get(s, s) for s in datos["signos"]],
        "b": [str(v) for v in datos["b"]],
    }
    return json.dumps(salida, ensure_ascii=False, indent=2)


def json_a_problema(texto: str) -> dict:
    """Lee y valida un JSON. Lanza ValueError con un mensaje claro si algo falla."""
    try:
        d = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"El archivo no es un JSON válido ({e.msg}, línea {e.lineno}).")
    if not isinstance(d, dict):
        raise ValueError("El JSON debe ser un objeto con las claves sentido, c, A, signos y b.")
    faltan = [k for k in ("sentido", "c", "A", "signos", "b") if k not in d]
    if faltan:
        raise ValueError("Al JSON le faltan las claves: " + ", ".join(faltan) + ".")
    sentido = str(d["sentido"]).lower()
    if sentido not in ("max", "min"):
        raise ValueError("'sentido' debe ser 'max' o 'min'.")
    c, A, signos, b = d["c"], d["A"], d["signos"], d["b"]
    if not isinstance(c, list) or not c:
        raise ValueError("'c' debe ser una lista con al menos un coeficiente.")
    if not isinstance(A, list) or not A or not all(isinstance(f, list) for f in A):
        raise ValueError("'A' debe ser una lista de filas (una por restricción).")
    n, m = len(c), len(A)
    if any(len(f) != n for f in A):
        raise ValueError(f"Dimensiones inconsistentes: cada fila de A debe tener {n} coeficientes (uno por variable).")
    if not isinstance(signos, list) or len(signos) != m:
        raise ValueError(f"'signos' debe tener {m} elementos (uno por restricción).")
    if not isinstance(b, list) or len(b) != m:
        raise ValueError(f"'b' debe tener {m} elementos (uno por restricción).")
    mapa = {"<=": "≤", "≤": "≤", ">=": "≥", "≥": "≥", "=": "="}
    if any(s not in mapa for s in signos):
        raise ValueError("Cada signo debe ser ≤, ≥ o = (también se acepta <= y >=).")
    return {"sentido": sentido, "c": [str(v) for v in c], "A": [[str(v) for v in f] for f in A],
            "signos": [mapa[s] for s in signos], "b": [str(v) for v in b]}


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def _estilos():
    base = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=base["Normal"], fontName="DejaVu", fontSize=9.5, leading=13)
    return {
        "titulo": ParagraphStyle("t", parent=normal, fontName="DejaVu-Bold", fontSize=16, leading=20, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=normal, fontName="DejaVu-Bold", fontSize=12, leading=16,
                             spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=normal, fontName="DejaVu-Bold", fontSize=10.5, spaceBefore=6),
        "n": normal,
        "peq": ParagraphStyle("p", parent=normal, fontSize=8, leading=10, textColor=colors.HexColor("#4b5563")),
    }


def _tabla(filas, encabezado=True, col_piv=None, fila_piv=None, tam=7.5):
    t = Table(filas, repeatRows=1 if encabezado else 0)
    st = [
        ("FONT", (0, 0), (-1, -1), "DejaVu", tam),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]
    if encabezado:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
               ("FONT", (0, 0), (-1, 0), "DejaVu-Bold", tam)]
    if col_piv is not None:
        st.append(("BACKGROUND", (col_piv, 1), (col_piv, -1), colors.HexColor("#dbeafe")))
    if fila_piv is not None:
        st.append(("BACKGROUND", (0, fila_piv), (-1, fila_piv), colors.HexColor("#d1fae5")))
        if col_piv is not None:
            st.append(("BACKGROUND", (col_piv, fila_piv), (col_piv, fila_piv), colors.HexColor("#fcd34d")))
    t.setStyle(TableStyle(st))
    return t


def _lim(v):
    return "−∞" if v == "-inf" else ("∞" if v is None else fmt(v))


def generar_pdf(p, r, sens=None, grafico=None, figura_png: bytes | None = None, modelo_txt: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.3 * cm, title="Solución paso a paso")
    e = _estilos()
    h = []
    h.append(Paragraph("Solución de programación lineal — paso a paso", e["titulo"]))
    h.append(Paragraph("Método Simplex con Gran M · Optimización · Universidad de Antioquia", e["peq"]))
    h.append(Spacer(1, 6))

    h.append(Paragraph("Formulación", e["h2"]))
    for linea in modelo_txt.splitlines():
        h.append(Paragraph(linea, e["n"]))

    h.append(Paragraph("Preparación (forma aumentada)", e["h2"]))
    for paso in r.preparacion:
        h.append(Paragraph("• " + paso, e["n"]))

    h.append(Paragraph("Tableros", e["h2"]))
    etq0 = "Z (R0)" if p.sentido == "max" else "−Z (R0)"
    for k, it in enumerate(r.iteraciones):
        titulo = f"Iteración {it.numero}"
        if k == 0 and len(r.iteraciones) > 1 and r.iteraciones[1].numero == 0:
            titulo = "Tablero inicial (con M)"
        h.append(Paragraph(titulo, e["h3"]))
        if it.nota:
            h.append(Paragraph(it.nota, e["peq"]))
        filas = [["Básica"] + it.columnas + ["Lado derecho"]]
        filas.append([etq0] + [fmt(v) for v in it.renglon0] + [fmt(it.z)])
        for i, nb in enumerate(it.basicas):
            filas.append([f"{nb} (R{i + 1})"] + [fmt(v) for v in it.filas[i]] + [fmt(it.rhs[i])])
        col_piv = (it.columnas.index(it.entra) + 1) if it.entra else None
        fila_piv = (it.pivote[0] + 1) if it.pivote else None
        tam = 7.5 if len(it.columnas) <= 10 else 6
        h.append(_tabla(filas, col_piv=col_piv, fila_piv=fila_piv, tam=tam))
        if it.entra:
            h.append(Paragraph(f"<b>Entra:</b> {it.entra} (coeficiente más negativo del renglón 0).", e["n"]))
            h.append(Paragraph("<b>Razón mínima:</b> " + "; ".join(f"R{f}: {t}" for f, t in it.cocientes), e["n"]))
            if it.sale:
                h.append(Paragraph(f"<b>Sale:</b> {it.sale}. <b>Pivote:</b> renglón {it.pivote[0]}, "
                                   f"columna {it.pivote[1]}.", e["n"]))
        if it.operaciones:
            h.append(Paragraph("<b>Operaciones:</b> " + " · ".join(it.operaciones), e["n"]))
        h.append(Spacer(1, 4))

    h.append(Paragraph("Resultado", e["h2"]))
    h.append(Paragraph(r.mensaje, e["n"]))
    for a in r.avisos:
        h.append(Paragraph("Nota: " + a, e["n"]))
    if r.estado == "optimo":
        dec = [[k, fmt(v)] for k, v in r.valores.items() if r.tipos[k] == "decision"]
        h.append(_tabla([["Variable", "Valor"]] + dec + [["Z", fmt(r.z)]]))
        if r.alternativa:
            h.append(Paragraph("Otra solución óptima: " + ", ".join(f"{k} = {fmt(v)}" for k, v in r.alternativa.items())
                               + f" (también Z = {fmt(r.z)}).", e["n"]))

    if figura_png and grafico is not None and grafico.aplica:
        h.append(PageBreak())
        h.append(Paragraph("Método gráfico", e["h2"]))
        h.append(Paragraph(grafico.mensaje, e["n"]))
        h.append(Image(io.BytesIO(figura_png), width=19 * cm, height=13 * cm, kind="proportional"))
        if grafico.vertices:
            h.append(_tabla([["Vértice (x₁, x₂)", "Z", "¿Óptimo?"]] +
                            [[f"({fmt(v.x1)}, {fmt(v.x2)})", fmt(v.z), "Sí" if v.optimo else ""] for v in grafico.vertices]))

    if sens is not None:
        h.append(PageBreak())
        h.append(Paragraph("Análisis de sensibilidad", e["h2"]))
        h.append(Paragraph("Lados derechos (recursos)", e["h3"]))
        filas = [["Restricción", "Tipo", "Valor actual", "Mínimo", "Máximo", "Precio sombra", "Holgura/exceso"]]
        for x in sens.recursos:
            filas.append([f"R{x.restriccion}", SIGNO_TXT[x.tipo], fmt(x.actual),
                          "−∞" if x.minimo is None else fmt(x.minimo), "∞" if x.maximo is None else fmt(x.maximo),
                          fmt(x.precio_sombra), fmt(x.holgura)])
        h.append(_tabla(filas, tam=8.5))
        h.append(Paragraph("Coeficientes de la función objetivo", e["h3"]))
        filas = [["Variable", "Valor actual", "Mínimo", "Máximo", "Valor en el óptimo", "Costo reducido"]]
        for x in sens.costos:
            filas.append([x.variable, fmt(x.actual), "−∞" if x.minimo is None else fmt(x.minimo),
                          "∞" if x.maximo is None else fmt(x.maximo), fmt(x.valor), fmt(x.costo_reducido)])
        h.append(_tabla(filas, tam=8.5))
        for a in sens.avisos:
            h.append(Paragraph("Nota: " + a, e["peq"]))

    doc.build(h)
    return buf.getvalue()
