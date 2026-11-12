import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
"""Prueba de la interfaz: carga cada ejemplo, resuelve y revisa que no haya errores."""
from streamlit.testing.v1 import AppTest
import re

NOMBRES = re.findall(r'^    "([^"]+)": (?:_ej|None)', open("app.py", encoding="utf-8").read(), re.M)

for nombre in NOMBRES:
    for modo in ["Paso a paso", "Solución directa"]:
        at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=60).run()
        at.selectbox(key="ejemplo").select(nombre).run()
        at.radio[1].set_value(modo).run()
        if modo == "Solución directa":   # probar también la vista en decimales
            at.sidebar.radio[2].set_value("Decimales").run()
        at.button[0].click().run()
        assert not at.exception, (nombre, [e.value for e in at.exception])
        txt = " ".join(m.value for m in at.markdown) + " ".join(x.value for x in at.success) + \
            " ".join(x.value for x in at.error) + " ".join(x.value for x in at.info)
        estado = "infactible" if "no tiene solución factible" in txt else (
            "no acotada" if "no acotada" in txt.lower() else "óptimo")
        print(f"{nombre:52s} {modo:16s} OK  -> {estado}; tabs={len(at.tabs)}; errores={len(at.error)}")
