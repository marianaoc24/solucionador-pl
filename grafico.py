"""
Método gráfico para problemas con 2 variables de decisión.

Pasos (clase del 8 de octubre):
  1. Graficar cada restricción como igualdad (recta frontera).
  2. Sombrear la región factible (donde se cumplen todas, con x1, x2 >= 0).
  3. Encontrar los vértices (soluciones factibles en vértice) y evaluar Z en cada uno.
  4. Dibujar la recta de la función objetivo (isoutilidad) que pasa por el óptimo.

Todo se calcula con fracciones exactas; solo se pasa a decimales para dibujar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from simplex import Problema, fmt  # noqa: E402


@dataclass
class Vertice:
    x1: Fraction
    x2: Fraction
    z: Fraction
    rectas: list            # nombres de las rectas que se cruzan ahí
    optimo: bool = False


@dataclass
class AnalisisGrafico:
    aplica: bool
    mensaje: str = ""
    vertices: list = field(default_factory=list)       # vértices factibles reales
    no_factibles: list = field(default_factory=list)   # cruces fuera de la región
    acotada: bool = True
    vacia: bool = False
    estado: str = ""        # optimo / no_acotado / infactible
    z_opt: Fraction | None = None
    optimos: list = field(default_factory=list)
    limites: tuple = (10, 10)
    poligono: list = field(default_factory=list)       # región recortada a la ventana
    redundantes: list = field(default_factory=list)    # restricciones que no tocan la región


def _texto_restriccion(fila, signo, b, nombres=("x₁", "x₂")):
    partes = []
    for coef, nom in zip(fila, nombres):
        if coef == 0:
            continue
        c = "" if abs(coef) == 1 else fmt(abs(coef))
        signo_t = "-" if coef < 0 else "+"
        if not partes:
            partes.append(("-" if coef < 0 else "") + f"{c}{nom}")
        else:
            partes.append(f" {signo_t} {c}{nom}")
    op = {"<=": "≤", ">=": "≥", "=": "="}[signo]
    return "".join(partes or ["0"]) + f" {op} {fmt(b)}"


def _cumple(fila, signo, b, x, y):
    v = fila[0] * x + fila[1] * y
    return v <= b if signo == "<=" else (v >= b if signo == ">=" else v == b)


def _cruce(l1, l2):
    (a1, b1, c1), (a2, b2, c2) = l1, l2
    det = a1 * b2 - a2 * b1
    if det == 0:
        return None
    return ((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det)


def analizar(p: Problema, estado_simplex: str | None = None) -> AnalisisGrafico:
    """estado_simplex: resultado del simplex ("no_acotado" confirma que Z crece sin límite)."""
    if len(p.c) != 2:
        return AnalisisGrafico(
            aplica=False,
            mensaje=(f"El problema tiene {len(p.c)} variables de decisión. El método gráfico solo aplica "
                     "con 2 variables (se dibuja en el plano x₁, x₂). Use el método simplex."))

    rectas = []   # (a, b, c, nombre)
    for i, (fila, bi) in enumerate(zip(p.A, p.b)):
        if fila[0] == 0 and fila[1] == 0:
            continue
        rectas.append((fila[0], fila[1], bi, f"R{i + 1}"))
    ejes = [(Fraction(1), Fraction(0), Fraction(0), "x₁ = 0"), (Fraction(0), Fraction(1), Fraction(0), "x₂ = 0")]

    def factible(x, y):
        return x >= 0 and y >= 0 and all(_cumple(f, s, bi, x, y) for f, s, bi in zip(p.A, p.signos, p.b))

    todas = rectas + ejes
    cruces = {}
    for l1, l2 in combinations(todas, 2):
        pt = _cruce(l1[:3], l2[:3])
        if pt is None:
            continue
        cruces.setdefault(pt, set()).update([l1[3], l2[3]])

    z_de = lambda x, y: p.c[0] * x + p.c[1] * y  # noqa: E731
    vertices, no_fact = [], []
    for (x, y), nom in cruces.items():
        v = Vertice(x, y, z_de(x, y), sorted(nom))
        (vertices if factible(x, y) else no_fact).append(v)
    no_fact = [v for v in no_fact if v.x1 >= 0 and v.x2 >= 0]

    # Ventana de dibujo: que se vean todos los cruces relevantes
    xs = [v.x1 for v in vertices + no_fact] + [Fraction(1)]
    ys = [v.x2 for v in vertices + no_fact] + [Fraction(1)]
    X = max(xs) * Fraction(13, 10)
    Y = max(ys) * Fraction(13, 10)
    X = max(X, Y / 4, Fraction(1))
    Y = max(Y, X / 4, Fraction(1))

    # Región recortada por la ventana (para sombrear y detectar si no está acotada)
    def recortar(X, Y):
        caja = [(Fraction(1), Fraction(0), X, "caja"), (Fraction(0), Fraction(1), Y, "caja")]
        pts = set()
        for l1, l2 in combinations(todas + caja, 2):
            pt = _cruce(l1[:3], l2[:3])
            if pt and factible(*pt) and pt[0] <= X and pt[1] <= Y:
                pts.add(pt)
        return pts

    pts_caja = recortar(X, Y)
    acotada = not any(pt[0] == X or pt[1] == Y for pt in pts_caja)
    if not acotada:
        # Ampliar la ventana para que se vea hacia dónde se abre la región
        X, Y = X * Fraction(5, 2), Y * Fraction(5, 2)
        pts_caja = recortar(X, Y)
    poligono = _casco(list(pts_caja))

    res = AnalisisGrafico(aplica=True, vertices=sorted(vertices, key=lambda v: (v.x1, v.x2)),
                          no_factibles=no_fact, acotada=acotada, limites=(X, Y), poligono=poligono)
    if vertices:
        en_borde = set()
        for v in vertices:
            en_borde.update(v.rectas)
        res.redundantes = [nom for (_, _, _, nom) in rectas if nom not in en_borde]

    if not vertices and not pts_caja:
        res.vacia = True
        res.estado = "infactible"
        res.mensaje = ("No hay región factible: ningún punto cumple todas las restricciones a la vez. "
                       "El problema no tiene solución factible.")
        return res

    # Óptimo: el mejor vértice; si la región no está acotada, revisar si Z mejora sin límite
    mejor = max if p.sentido == "max" else min
    if vertices:
        z_opt = mejor(v.z for v in vertices)
    else:
        z_opt = None
    ilimitado = (not acotada) and (estado_simplex == "no_acotado" or z_opt is None)
    if ilimitado:
        res.estado = "no_acotado"
        res.mensaje = ("La región factible no está acotada en la dirección en que mejora Z: la recta de "
                       "isoutilidad se puede desplazar sin límite. Solución no acotada.")
        return res

    res.estado = "optimo"
    res.z_opt = z_opt
    if "=" in p.signos:
        res.redundantes = [nom for nom in res.redundantes
                           if p.signos[int(nom[1:]) - 1] != "="]
    for v in res.vertices:
        v.optimo = v.z == z_opt
    res.optimos = [v for v in res.vertices if v.optimo]
    if len(res.optimos) > 1:
        a, b = res.optimos[0], res.optimos[-1]
        res.mensaje = (f"Soluciones óptimas múltiples: la recta de Z es paralela a una restricción y todo el "
                       f"segmento entre ({fmt(a.x1)}, {fmt(a.x2)}) y ({fmt(b.x1)}, {fmt(b.x2)}) da Z = {fmt(z_opt)}.")
    else:
        o = res.optimos[0]
        res.mensaje = f"El óptimo está en el vértice ({fmt(o.x1)}, {fmt(o.x2)}) con Z = {fmt(z_opt)}."
    if not acotada:
        res.mensaje += " La región factible no está acotada, pero Z no mejora en la dirección abierta."
    if "=" in p.signos:
        res.mensaje += (" Como hay una restricción de igualdad, la región factible es solo el segmento "
                        "de esa recta que cumple las demás restricciones.")
    return res


def _casco(puntos):
    """Casco convexo (cadena monótona). Devuelve la lista ordenada de vértices."""
    pts = sorted(set(puntos))
    if len(pts) <= 2:
        return pts

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    inf, sup = [], []
    for q in pts:
        while len(inf) >= 2 and cruz(inf[-2], inf[-1], q) <= 0:
            inf.pop()
        inf.append(q)
    for q in reversed(pts):
        while len(sup) >= 2 and cruz(sup[-2], sup[-1], q) <= 0:
            sup.pop()
        sup.append(q)
    return inf[:-1] + sup[:-1]


COLORES = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#be185d", "#4d7c0f"]


def dibujar(p: Problema, g: AnalisisGrafico):
    X, Y = float(g.limites[0]), float(g.limites[1])
    fig, ax = plt.subplots(figsize=(8, 6.5), dpi=110)

    # Región factible
    if g.poligono:
        xs = [float(a) for a, _ in g.poligono]
        ys = [float(b) for _, b in g.poligono]
        if len(g.poligono) >= 3:
            ax.fill(xs, ys, color="#22c55e", alpha=0.25, label="Región factible", zorder=1)
        else:
            ax.plot(xs, ys, color="#16a34a", linewidth=6, alpha=0.5, label="Región factible", zorder=1)

    # Rectas de las restricciones
    for i, (fila, s, bi) in enumerate(zip(p.A, p.signos, p.b)):
        a, b = float(fila[0]), float(fila[1])
        etiqueta = f"R{i + 1}: " + _texto_restriccion(fila, s, bi)
        if f"R{i + 1}" in g.redundantes:
            etiqueta += "  (redundante)"
        color = COLORES[i % len(COLORES)]
        estilo = ":" if f"R{i + 1}" in g.redundantes else "-"
        if b != 0:
            xx = [0, X]
            yy = [(float(bi) - a * x) / b for x in xx]
            ax.plot(xx, yy, estilo, color=color, linewidth=1.8, label=etiqueta, zorder=2)
        elif a != 0:
            ax.axvline(float(bi) / a, linestyle=estilo, color=color, linewidth=1.8, label=etiqueta, zorder=2)

    # Recta de la función objetivo en el óptimo (isoutilidad)
    if g.estado == "optimo" and g.z_opt is not None:
        c1, c2, z = float(p.c[0]), float(p.c[1]), float(g.z_opt)
        lab = "Z: " + _texto_restriccion(p.c, "=", g.z_opt) + " (óptimo)"
        if c2 != 0:
            xx = [0, X]
            ax.plot(xx, [(z - c1 * x) / c2 for x in xx], "k--", linewidth=2, label=lab, zorder=3)
        elif c1 != 0:
            ax.axvline(z / c1, color="k", linestyle="--", linewidth=2, label=lab, zorder=3)
        if len(g.optimos) > 1:
            a, b = g.optimos[0], g.optimos[-1]
            ax.plot([float(a.x1), float(b.x1)], [float(a.x2), float(b.x2)], color="#f59e0b",
                    linewidth=6, alpha=0.8, label="Segmento de óptimos", zorder=4)

    # Vértices factibles con su Z
    for v in g.vertices:
        color = "#f59e0b" if v.optimo else "#111827"
        ax.plot(float(v.x1), float(v.x2), "o", color=color, markersize=9 if v.optimo else 6, zorder=5,
                markeredgecolor="white")
        ax.annotate(f"({fmt(v.x1)}, {fmt(v.x2)})\nZ = {fmt(v.z)}", (float(v.x1), float(v.x2)),
                    textcoords="offset points", xytext=(6, 6), fontsize=8.5,
                    fontweight="bold" if v.optimo else "normal", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, alpha=0.85))
    for v in g.no_factibles:
        if float(v.x1) <= X and float(v.x2) <= Y:
            ax.plot(float(v.x1), float(v.x2), "x", color="#9ca3af", markersize=6, zorder=4)

    ax.set_xlim(0, X)
    ax.set_ylim(0, Y)
    ax.axhline(0, color="#374151", linewidth=1)
    ax.axvline(0, color="#374151", linewidth=1)
    ax.set_xlabel("x₁")
    ax.set_ylabel("x₂")
    titulo = {"optimo": "Método gráfico", "no_acotado": "Método gráfico: solución no acotada",
              "infactible": "Método gráfico: sin región factible"}.get(g.estado, "Método gráfico")
    if g.estado == "optimo" and not g.acotada:
        titulo += " (región no acotada)"
    ax.set_title(titulo)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8.5, frameon=False)
    fig.tight_layout()
    return fig
