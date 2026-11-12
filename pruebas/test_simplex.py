import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
"""Pruebas con los ejemplos vistos en clase."""
from fractions import Fraction as F

from simplex import Problema, resolver, fmt


def mostrar(nombre, r):
    print(f"\n=== {nombre} ===")
    for paso in r.preparacion:
        print("  ·", paso)
    for it in r.iteraciones:
        extra = f" | entra {it.entra}, sale {it.sale}" if it.entra else ""
        print(f"  Iter {it.numero}: básicas {it.basicas}, Z = {fmt(it.z)}{extra}")
        for op in it.operaciones:
            print("      ", op)
    print("  Estado:", r.estado, "|", r.mensaje)
    if r.z is not None:
        dec = {k: fmt(v) for k, v in r.valores.items() if r.tipos[k] == "decision"}
        print("  Solución:", dec, " Z =", fmt(r.z))


casos = []

# Wyndor Glass: (2, 6), Z = 36, 2 iteraciones
r = resolver(Problema("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18]))
mostrar("Wyndor", r)
casos.append(r.estado == "optimo" and r.z == 36 and r.valores["x1"] == 2 and r.valores["x2"] == 6
             and len(r.iteraciones) == 3)

# Worldlight: (125, 25), Z = 175, 3 iteraciones (entra S3 en la tercera)
r = resolver(Problema("max", [1, 2], [[1, 3], [2, 2], [0, 1]], ["<="] * 3, [200, 300, 60]))
mostrar("Worldlight", r)
casos.append(r.estado == "optimo" and r.z == 175 and r.valores["x1"] == 125 and r.valores["x2"] == 25)

# Gran M (clase del 20 oct): min 0.4x1 + 0.5x2 -> (7.5, 4.5), Z = 5.25
r = resolver(Problema("min", [F("0.4"), F("0.5")],
                      [[F("0.3"), F("0.1")], [F("0.5"), F("0.5")], [F("0.6"), F("0.4")]],
                      ["<=", "=", ">="], [F("2.7"), 6, 6]))
mostrar("Gran M - terapia", r)
casos.append(r.estado == "optimo" and r.z == F("5.25") and r.valores["x1"] == F("7.5")
             and r.valores["x2"] == F("4.5"))

# Caso 2: múltiples óptimos (Z = 3x1 + 2x2) -> Z = 18
r = resolver(Problema("max", [3, 2], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18]))
mostrar("Múltiples óptimos", r)
casos.append(r.estado == "optimo" and r.z == 18 and r.multiples)

# Caso 3: no acotado (solo x1 <= 4)
r = resolver(Problema("max", [3, 5], [[1, 0]], ["<="], [4]))
mostrar("No acotado", r)
casos.append(r.estado == "no_acotado")

# Caso 1: sin solución factible (3x1 + 5x2 >= 50)
r = resolver(Problema("max", [3, 5], [[1, 0], [0, 2], [3, 2], [3, 5]],
                      ["<=", "<=", "<=", ">="], [4, 12, 18, 50]))
mostrar("Infactible", r)
casos.append(r.estado == "infactible")

# Cerdos (calcio mínimo 1 %): infactible
r = resolver(Problema("min", [F("0.2"), F("0.6")],
                      [[1, 1], [F("-0.009"), F("-0.008")], [F("-0.21"), F("0.3")], [F("-0.03"), F("0.01")]],
                      ["=", ">=", ">=", "<="], [90, 0, 0, 0]))
mostrar("Cerdos", r)
casos.append(r.estado == "infactible")

# Textiles: (48, 0, 84), Z = 2388
r = resolver(Problema("max", [20, 15, 17], [[3, 5, 4], [6, 1, 3]], ["<="] * 2, [480, 540]))
mostrar("Textiles", r)
casos.append(r.estado == "optimo" and r.z == 2388)

# Lado derecho negativo: -x1 - x2 <= -2 (equivale a x1 + x2 >= 2), min x1 + 2x2 -> (2, 0), Z = 2
r = resolver(Problema("min", [1, 2], [[-1, -1]], ["<="], [-2]))
mostrar("Lado derecho negativo", r)
casos.append(r.estado == "optimo" and r.z == 2)

print("\nPruebas:", sum(casos), "de", len(casos), "correctas")
assert all(casos), casos
