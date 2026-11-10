"""
Análisis de sensibilidad a partir del tablero final del simplex.

Idea (clase del 27 de octubre):
  - En el tablero final, las columnas de las variables que formaron la identidad
    al inicio (holguras o artificiales) contienen B⁻¹.
  - El precio sombra de la restricción i es el coeficiente, en el renglón 0, de la
    variable que formó la identidad en ese renglón (sin la parte de M).
  - El costo reducido de cada variable es su coeficiente en el renglón 0.
  - Rango de un lado derecho b_i: valores para los que  x_B = B⁻¹·b  sigue ≥ 0.
  - Rango de un coeficiente de costo c_j: valores para los que el renglón 0
    sigue sin negativos (la base actual sigue siendo óptima).

Los resultados se expresan en términos del problema ORIGINAL (Max o Min, y con los
signos originales de las restricciones), aunque internamente se haya maximizado -Z
o multiplicado alguna restricción por -1.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from simplex import Problema, Resultado

INF = None  # se usa None para "sin límite"


@dataclass
class FilaRecurso:
    restriccion: int
    tipo: str
    actual: Fraction
    minimo: Fraction | None      # None = -infinito
    maximo: Fraction | None      # None = +infinito
    precio_sombra: Fraction
    holgura: Fraction            # holgura (≤) o exceso (≥); 0 en =
    activa: bool


@dataclass
class FilaCosto:
    variable: str
    actual: Fraction
    minimo: Fraction | None
    maximo: Fraction | None
    valor: Fraction
    costo_reducido: Fraction
    basica: bool


@dataclass
class Sensibilidad:
    recursos: list
    costos: list
    B_inv: list
    basicas: list
    avisos: list


def analizar(p: Problema, r: Resultado) -> Sensibilidad:
    if r.estado != "optimo":
        raise ValueError("El análisis de sensibilidad solo se hace sobre una solución óptima.")
    fin = r.final
    m = len(p.b)
    n = len(p.c)
    col = {nombre: j for j, nombre in enumerate(fin.columnas)}
    r0 = [v.a for v in fin.renglon0]          # sin la parte de M
    avisos = []

    # B⁻¹: columnas de las variables que formaron la identidad al inicio
    B_inv = [[fin.filas[k][col[r.basica_inicial[i]]] for i in range(m)] for k in range(m)]
    x_B = fin.rhs

    s_obj = 1 if p.sentido == "max" else -1

    # ---------------- Recursos (lados derechos) ----------------
    x = [r.valores[p.nombres[j]] for j in range(n)]
    recursos = []
    for i in range(m):
        y = r0[col[r.basica_inicial[i]]]                # precio sombra en la forma interna
        sombra = y * r.signo_fila[i] * s_obj            # en términos del problema original
        # Rango de Δ' (cambio del lado derecho interno) para que x_B + Δ'·B⁻¹[:, i] >= 0
        lo, hi = None, None
        for k in range(m):
            a = B_inv[k][i]
            if a > 0:
                v = -x_B[k] / a
                lo = v if lo is None or v > lo else lo
            elif a < 0:
                v = -x_B[k] / a
                hi = v if hi is None or v < hi else hi
        if r.signo_fila[i] == -1:                       # Δ = -Δ'
            lo, hi = (None if hi is None else -hi), (None if lo is None else -lo)
        bi = p.b[i]
        lhs = sum(p.A[i][j] * x[j] for j in range(n))
        if p.signos[i] == "<=":
            holg = bi - lhs
        elif p.signos[i] == ">=":
            holg = lhs - bi
        else:
            holg = Fraction(0)
        recursos.append(FilaRecurso(
            restriccion=i + 1, tipo=p.signos[i], actual=bi,
            minimo=None if lo is None else bi + lo,
            maximo=None if hi is None else bi + hi,
            precio_sombra=sombra, holgura=holg, activa=(holg == 0)))

    # ---------------- Coeficientes de costo ----------------
    no_basicas = [nombre for nombre in fin.columnas
                  if nombre not in fin.basicas and r.tipos[nombre] != "artificial"]
    costos = []
    for j in range(n):
        nombre = p.nombres[j]
        cj = p.c[j]
        rc = r0[col[nombre]]
        if nombre not in fin.basicas:
            # La base sigue óptima mientras rc - δ' >= 0  (δ' = cambio del costo interno)
            d_lo, d_hi = None, rc
        else:
            k = fin.basicas.index(nombre)
            d_lo, d_hi = None, None
            for nb in no_basicas:
                t = fin.filas[k][col[nb]]
                if t == 0:
                    continue
                v = -r0[col[nb]] / t
                if t > 0:
                    d_lo = v if d_lo is None or v > d_lo else d_lo
                else:
                    d_hi = v if d_hi is None or v < d_hi else d_hi
        if s_obj == 1:
            mn = None if d_lo is None else cj + d_lo
            mx = None if d_hi is None else cj + d_hi
        else:   # costo interno = -c_j  ->  c_j = -(c'_j)
            mn = None if d_hi is None else cj - d_hi
            mx = None if d_lo is None else cj - d_lo
        costos.append(FilaCosto(variable=nombre, actual=cj, minimo=mn, maximo=mx,
                                valor=r.valores[nombre], costo_reducido=rc,
                                basica=nombre in fin.basicas))

    if r.degenerado:
        avisos.append("La solución es degenerada: los rangos son válidos, pero un precio sombra "
                      "puede cambiar al mover el recurso en una sola dirección.")
    if r.multiples:
        avisos.append("Hay soluciones óptimas múltiples: el rango de los coeficientes de costo "
                      "corresponde a la solución mostrada; en un extremo del rango la otra solución "
                      "también es óptima.")
    return Sensibilidad(recursos=recursos, costos=costos, B_inv=B_inv,
                        basicas=list(fin.basicas), avisos=avisos)
