import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
from streamlit.testing.v1 import AppTest
from exportar import json_a_problema, problema_a_json, generar_pdf
from simplex import Problema, resolver
import grafico, sensibilidad

# 1. Agregar una variable y una restricción conserva lo escrito
at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=60).run()
at.number_input(key="n").set_value(3).run()
at.number_input(key="m").set_value(4).run()
d = at.session_state["datos"]
assert d["c"][:2] == ["3", "5"] and d["c"][2] == "0", d["c"]
assert d["A"][2][:2] == ["3", "2"] and len(d["A"]) == 4, d["A"]
at.number_input(key="n").set_value(2).run()
assert at.session_state["datos"]["c"] == ["3", "5"]
print("1. Cambiar n y m conserva los datos: OK")

# 2. Validación: vacío y texto no numérico
at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=60).run()
at.session_state["datos"]["b"][0] = ""
at.session_state["datos"]["A"][1][1] = "abc"
at.session_state["version"] += 1
at.run(); at.button[0].click().run()
errs = " ".join(e.value for e in at.error)
assert "Falta un valor en el lado derecho de R1" in errs and "«abc»" in errs, errs
print("2. Validación de vacíos y no numéricos: OK ->", errs.replace("\n", " ")[:160])

# 3. JSON ida y vuelta + errores claros
datos = {"sentido": "min", "c": ["4", "1"], "A": [["3", "1"], ["4", "3"], ["-1", "-2"]], "signos": ["=", "≥", "≥"], "b": ["3", "6", "-4"]}
assert json_a_problema(problema_a_json(datos)) == datos
for malo, esperado in [('{"sentido":"max"}', "faltan"), ('{"sentido":"max","c":[1,2],"A":[[1]],"signos":["<="],"b":[3]}', "inconsistentes"), ("no es json", "JSON válido")]:
    try: json_a_problema(malo); raise SystemExit("debió fallar")
    except ValueError as e: assert esperado in str(e), e
print("3. Guardar/cargar JSON y mensajes de error: OK")

# 4. PDF para todos los casos
casos = [Problema("min", [4, 1], [[3, 1], [4, 3], [-1, -2]], ["=", ">=", ">="], [3, 6, -4]),
         Problema("max", [3, 2, 5], [[1, 2, 1], [3, 0, 2], [1, 4, 0]], ["<="]*3, [430, 460, 420]),
         Problema("max", [1, 1], [[1, 1], [1, 1]], ["<=", ">="], [2, 5])]
for p in casos:
    r = resolver(p); g = grafico.analizar(p, r.estado)
    s = sensibilidad.analizar(p, r) if r.estado == "optimo" else None
    pdf = generar_pdf(p, r, s, g, None, "modelo")
    assert pdf[:4] == b"%PDF" and len(pdf) > 3000
open("pruebas/ejemplo.pdf", "wb").write(
    generar_pdf(casos[0], resolver(casos[0]), sensibilidad.analizar(casos[0], resolver(casos[0])), None, None, "Min Z = 4x1 + x2"))
print("4. Exportar a PDF: OK")
