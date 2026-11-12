"""
Interfaz gráfica: Solucionador de Programación Lineal (Optimización, UdeA).

Ejecutar en el computador:
    pip install -r requirements.txt
    streamlit run app.py
"""
import hashlib
import io
from fractions import Fraction

import pandas as pd
import streamlit as st

import grafico
import sensibilidad
from exportar import generar_pdf, json_a_problema, problema_a_json
from simplex import Problema, fmt, mostrando_decimales, resolver, usar_decimales

st.set_page_config(page_title="Solucionador de Programación Lineal", page_icon="📐", layout="wide")

SIGNOS_UI = {"≤": "<=", "≥": ">=", "=": "="}
SIGNO_TXT = {"<=": "≤", ">=": "≥", "=": "="}

# --------------------------------------------------------------------------
# Ejemplos (los 7 del enunciado y los de clase)
# --------------------------------------------------------------------------
def _ej(sentido, c, A, signos, b):
    return {"sentido": sentido, "c": [str(v) for v in c], "A": [[str(v) for v in f] for f in A],
            "signos": signos, "b": [str(v) for v in b]}


EJEMPLOS = {
    "Problema nuevo (vacío)": None,
    "Enunciado 1 · forma estándar y redundante": _ej("max", [50, 80], [[2, 1], [1, 3], [0, 1]], ["≤"] * 3, [100, 90, 40]),
    "Enunciado 2 · min, =, ≥, lado derecho negativo": _ej("min", [4, 1], [[3, 1], [4, 3], [-1, -2]], ["=", "≥", "≥"], [3, 6, -4]),
    "Enunciado 3 · tres variables": _ej("max", [3, 2, 5], [[1, 2, 1], [3, 0, 2], [1, 4, 0]], ["≤"] * 3, [430, 460, 420]),
    "Enunciado 4 · infactible": _ej("max", [1, 1], [[1, 1], [1, 1]], ["≤", "≥"], [2, 5]),
    "Enunciado 5 · no acotado": _ej("max", [1, 1], [[1, -1], [-1, 1]], ["≤"] * 2, [1, 2]),
    "Enunciado 6 · óptimos múltiples": _ej("max", [2, 4], [[1, 2], [1, 1]], ["≤"] * 2, [5, 4]),
    "Enunciado 7 · degeneración": _ej("max", [3, 9], [[1, 4], [1, 2]], ["≤"] * 2, [8, 4]),
    "Clase · Wyndor Glass": _ej("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["≤"] * 3, [4, 12, 18]),
    "Clase · Worldlight": _ej("max", [1, 2], [[1, 3], [2, 2], [0, 1]], ["≤"] * 3, [200, 300, 60]),
    "Clase · terapia (Gran M)": _ej("min", ["0.4", "0.5"], [["0.3", "0.1"], ["0.5", "0.5"], ["0.6", "0.4"]],
                                    ["≤", "=", "≥"], ["2.7", 6, 6]),
}

# --------------------------------------------------------------------------
# Estado: el problema se guarda como texto para no perder lo escrito
# --------------------------------------------------------------------------
ss = st.session_state
if "datos" not in ss:
    ss.datos = dict(EJEMPLOS["Clase · Wyndor Glass"])
    ss.version = 0
    ss.ultimo_ejemplo = "Clase · Wyndor Glass"
    ss.ultimo_archivo = None


def cargar(datos):
    ss.datos = {"sentido": datos["sentido"], "c": list(datos["c"]), "A": [list(f) for f in datos["A"]],
                "signos": list(datos["signos"]), "b": list(datos["b"])}
    ss.n = len(datos["c"])
    ss.m = len(datos["b"])
    ss.sentido_ui = "Maximizar" if datos["sentido"] == "max" else "Minimizar"
    ss.version += 1


def cambiar_dimensiones():
    """Agrega o quita variables/restricciones conservando lo ya escrito."""
    d = ss.datos
    n, m = ss.n, ss.m
    d["c"] = (d["c"] + ["0"] * n)[:n]
    d["A"] = [(fila + ["0"] * n)[:n] for fila in d["A"]]
    d["A"] = (d["A"] + [["0"] * n for _ in range(m)])[:m]
    d["signos"] = (d["signos"] + ["≤"] * m)[:m]
    d["b"] = (d["b"] + ["0"] * m)[:m]
    ss.version += 1


def elegir_ejemplo():
    ej = EJEMPLOS[ss.ejemplo]
    if ej is None:
        cargar({"sentido": "max", "c": ["", ""], "A": [["", ""], ["", ""]], "signos": ["≤", "≤"], "b": ["", ""]})
    else:
        cargar(ej)
    ss.resolver = False


if "n" not in ss:
    ss.n, ss.m = len(ss.datos["c"]), len(ss.datos["b"])
    ss.sentido_ui = "Maximizar" if ss.datos["sentido"] == "max" else "Minimizar"

# --------------------------------------------------------------------------
# Barra lateral
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("1. Problema")
    st.selectbox("Cargar un ejemplo", list(EJEMPLOS), key="ejemplo",
                 index=list(EJEMPLOS).index("Clase · Wyndor Glass"), on_change=elegir_ejemplo)
    archivo = st.file_uploader("…o abrir un problema guardado (JSON)", type=["json"])
    if archivo is not None:
        contenido = archivo.getvalue()
        h = hashlib.md5(contenido).hexdigest()
        if h != ss.ultimo_archivo:
            ss.ultimo_archivo = h
            try:
                cargar(json_a_problema(contenido.decode("utf-8")))
                st.success("Problema cargado.")
            except (ValueError, UnicodeDecodeError) as e:
                st.error(f"No se pudo abrir el archivo: {e}")

    st.number_input("Variables de decisión (n)", 1, 10, key="n", on_change=cambiar_dimensiones)
    st.number_input("Restricciones (m)", 1, 15, key="m", on_change=cambiar_dimensiones)
    st.radio("Objetivo", ["Maximizar", "Minimizar"], key="sentido_ui", horizontal=True)
    ss.datos["sentido"] = "max" if ss.sentido_ui == "Maximizar" else "min"

    st.header("2. Modo de solución")
    modo = st.radio("¿Cómo quiere ver la solución?", ["Paso a paso", "Solución directa"],
                    help="Paso a paso: forma aumentada y cada tablero. Directa: solo el resultado.")
    formato = st.radio("Mostrar los números en", ["Fracciones", "Decimales"], horizontal=True,
                       help="Los cálculos siempre se hacen con fracciones exactas; esto solo cambia "
                            "cómo se muestran los resultados.")
    if formato == "Decimales":
        cifras = st.select_slider("Cifras decimales", options=[2, 3, 4], value=3)
        usar_decimales(cifras)
    else:
        usar_decimales(None)

    st.download_button("💾 Guardar problema (JSON)", problema_a_json(ss.datos),
                       file_name="problema_pl.json", mime="application/json", width="stretch")
    st.caption("Números: enteros, decimales (0.5) o fracciones (2/3). Todas las variables son ≥ 0.")

# --------------------------------------------------------------------------
# Entrada del problema
# --------------------------------------------------------------------------
st.title("📐 Solucionador de Programación Lineal")
st.caption("Método de la Gran M paso a paso, método gráfico y análisis de sensibilidad · Optimización · UdeA")

n, m, d = ss.n, ss.m, ss.datos
cols = [f"x{j + 1}" for j in range(n)]

st.subheader(("Maximizar" if d["sentido"] == "max" else "Minimizar") + " Z")
obj = st.data_editor(pd.DataFrame([d["c"]], columns=cols, index=["Coeficiente de costo"]),
                     key=f"obj_{ss.version}", width="stretch")
st.subheader("Sujeto a")
res = st.data_editor(
    pd.DataFrame([fila + [s, bi] for fila, s, bi in zip(d["A"], d["signos"], d["b"])],
                 columns=cols + ["Signo", "Lado derecho"], index=[f"R{i + 1}" for i in range(m)]),
    key=f"res_{ss.version}", width="stretch",
    column_config={"Signo": st.column_config.SelectboxColumn("Signo", options=list(SIGNOS_UI), required=True)})

# Guardar lo escrito en el estado (así no se pierde al cambiar n o m)
d["c"] = [str(obj.iloc[0][c]) if pd.notna(obj.iloc[0][c]) else "" for c in cols]
d["A"] = [[str(res.iloc[i][c]) if pd.notna(res.iloc[i][c]) else "" for c in cols] for i in range(m)]
d["signos"] = [res.iloc[i]["Signo"] if res.iloc[i]["Signo"] in SIGNOS_UI else "≤" for i in range(m)]
d["b"] = [str(res.iloc[i]["Lado derecho"]) if pd.notna(res.iloc[i]["Lado derecho"]) else "" for i in range(m)]

if st.button("Resolver", type="primary", width="stretch"):
    ss.resolver = True


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------
def leer(texto):
    t = str(texto).strip().replace(" ", "")
    if t.count(",") == 1 and "." not in t:
        t = t.replace(",", ".")
    return Fraction(t)


def validar(d):
    errores, avisos = [], []

    def num(texto, donde):
        if str(texto).strip() in ("", "None", "nan"):
            errores.append(f"Falta un valor en {donde}.")
            return None
        try:
            return leer(texto)
        except (ValueError, ZeroDivisionError):
            errores.append(f"«{texto}» en {donde} no es un número válido (use 3, -0.5 o 2/3).")
            return None

    c = [num(v, f"el coeficiente de x{j + 1} en Z") for j, v in enumerate(d["c"])]
    A = [[num(v, f"R{i + 1}, coeficiente de x{j + 1}") for j, v in enumerate(fila)] for i, fila in enumerate(d["A"])]
    b = [num(v, f"el lado derecho de R{i + 1}") for i, v in enumerate(d["b"])]
    if len(A) != len(b) or any(len(f) != len(c) for f in A):
        errores.append("Dimensiones inconsistentes entre la función objetivo y las restricciones.")
    if errores:
        return None, errores, avisos
    for i, fila in enumerate(A):
        if all(v == 0 for v in fila):
            if (d["signos"][i] == "≤" and b[i] < 0) or (d["signos"][i] == "≥" and b[i] > 0) or \
                    (d["signos"][i] == "=" and b[i] != 0):
                avisos.append(f"R{i + 1} tiene todos sus coeficientes en 0 y no se puede cumplir.")
            else:
                avisos.append(f"R{i + 1} tiene todos sus coeficientes en 0: no restringe nada.")
    if all(v == 0 for v in c):
        avisos.append("Todos los coeficientes de Z son 0: cualquier punto factible es óptimo.")
    p = Problema(d["sentido"], c, A, [SIGNOS_UI[s] for s in d["signos"]], b)
    return p, errores, avisos


if not ss.get("resolver"):
    st.info("Escriba el problema (o cargue un ejemplo) y pulse **Resolver**. "
            "Puede editarlo y volver a resolver cuantas veces quiera.")
    st.stop()

problema, errores, avisos_entrada = validar(d)
if errores:
    st.error("**Revise el problema antes de resolver:**\n\n" + "\n".join(f"- {e}" for e in errores))
    st.stop()
for a in avisos_entrada:
    st.warning(a)

r = resolver(problema)
g = grafico.analizar(problema, r.estado)
sens = sensibilidad.analizar(problema, r) if r.estado == "optimo" else None


# --------------------------------------------------------------------------
# Utilidades de presentación
# --------------------------------------------------------------------------
def _var(nombre):
    if nombre[0] in "xSEA" and nombre[1:].isdigit():
        return f"{nombre[0]}_{{{nombre[1:]}}}"
    return nombre


def _tex(x):
    x = Fraction(x)
    if x.denominator == 1:
        return str(x.numerator)
    if mostrando_decimales():
        return fmt(x)
    s = "-" if x < 0 else ""
    return rf"{s}\tfrac{{{abs(x.numerator)}}}{{{x.denominator}}}"


def _tex_m(v):
    """MNum o Fraction en LaTeX."""
    if hasattr(v, "m") and v.m != 0:
        t = fmt(v).replace("M", r"\,M")
        return t
    return _tex(v.a if hasattr(v, "a") else v)


def lado_izq(coefs, nombres, tex=_tex):
    partes = []
    for coef, nom in zip(coefs, nombres):
        es_cero = coef.is_zero() if hasattr(coef, "is_zero") else coef == 0
        if es_cero:
            continue
        txt = tex(coef)
        neg = txt.startswith("-")
        cuerpo = txt[1:] if neg else txt
        if hasattr(coef, "m") and coef.m != 0 and coef.a != 0:
            cuerpo, neg = f"({txt})", False
        if cuerpo == "1":
            cuerpo = ""
        if not partes:
            partes.append(("-" if neg else "") + cuerpo + _var(nom))
        else:
            partes.append((" - " if neg else " + ") + cuerpo + _var(nom))
    return "".join(partes) or "0"


def modelo_latex(p):
    sentido = r"\max" if p.sentido == "max" else r"\min"
    lineas = [rf"{sentido}\; Z &= {lado_izq(p.c, p.nombres)}\\[2pt]"]
    for fila, s, bi in zip(p.A, p.signos, p.b):
        op = {"<=": r"\le", ">=": r"\ge", "=": "="}[s]
        lineas.append(rf"{lado_izq(fila, p.nombres)} &{op} {_tex(bi)}\\")
    lineas.append(", ".join(_var(nm) for nm in p.nombres) + r" &\ge 0")
    return r"\begin{aligned}" + "\n".join(lineas) + r"\end{aligned}"


def modelo_texto(p):
    def lado(coefs):
        partes = []
        for coef, nom in zip(coefs, p.nombres):
            if coef == 0:
                continue
            c = "" if abs(coef) == 1 else fmt(abs(coef))
            partes.append(("- " if coef < 0 else ("+ " if partes else "")) + f"{c}{nom}")
        return " ".join(partes) or "0"
    lineas = [("Max" if p.sentido == "max" else "Min") + " Z = " + lado(p.c), "Sujeto a:"]
    lineas += [f"R{i + 1}: {lado(f)} {SIGNO_TXT[s]} {fmt(bi)}" for i, (f, s, bi) in enumerate(zip(p.A, p.signos, p.b))]
    lineas.append(", ".join(p.nombres) + " ≥ 0")
    return "\n".join(lineas)


def forma_aumentada_latex(r, p):
    it0 = r.iteraciones[0]
    etq = "Z" if p.sentido == "max" else "-Z"
    lineas = []
    # Renglón 0 tal como se planteó (antes de quitar la M de las artificiales)
    r0 = lado_izq(it0.renglon0, it0.columnas, tex=_tex_m)
    lineas.append(rf"{etq} + {r0} &= 0 \quad (R_0)\\[3pt]" if not r0.startswith("-")
                  else rf"{etq} {r0} &= 0 \quad (R_0)\\[3pt]")
    for i in range(len(it0.basicas)):
        lineas.append(rf"{lado_izq(it0.filas[i], it0.columnas)} &= {_tex(it0.rhs[i])} \quad (R_{{{i + 1}}})\\")
    lineas.append(", ".join(_var(c) for c in it0.columnas) + r" &\ge 0")
    return r"\begin{aligned}" + "\n".join(lineas) + r"\end{aligned}"


def tablero_df(it, sentido):
    etq = "Z (R0)" if sentido == "max" else "-Z (R0)"
    filas = [[etq] + [fmt(v) for v in it.renglon0] + [fmt(it.z)]]
    for i, nb in enumerate(it.basicas):
        filas.append([f"{nb} (R{i + 1})"] + [fmt(v) for v in it.filas[i]] + [fmt(it.rhs[i])])
    return pd.DataFrame(filas, columns=["Básica"] + it.columnas + ["Lado derecho"])


def estilo_tablero(df, it):
    col_piv = it.entra
    fila_piv = it.pivote[0] if it.pivote else None

    def color(data):
        e = pd.DataFrame("", index=data.index, columns=data.columns)
        if col_piv in data.columns:
            e[col_piv] = "background-color: rgba(59,130,246,0.18)"
        if fila_piv is not None:
            e.iloc[fila_piv, :] = "background-color: rgba(16,185,129,0.18)"
            if col_piv in data.columns:
                e.loc[fila_piv, col_piv] = "background-color: rgba(245,158,11,0.6); font-weight: 700"
        return e

    return df.style.apply(color, axis=None)


def lim(v, menos=False):
    if v is None:
        return "−∞" if menos else "∞"
    return fmt(v)


def aprox(v):
    f = float(v)
    return "" if f == int(f) else f" ≈ {f:.4g}"


# --------------------------------------------------------------------------
# Resultados
# --------------------------------------------------------------------------
st.divider()
nombres_tabs = ["✅ Solución"]
if modo == "Paso a paso":
    nombres_tabs.append("🧮 Paso a paso")
nombres_tabs += ["📈 Método gráfico", "🔍 Análisis de sensibilidad", "📄 Exportar"]
tabs = dict(zip(nombres_tabs, st.tabs(nombres_tabs)))

# ---------------- Solución ----------------
with tabs["✅ Solución"]:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("##### Formulación")
        st.latex(modelo_latex(problema))
    with c2:
        st.markdown("##### ¿Está en forma estándar?")
        ok, razones = problema.en_forma_estandar()
        if ok:
            st.success("Sí: maximización, todas las restricciones ≤, lados derechos ≥ 0 y variables ≥ 0. "
                       "Basta el simplex básico (no aparecen variables artificiales).")
        else:
            st.warning("No. " + " ".join(razones) + " Se resuelve con el método de la **Gran M**.")

    st.markdown("##### Resultado")
    if r.estado == "infactible":
        st.error("**El problema no tiene solución factible.** Ninguna combinación de valores cumple todas las "
                 "restricciones a la vez. " + r.mensaje)
    elif r.estado == "no_acotado":
        st.error("**Solución no acotada.** Z puede mejorar sin límite; revise si falta alguna restricción. "
                 + r.mensaje)
    else:
        st.success(r.mensaje)
        dec = {k: v for k, v in r.valores.items() if r.tipos[k] == "decision"}
        cm_ = st.columns(min(len(dec), 6) + 1)
        for col, (nombre, valor) in zip(cm_, dec.items()):
            col.metric(nombre, fmt(valor), help=f"≈ {float(valor):.6g}")
        cm_[-1].metric("Z " + ("máxima" if problema.sentido == "max" else "mínima"), fmt(r.z),
                       help=f"≈ {float(r.z):.6g}")

        if r.multiples:
            alt = r.alternativa
            punto = ", ".join(f"{k} = {fmt(v)}" for k, v in dec.items())
            otro = ", ".join(f"{k} = {fmt(v)}" for k, v in alt.items())
            st.info(f"**Soluciones óptimas múltiples.** Además de ({punto}), también es óptimo ({otro}), y todo "
                    f"el segmento que los une (combinación convexa): todos dan Z = {fmt(r.z)}.")
        for a in r.avisos:
            st.info(a)

        st.markdown("##### Holgura o exceso de cada restricción")
        filas = []
        for i in range(m):
            x = [r.valores[v] for v in problema.nombres]
            lhs = sum(problema.A[i][j] * x[j] for j in range(n))
            s = problema.signos[i]
            if s == "<=":
                tipo, val = "Holgura (recurso sin usar)", problema.b[i] - lhs
            elif s == ">=":
                tipo, val = "Exceso (sobre el mínimo)", lhs - problema.b[i]
            else:
                tipo, val = "—", Fraction(0)
            filas.append([f"R{i + 1}", f"{fmt(lhs)} {SIGNO_TXT[s]} {fmt(problema.b[i])}", tipo, fmt(val),
                          "Sí" if val == 0 else "No"])
        st.dataframe(pd.DataFrame(filas, columns=["Restricción", "Valor en el óptimo", "Tipo", "Cantidad",
                                                  "¿Activa?"]), hide_index=True, width="stretch")
        st.caption("Una restricción activa se cumple con igualdad: es la que limita la solución.")
    if modo == "Solución directa":
        st.caption("Para ver la forma aumentada y cada tablero, elija **Paso a paso** en la barra lateral.")

# ---------------- Paso a paso ----------------
if "🧮 Paso a paso" in tabs:
    with tabs["🧮 Paso a paso"]:
        st.markdown("##### 1. Preparación")
        for paso in r.preparacion:
            st.markdown(f"- {paso}")
        st.markdown("##### 2. Forma aumentada")
        tipos_txt = {"decision": "decisión", "holgura": "holgura", "exceso": "exceso", "artificial": "artificial"}
        st.latex(forma_aumentada_latex(r, problema))
        st.caption("Variables: " + ", ".join(f"{k} ({tipos_txt[v]})" for k, v in r.tipos.items()))

        st.markdown("##### 3. Tableros")
        st.caption("🟦 columna pivote (entra) · 🟩 renglón pivote (sale) · 🟧 número pivote")
        for k, it in enumerate(r.iteraciones):
            if k == 0 and len(r.iteraciones) > 1 and r.iteraciones[1].numero == 0:
                titulo = "Tablero inicial (con la penalización M)"
            else:
                titulo = f"Iteración {it.numero}"
            ultimo = k == len(r.iteraciones) - 1
            if ultimo:
                titulo += " — tablero final"
            with st.expander(titulo, expanded=True):
                if it.nota:
                    st.caption(it.nota)
                st.dataframe(estilo_tablero(tablero_df(it, problema.sentido), it), hide_index=True,
                             width="stretch")
                st.markdown(f"**Variables básicas:** {', '.join(it.basicas)} · **Valor actual:** "
                            f"{'Z' if problema.sentido == 'max' else '-Z'} = {fmt(it.z)}")
                if it.entra:
                    negs = [f"{c} ({fmt(v)})" for c, v in zip(it.columnas, it.renglon0) if v < 0]
                    st.markdown(f"**¿Es óptimo?** No: hay coeficientes negativos en el renglón 0: {', '.join(negs)}.")
                    st.markdown(f"**Entra {it.entra}:** tiene el coeficiente más negativo (mayor valor absoluto "
                                f"entre los negativos), es decir, es la que más mejora Z por unidad.")
                    st.markdown("**Prueba de la razón mínima** (lado derecho ÷ coeficiente positivo de la columna):")
                    for fila, texto in it.cocientes:
                        st.markdown(f"- R{fila}: {texto}")
                    if it.sale:
                        st.markdown(f"**Sale {it.sale}:** su renglón (R{it.pivote[0]}) tiene la menor razón; es "
                                    f"la primera restricción que se vuelve activa al aumentar {it.entra}. "
                                    f"**Número pivote:** renglón {it.pivote[0]}, columna {it.pivote[1]}.")
                    else:
                        st.markdown(f"**Ninguna variable puede salir:** la columna de {it.entra} no tiene "
                                    "coeficientes positivos, así que la variable puede crecer sin límite.")
                elif ultimo and r.estado != "no_acotado":
                    st.markdown("**Prueba de optimalidad:** no hay coeficientes negativos en el renglón 0.")
                if it.operaciones:
                    st.markdown("**Operaciones de renglón:** " + " · ".join(f"`{op}`" for op in it.operaciones))

        st.markdown("##### 4. Conclusión")
        if r.estado == "optimo":
            st.success(r.mensaje)
            if problema.sentido == "min":
                st.caption(f"Como se maximizó -Z, el valor de Z es el del tablero con el signo cambiado: Z = {fmt(r.z)}.")
        elif r.estado == "infactible":
            st.error(r.mensaje)
        else:
            st.error(r.mensaje)

# ---------------- Método gráfico ----------------
fig_png = None
with tabs["📈 Método gráfico"]:
    if not g.aplica:
        st.info(g.mensaje)
    else:
        fig = grafico.dibujar(problema, g)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        fig_png = buf.getvalue()
        import matplotlib.pyplot as plt
        plt.close(fig)
        c1, c2 = st.columns([3, 2])
        with c1:
            st.image(fig_png, width="stretch")
        with c2:
            (st.success if g.estado == "optimo" else st.error)(g.mensaje)
            if g.vertices:
                st.markdown("**Vértices de la región factible y su Z**")
                st.dataframe(pd.DataFrame(
                    [[f"({fmt(v.x1)}, {fmt(v.x2)})", fmt(v.z), ", ".join(v.rectas), "⭐" if v.optimo else ""]
                     for v in g.vertices], columns=["(x₁, x₂)", "Z", "Rectas que se cruzan", "Óptimo"]),
                    hide_index=True, width="stretch")
            if g.redundantes:
                st.info(f"Restricción(es) redundante(s): {', '.join(g.redundantes)}. No tocan la región factible; "
                        "si se eliminan, la solución no cambia (se dibujan punteadas).")
            if not g.acotada and g.estado != "infactible":
                st.caption("La región factible no está acotada: se dibuja recortada a la ventana.")
            st.caption("Los puntos grises (×) son cruces de rectas que no son factibles.")

# ---------------- Sensibilidad ----------------
with tabs["🔍 Análisis de sensibilidad"]:
    if sens is None:
        st.info("El análisis de sensibilidad se hace sobre el tablero final de una solución óptima; "
                "este problema no la tiene.")
    else:
        st.caption("Se parte del tablero final. Cada rango supone que solo cambia **un** dato a la vez "
                   "(cambio marginal). Dentro del rango, la base óptima no cambia y no hay que resolver de nuevo.")
        st.markdown("##### Lados derechos (recursos)")
        st.dataframe(pd.DataFrame(
            [[f"R{x.restriccion}", SIGNO_TXT[x.tipo], fmt(x.actual), lim(x.minimo, True), lim(x.maximo),
              fmt(x.precio_sombra) + aprox(x.precio_sombra), fmt(x.holgura), "Sí" if x.activa else "No"]
             for x in sens.recursos],
            columns=["Restricción", "Tipo", "Valor actual", "Mínimo", "Máximo", "Precio sombra",
                     "Holgura / exceso", "¿Activa?"]), hide_index=True, width="stretch")
        st.markdown("##### Coeficientes de la función objetivo")
        st.dataframe(pd.DataFrame(
            [[x.variable, fmt(x.actual), lim(x.minimo, True), lim(x.maximo), fmt(x.valor),
              fmt(x.costo_reducido), "Sí" if x.basica else "No"] for x in sens.costos],
            columns=["Variable", "Valor actual", "Mínimo", "Máximo", "Valor en el óptimo", "Costo reducido",
                     "¿Básica?"]), hide_index=True, width="stretch")

        st.markdown("##### Interpretación")
        verbo = "aumenta" if problema.sentido == "max" else "cambia"
        for x in sens.recursos:
            rango = f"entre {lim(x.minimo, True)} y {lim(x.maximo)}"
            if x.precio_sombra != 0:
                efecto = "aumenta" if x.precio_sombra > 0 else "disminuye"
                st.markdown(f"- **R{x.restriccion}** (precio sombra {fmt(x.precio_sombra)}): por cada unidad más "
                            f"en su lado derecho, Z {efecto} en {fmt(abs(x.precio_sombra))}. Vale mientras el lado "
                            f"derecho esté {rango}.")
            else:
                st.markdown(f"- **R{x.restriccion}** (precio sombra 0): no limita la solución "
                            f"(holgura/exceso = {fmt(x.holgura)}); si su lado derecho se mueve {rango}, "
                            "Z no cambia.")
        for x in sens.costos:
            rango = f"entre {lim(x.minimo, True)} y {lim(x.maximo)}"
            if x.basica:
                st.markdown(f"- **{x.variable}** = {fmt(x.valor)}: su coeficiente puede variar {rango} sin que "
                            "cambie la solución óptima (solo cambia el valor de Z).")
            elif x.costo_reducido == 0:
                st.markdown(f"- **{x.variable}** = 0 (no básica) con costo reducido 0: puede entrar a la base "
                            "sin cambiar Z; por eso hay soluciones óptimas múltiples. Mientras su coeficiente "
                            f"esté {rango}, esta solución sigue siendo óptima.")
            else:
                st.markdown(f"- **{x.variable}** = 0 (no básica): su coeficiente debe mejorar en "
                            f"{fmt(x.costo_reducido)} (costo reducido) para que convenga producirla; "
                            f"mientras esté {rango}, sigue en 0.")
        for a in sens.avisos:
            st.info(a)
        with st.expander("Ver B⁻¹ del tablero final (simplex revisado)"):
            st.caption(f"Variables básicas (en orden de renglón): {', '.join(sens.basicas)}. "
                       "B⁻¹ está en las columnas de las variables que formaron la identidad al inicio.")
            st.dataframe(pd.DataFrame([[fmt(v) for v in fila] for fila in sens.B_inv],
                                      columns=[f"col {i + 1}" for i in range(m)],
                                      index=[f"R{i + 1}" for i in range(m)]), width="stretch")

# ---------------- Exportar ----------------
with tabs["📄 Exportar"]:
    st.markdown("Descargue la solución completa (paso a paso, gráfico y sensibilidad) o el problema "
                "para abrirlo después.")
    try:
        pdf = generar_pdf(problema, r, sens, g, fig_png, modelo_texto(problema))
        st.download_button("📄 Descargar solución en PDF", pdf, file_name="solucion_pl.pdf",
                           mime="application/pdf", type="primary")
    except Exception as e:  # el PDF nunca debe tumbar la aplicación
        st.warning(f"No se pudo generar el PDF: {e}")
    st.download_button("💾 Descargar problema (JSON)", problema_a_json(ss.datos), file_name="problema_pl.json",
                       mime="application/json")
