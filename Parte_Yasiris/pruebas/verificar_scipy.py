import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
"""Verificación independiente con scipy (solo para comprobar, no para resolver)."""
from fractions import Fraction as F
import random
from scipy.optimize import linprog
from simplex import Problema, resolver
from sensibilidad import analizar

def lp(p, c=None, b=None):
    c = list(p.c if c is None else c); b = list(p.b if b is None else b)
    cc = [-float(v) for v in c] if p.sentido == "max" else [float(v) for v in c]
    Aub, bub, Aeq, beq = [], [], [], []
    for fila, s, bi in zip(p.A, p.signos, b):
        f = [float(v) for v in fila]
        if s == "<=": Aub.append(f); bub.append(float(bi))
        elif s == ">=": Aub.append([-v for v in f]); bub.append(-float(bi))
        else: Aeq.append(f); beq.append(float(bi))
    r = linprog(cc, A_ub=Aub or None, b_ub=bub or None, A_eq=Aeq or None, b_eq=beq or None, method="highs")
    if r.status != 0: return r.status, None, None
    z = -r.fun if p.sentido == "max" else r.fun
    return 0, r.x, z

def chequear(p, nombre):
    r = resolver(p); st, x, z = lp(p)
    estado = {0: "optimo", 2: "infactible", 3: "no_acotado"}[st]
    assert r.estado == estado, (nombre, r.estado, estado)
    if estado != "optimo": return 0
    assert abs(float(r.z) - z) < 1e-6, (nombre, r.z, z)
    s = analizar(p, r); n_ok = 0; eps = 1e-3
    base = [r.valores[v] for v in p.nombres]
    for rec in s.recursos:
        i = rec.restriccion - 1
        # precio sombra: derivada de Z respecto a b_i dentro del rango
        lo = float(rec.minimo) if rec.minimo is not None else float(rec.actual) - 10
        hi = float(rec.maximo) if rec.maximo is not None else float(rec.actual) + 10
        if hi - lo > 2 * eps:
            mid = (lo + hi) / 2; d = min(eps, (hi - lo) / 4)
            b1 = list(p.b); b1[i] = mid - d; b2 = list(p.b); b2[i] = mid + d
            z1 = lp(p, b=b1)[2]; z2 = lp(p, b=b2)[2]
            if z1 is not None and z2 is not None:
                assert abs((z2 - z1) / (2 * d) - float(rec.precio_sombra)) < 1e-4, (nombre, "sombra", i, rec.precio_sombra, (z2 - z1) / (2 * d))
                n_ok += 1
        # fuera del rango (si es finito) la solución debe cambiar de base: Z deja de ser lineal con el mismo precio
        for lim, sig in ((rec.minimo, -1), (rec.maximo, 1)):
            if lim is None: continue
            b3 = list(p.b); b3[i] = float(lim) + sig * 0.5
            st3, x3, z3 = lp(p, b=b3)
            if st3 == 0:
                pred = float(r.z) + float(rec.precio_sombra) * (float(lim) + sig * 0.5 - float(rec.actual))
                assert abs(z3 - pred) > 1e-7 or rec.precio_sombra == 0, (nombre, "rango b", i, lim)
            n_ok += 1
    for cs in s.costos:
        j = p.nombres.index(cs.variable)
        for lim, sig in ((cs.minimo, -1), (cs.maximo, 1)):
            if lim is None: continue
            dentro = list(p.c); dentro[j] = float(lim) - sig * 0.01
            fuera = list(p.c); fuera[j] = float(lim) + sig * 0.5
            _, xd, _ = lp(p, c=dentro); _, xf, _ = lp(p, c=fuera)
            assert max(abs(a - float(b_)) for a, b_ in zip(xd, base)) < 1e-6, (nombre, "dentro rango c", cs.variable)
            if xf is not None and not r.multiples and not r.degenerado:
                assert max(abs(a - float(b_)) for a, b_ in zip(xf, base)) > 1e-6, (nombre, "fuera rango c", cs.variable, lim)
            n_ok += 1
    return n_ok

problemas = {
 "E1": Problema("max", [50, 80], [[2, 1], [1, 3], [0, 1]], ["<="]*3, [100, 90, 40]),
 "E2": Problema("min", [4, 1], [[3, 1], [4, 3], [-1, -2]], ["=", ">=", ">="], [3, 6, -4]),
 "E3": Problema("max", [3, 2, 5], [[1, 2, 1], [3, 0, 2], [1, 4, 0]], ["<="]*3, [430, 460, 420]),
 "E4": Problema("max", [1, 1], [[1, 1], [1, 1]], ["<=", ">="], [2, 5]),
 "E5": Problema("max", [1, 1], [[1, -1], [-1, 1]], ["<="]*2, [1, 2]),
 "E6": Problema("max", [2, 4], [[1, 2], [1, 1]], ["<="]*2, [5, 4]),
 "E7": Problema("max", [3, 9], [[1, 4], [1, 2]], ["<="]*2, [8, 4]),
 "Wyndor": Problema("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="]*3, [4, 12, 18]),
 "Dieta": Problema("min", [F("0.4"), F("0.5")], [[F("0.3"), F("0.1")], [F("0.5"), F("0.5")], [F("0.6"), F("0.4")]], ["<=", "=", ">="], [F("2.7"), 6, 6]),
}
total = 0
for k, p in problemas.items():
    total += chequear(p, k)
# Problemas aleatorios
random.seed(7); n_rand = 0
for t in range(300):
    n = random.randint(2, 4); m = random.randint(2, 4)
    A = [[random.randint(-3, 8) for _ in range(n)] for _ in range(m)]
    sg = [random.choice(["<=", "<=", ">=", "="]) for _ in range(m)]
    b = [random.randint(-10, 30) for _ in range(m)]
    c = [random.randint(-5, 10) for _ in range(n)]
    p = Problema(random.choice(["max", "min"]), c, A, sg, b)
    try:
        total += chequear(p, f"aleatorio {t}"); n_rand += 1
    except AssertionError as e:
        print("FALLA", e, p); raise
print(f"OK: 9 problemas de clase/enunciado + {n_rand} aleatorios; {total} comprobaciones de sensibilidad")
