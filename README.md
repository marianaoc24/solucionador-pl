# Solucionador de Programación Lineal

Aplicación con interfaz gráfica que resuelve problemas de programación lineal por el **método de la Gran M**, mostrando el proceso completo paso a paso. Proyecto del curso **Optimización** — Universidad de Antioquia, 2026-2.

**Integrantes:**
- Mariana Ospina Cardona
- Yasiris Mercado

**Aplicación en línea:** _(URL de Streamlit Cloud)_

## Qué hace

| Requisito del enunciado | Dónde está |
|---|---|
| Recibe Max/Min, n variables, m restricciones (≤, ≥, =) y lados derechos de cualquier signo; valida la entrada | Barra lateral y tablas de entrada (`app.py`) |
| Método propio: Gran M | `simplex.py` |
| Modo **solución directa** o **paso a paso** (forma aumentada, entrante, razón mínima, saliente, pivote, tablero) | Barra lateral → *Modo de solución*; pestaña *Paso a paso* |
| Solución óptima: variables, Z, holgura o exceso de cada restricción | Pestaña *Solución* |
| Método gráfico (2 variables): región factible, vértices con su Z, recta de Z en el óptimo; aviso si n > 2 | `grafico.py`; pestaña *Método gráfico* |
| Análisis de sensibilidad: precios sombra, costos reducidos, rangos de c y de b | `sensibilidad.py`; pestaña *Análisis de sensibilidad* |
| Casos especiales: infactible, no acotado, óptimos múltiples, degenerado | Mensajes en *Solución* y *Paso a paso* |
| **Bonificaciones:** fracciones exactas con opción de verlas en decimales (2, 3 o 4 cifras), exportar a PDF, guardar/cargar JSON | `simplex.py` (`usar_decimales`), `exportar.py`; barra lateral y pestaña *Exportar* |

## Requisitos

- Python 3.10 o superior
- Las librerías de `requirements.txt` (Streamlit, pandas, matplotlib, reportlab)

## Instalación y ejecución

```bash
git clone https://github.com/marianaoc24/solucionador-pl.git
cd solucionador-pl
pip install -r requirements.txt
streamlit run app.py
```

La aplicación se abre en el navegador en `http://localhost:8501`.

## Estructura del código

| Archivo | Contenido |
|---|---|
| `simplex.py` | Números con M (`MNum`), el modelo (`Problema`) y el método de la Gran M paso a paso (`resolver`) |
| `sensibilidad.py` | Precios sombra, costos reducidos y rangos a partir del tablero final (B⁻¹) |
| `grafico.py` | Vértices, región factible y dibujo del método gráfico |
| `exportar.py` | PDF de la solución y lectura/escritura de problemas en JSON |
| `app.py` | Interfaz gráfica (Streamlit) |
| `pruebas/` | Pruebas automáticas |

## Cómo funciona el método (resumen)

1. Si un lado derecho es negativo, la restricción se multiplica por −1 (y si es desigualdad, cambia el sentido).
2. Minimizar Z equivale a maximizar −Z.
3. Restricción ≤ → + holgura (S). Restricción ≥ → − exceso (E) + artificial (A). Restricción = → + artificial (A).
4. Las artificiales se penalizan con −M y se elimina la M de sus columnas para que las básicas formen la identidad.
5. En cada iteración entra la variable con el coeficiente más negativo del renglón 0, sale la de menor razón mínima, y se hacen las operaciones de renglón. Se termina cuando no hay negativos en el renglón 0.
6. Si al final queda una artificial con valor positivo, el problema es infactible.

Todos los cálculos usan fracciones exactas (`fractions.Fraction`). La opción *Decimales* de la barra lateral solo cambia cómo se muestran los números, no los cálculos.

## Pruebas

```bash
python pruebas/test_simplex.py     # ejemplos de clase
python pruebas/verificar_scipy.py  # compara con scipy (solo verificación) en 300 problemas aleatorios
python pruebas/test_app.py         # recorre la interfaz con todos los ejemplos
python pruebas/test_extras.py      # validación, cambio de dimensiones, JSON y PDF
```

scipy se usa **solo para verificar** los resultados en las pruebas, nunca para resolver en la aplicación (`pip install scipy` para correr esa prueba).

## Formato JSON de un problema

```json
{
  "sentido": "min",
  "c": ["4", "1"],
  "A": [["3", "1"], ["4", "3"], ["-1", "-2"]],
  "signos": ["=", "≥", "≥"],
  "b": ["3", "6", "-4"]
}
```

## Referencias

- Hillier, F. y Lieberman, G. *Introducción a la Investigación de Operaciones*. McGraw-Hill.
- Diapositivas del curso Optimización, prof. Ronald Ortiz, UdeA.
