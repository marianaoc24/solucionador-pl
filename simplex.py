"""
Método Simplex tabular con Gran M, paso a paso.

Sigue el procedimiento visto en clase (Optimización, UdeA):
  1. Si algún lado derecho es negativo, se multiplica la restricción por -1
     (y si es desigualdad, cambia el sentido).
  2. Minimizar Z  equivale a  maximizar -Z.
  3. Restricción <=  -> + variable de holgura (S)
     Restricción >=  -> - variable de exceso (E) + variable artificial (A)
     Restricción  =  -> + variable artificial (A)
  4. Las artificiales se penalizan con -M en la función objetivo (maximización).
  5. Renglón 0:  Z - c·x + M·A = 0, y luego se elimina la M de las columnas
     artificiales para que las variables básicas formen la identidad.
  6. Iterar:
       - Entra la variable con el coeficiente más negativo del renglón 0
         (mayor valor absoluto entre los negativos).
       - Sale la que gane la prueba del cociente mínimo (solo divisores > 0).
       - Se divide el renglón pivote entre el número pivote y se hacen 0
         los demás elementos de la columna pivote.
     hasta que no haya coeficientes negativos en el renglón 0.

Todos los cálculos se hacen con fracciones exactas para que los tableros
se vean igual que en las diapositivas (2/3, 5/6, ...).
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from fractions import Fraction

# Cómo se MUESTRAN los números: None = fracciones exactas; un entero = cifras decimales.
# Los cálculos siempre se hacen con fracciones exactas; esto solo cambia el texto.
_CIFRAS: ContextVar = ContextVar("cifras_decimales", default=None)


def usar_decimales(cifras: int | None) -> None:
    """None para mostrar fracciones (2/3); un número para mostrar decimales (0.667)."""
    _CIFRAS.set(cifras)


def mostrando_decimales() -> bool:
    return _CIFRAS.get() is not None


# --------------------------------------------------------------------------
# Números de la forma  a + b·M  (para la Gran M)
# --------------------------------------------------------------------------
class MNum:
    """Número simbólico a + b·M, donde M es 'muy grande'.

    Se compara primero por el coeficiente de M y, si empatan, por la parte
    constante. Así funciona la regla de clase: 'la M domina'.
    """

    __slots__ = ("a", "m")

    def __init__(self, a=0, m=0):
        self.a = Fraction(a)
        self.m = Fraction(m)

    @staticmethod
    def of(x) -> "MNum":
        return x if isinstance(x, MNum) else MNum(x, 0)

    def __add__(self, o):
        o = MNum.of(o)
        return MNum(self.a + o.a, self.m + o.m)

    __radd__ = __add__

    def __sub__(self, o):
        o = MNum.of(o)
        return MNum(self.a - o.a, self.m - o.m)

    def __rsub__(self, o):
        return MNum.of(o) - self

    def __neg__(self):
        return MNum(-self.a, -self.m)

    def __mul__(self, k):
        if isinstance(k, MNum):
            if k.m != 0 and self.m != 0:
                raise ValueError("No se puede multiplicar M por M")
            if k.m == 0:
                k = k.a
            else:
                return MNum(self.a * k.a, self.a * k.m)
        k = Fraction(k)
        return MNum(self.a * k, self.m * k)

    __rmul__ = __mul__

    def _key(self):
        return (self.m, self.a)

    def __lt__(self, o):
        return self._key() < MNum.of(o)._key()

    def __le__(self, o):
        return self._key() <= MNum.of(o)._key()

    def __gt__(self, o):
        return self._key() > MNum.of(o)._key()

    def __ge__(self, o):
        return self._key() >= MNum.of(o)._key()

    def __eq__(self, o):
        try:
            return self._key() == MNum.of(o)._key()
        except (TypeError, ValueError):
            return NotImplemented

    def __hash__(self):
        return hash(self._key())

    def is_zero(self):
        return self.a == 0 and self.m == 0

    def __abs__(self):
        return -self if self < 0 else self

    def __repr__(self):
        return fmt(self)


def fmt_frac(x: Fraction) -> str:
    x = Fraction(x)
    if x.denominator == 1:
        return str(x.numerator)
    cifras = _CIFRAS.get()
    if cifras is not None:
        texto = f"{float(x):.{cifras}f}".rstrip("0").rstrip(".")
        if texto in ("0", "-0", ""):           # muy pequeño, pero no es cero
            return f"{float(x):.{cifras}g}"
        return texto
    return f"{x.numerator}/{x.denominator}"


def fmt(x) -> str:
    """Texto de un número, en fracción. Para MNum: '-11/10 M + 2/5'."""
    if not isinstance(x, MNum):
        return fmt_frac(Fraction(x))
    if x.m == 0:
        return fmt_frac(x.a)
    if x.m == 1:
        mt = "M"
    elif x.m == -1:
        mt = "-M"
    else:
        mt = f"{fmt_frac(x.m)}M"
    if x.a == 0:
        return mt
    sign = "+" if x.a > 0 else "-"
    return f"{mt} {sign} {fmt_frac(abs(x.a))}"


# --------------------------------------------------------------------------
# Modelo y resultados
# --------------------------------------------------------------------------
@dataclass
class Problema:
    """Problema de programación lineal tal como se formula en clase.

    sentido:  "max" o "min"
    c:        coeficientes de costo  (lista de n números)
    A:        coeficientes tecnológicos (m listas de n números)
    signos:   "<=", ">=" o "=" para cada restricción
    b:        lado derecho (recursos)
    Todas las variables de decisión se asumen >= 0.
    """

    sentido: str
    c: list
    A: list
    signos: list
    b: list
    nombres: list | None = None

    def __post_init__(self):
        self.c = [Fraction(v) for v in self.c]
        self.A = [[Fraction(v) for v in fila] for fila in self.A]
        self.b = [Fraction(v) for v in self.b]
        self.sentido = self.sentido.lower()
        n = len(self.c)
        if self.sentido not in ("max", "min"):
            raise ValueError("El sentido debe ser 'max' o 'min'")
        if any(len(f) != n for f in self.A):
            raise ValueError("Cada restricción debe tener un coeficiente por variable")
        if len(self.A) != len(self.b) or len(self.b) != len(self.signos):
            raise ValueError("A, signos y b deben tener el mismo número de restricciones")
        for s in self.signos:
            if s not in ("<=", ">=", "="):
                raise ValueError(f"Signo no válido: {s}")
        if self.nombres is None:
            self.nombres = [f"x{j + 1}" for j in range(n)]

    def en_forma_estandar(self) -> tuple[bool, list[str]]:
        """Las 4 condiciones de clase. Devuelve (cumple, razones si no cumple)."""
        razones = []
        if self.sentido != "max":
            razones.append("La función objetivo no es de maximización.")
        if any(s != "<=" for s in self.signos):
            razones.append("No todas las restricciones son de tipo ≤.")
        if any(v < 0 for v in self.b):
            razones.append("Hay lados derechos (recursos) negativos.")
        # La no negatividad de las variables se asume siempre.
        return (not razones, razones)


@dataclass
class Iteracion:
    numero: int
    columnas: list            # nombres de las columnas (variables)
    basicas: list             # variable básica de cada renglón 1..m
    renglon0: list            # coeficientes del renglón 0 (MNum)
    z: MNum                   # lado derecho del renglón 0
    filas: list               # renglones 1..m (Fraction)
    rhs: list                 # lado derecho de los renglones 1..m
    entra: str | None = None
    sale: str | None = None
    cocientes: list = field(default_factory=list)   # (renglón, texto)
    pivote: tuple | None = None                    # (renglón, columna)
    operaciones: list = field(default_factory=list) # texto de operaciones
    nota: str = ""


@dataclass
class Resultado:
    estado: str                    # "optimo", "no_acotado", "infactible"
    iteraciones: list
    preparacion: list              # pasos de conversión (texto)
    valores: dict                  # valor de cada variable
    z: Fraction | None
    multiples: bool = False
    columnas: list = field(default_factory=list)
    tipos: dict = field(default_factory=dict)      # nombre -> decision/holgura/exceso/artificial
    base_final: list = field(default_factory=list)
    mensaje: str = ""
    sentido: str = "max"
    signo_fila: list = field(default_factory=list)     # -1 si la restricción se multiplicó por -1
    signos_mod: list = field(default_factory=list)     # tipo de cada restricción tras la conversión
    basica_inicial: list = field(default_factory=list) # variable que formó la identidad en cada renglón
    holgura_de_fila: list = field(default_factory=list)  # S o E de cada restricción (None si es =)
    degenerado: bool = False
    alternativa: dict | None = None    # otra solución óptima (vértice) si hay óptimos múltiples
    avisos: list = field(default_factory=list)

    @property
    def final(self):
        return self.iteraciones[-1]


# --------------------------------------------------------------------------
# Método simplex
# --------------------------------------------------------------------------
def resolver(p: Problema, max_iter: int = 100) -> Resultado:
    preparacion: list[str] = []
    n = len(p.c)
    m = len(p.b)

    A = [fila[:] for fila in p.A]
    b = p.b[:]
    signos = p.signos[:]

    # 1. Lados derechos negativos
    signo_fila = [1] * m
    for i in range(m):
        if b[i] < 0:
            signo_fila[i] = -1
            A[i] = [-v for v in A[i]]
            b[i] = -b[i]
            antes = signos[i]
            signos[i] = {"<=": ">=", ">=": "<=", "=": "="}[antes]
            preparacion.append(
                f"La restricción {i + 1} tiene lado derecho negativo: se multiplica por -1"
                + (f" y pasa de {_SIG[antes]} a {_SIG[signos[i]]}." if antes != "=" else ".")
            )

    # 2. Minimización
    c = p.c[:]
    if p.sentido == "min":
        c = [-v for v in c]
        preparacion.append("Minimizar Z equivale a maximizar -Z: se multiplica la función objetivo por -1.")

    # 3. Variables adicionales
    columnas = list(p.nombres)
    tipos = {nombre: "decision" for nombre in columnas}
    filas = [list(fila) for fila in A]
    basicas: list[str] = [""] * m
    artificiales: list[int] = []   # renglones con artificial
    holgura_de_fila: list = [None] * m
    ns = ne = nr = 0

    def nueva_columna(nombre, tipo, fila_uno, valor):
        columnas.append(nombre)
        tipos[nombre] = tipo
        for k in range(m):
            filas[k].append(Fraction(valor) if k == fila_uno else Fraction(0))

    for i in range(m):
        if signos[i] == "<=":
            ns += 1
            nombre = f"S{ns}"
            nueva_columna(nombre, "holgura", i, 1)
            basicas[i] = nombre
            holgura_de_fila[i] = nombre
            preparacion.append(f"Restricción {i + 1} (≤): se suma la variable de holgura {nombre}.")
        elif signos[i] == ">=":
            ne += 1
            nr += 1
            ex, ar = f"E{ne}", f"A{nr}"
            nueva_columna(ex, "exceso", i, -1)
            nueva_columna(ar, "artificial", i, 1)
            basicas[i] = ar
            holgura_de_fila[i] = ex
            artificiales.append(i)
            preparacion.append(
                f"Restricción {i + 1} (≥): se resta la variable de exceso {ex} y se suma la artificial {ar}."
            )
        else:
            nr += 1
            ar = f"A{nr}"
            nueva_columna(ar, "artificial", i, 1)
            basicas[i] = ar
            artificiales.append(i)
            preparacion.append(f"Restricción {i + 1} (=): se suma la variable artificial {ar}.")

    total = len(columnas)
    basica_inicial = basicas[:]
    avisos: list[str] = []
    hubo_empate_salida = False

    # 4-5. Renglón 0:  Z - c·x + M·A = 0
    r0 = [MNum(0)] * total
    for j in range(n):
        r0[j] = MNum(-c[j])
    for j, nombre in enumerate(columnas):
        if tipos[nombre] == "artificial":
            r0[j] = MNum(0, 1)
    z = MNum(0)
    if artificiales:
        preparacion.append("Las variables artificiales se penalizan con -M en la función objetivo.")

    iteraciones: list[Iteracion] = []

    def foto(num, nota=""):
        return Iteracion(
            numero=num,
            columnas=columnas[:],
            basicas=basicas[:],
            renglon0=r0[:],
            z=z,
            filas=[f[:] for f in filas],
            rhs=b[:],
            nota=nota,
        )

    if artificiales:
        # Tablero antes de eliminar la M de las columnas artificiales
        iteraciones.append(foto(0, "Tablero inicial con la penalización M (todavía no se forma la identidad)."))
        ops = []
        for i in artificiales:
            r0 = [r0[j] - MNum(0, 1) * filas[i][j] for j in range(total)]
            z = z - MNum(0, 1) * b[i]
            ops.append(f"R0 = R0 - M·R{i + 1}")
        iteraciones[-1].operaciones = ops
        iteraciones.append(foto(0, "Renglón 0 sin M en las columnas artificiales: las básicas forman la identidad."))
    else:
        iteraciones.append(foto(0, "Tablero inicial: las variables de holgura forman la identidad."))

    estado = "optimo"
    mensaje = ""
    for it in range(1, max_iter + 1):
        actual = iteraciones[-1]
        # Prueba de optimalidad
        negativos = [j for j in range(total) if r0[j] < 0]
        if not negativos:
            break
        # Variable que entra: la más negativa (desempate: la primera)
        e = min(negativos, key=lambda j: (r0[j], j))
        empatadas = [columnas[j] for j in negativos if r0[j] == r0[e]]
        if len(empatadas) > 1:
            actual.nota = (actual.nota + " " if actual.nota else "") + (
                f"Empate en la variable que entra ({', '.join(empatadas)}): "
                f"la elección es arbitraria; se escoge {columnas[e]}.")
        # Prueba del cociente mínimo
        cocientes = []
        mejor = None
        for i in range(m):
            coef = filas[i][e]
            if coef > 0:
                q = b[i] / coef
                cocientes.append((i + 1, f"{_paren(b[i])} ÷ {_paren(coef)} = {fmt(q)}"))
                if mejor is None or q < mejor[0]:
                    mejor = (q, i)
            else:
                cocientes.append((i + 1, "no se puede (divisor ≤ 0)"))
        actual.entra = columnas[e]
        actual.cocientes = cocientes
        if mejor is None:
            estado = "no_acotado"
            mensaje = (
                f"Ninguna variable puede salir: en la columna de {columnas[e]} no hay coeficientes positivos. "
                "La región factible no está acotada y Z crece sin límite (posible error de formulación)."
            )
            break
        s = mejor[1]
        empate = [i for i in range(m) if filas[i][e] > 0 and b[i] / filas[i][e] == mejor[0]]
        if len(empate) > 1:
            hubo_empate_salida = True
            actual.nota = (actual.nota + " " if actual.nota else "") + (
                "Empate en la prueba de la razón mínima ("
                + ", ".join(f"R{i + 1}" for i in empate)
                + f"): se escoge R{s + 1}. La variable que no sale queda básica con valor 0 (degeneración).")
        actual.sale = basicas[s]
        actual.pivote = (s + 1, columnas[e])
        piv = filas[s][e]

        # Operaciones de renglón
        ops = []
        if piv != 1:
            ops.append(f"R{s + 1} = R{s + 1} ÷ {_paren(piv)}")
        filas[s] = [v / piv for v in filas[s]]
        b[s] = b[s] / piv
        for i in range(m):
            if i == s:
                continue
            k = filas[i][e]
            if k != 0:
                filas[i] = [filas[i][j] - k * filas[s][j] for j in range(total)]
                b[i] = b[i] - k * b[s]
                ops.append(_texto_op(i + 1, k, s + 1))
        k0 = r0[e]
        if not k0.is_zero():
            r0 = [r0[j] - k0 * filas[s][j] for j in range(total)]
            z = z - k0 * b[s]
            ops.append(_texto_op(0, k0, s + 1))
        actual.operaciones = ops
        basicas[s] = columnas[e]
        iteraciones.append(foto(it))
    else:
        estado = "no_acotado"
        mensaje = "Se alcanzó el número máximo de iteraciones (posible ciclo por degeneración)."

    # Valores finales
    valores = {nombre: Fraction(0) for nombre in columnas}
    for i, nombre in enumerate(basicas):
        valores[nombre] = b[i]

    if estado == "optimo":
        art_positivas = [nb for nb in basicas if tipos[nb] == "artificial" and valores[nb] > 0]
        if art_positivas:
            estado = "infactible"
            mensaje = (
                "Una variable artificial quedó con valor positivo en la solución final "
                f"({', '.join(art_positivas)}). El problema no tiene solución factible."
            )

    zval = None
    multiples = False
    alternativa = None
    degenerado = False
    if estado == "optimo":
        en_cero = [nb for nb in basicas if valores[nb] == 0 and tipos[nb] != "artificial"]
        degenerado = bool(en_cero) or hubo_empate_salida
        if degenerado:
            avisos.append(
                "Solución degenerada: "
                + (f"la variable básica {', '.join(en_cero)} vale 0. " if en_cero else "")
                + "Hubo o puede haber empates en la razón mínima; el simplex podría ciclar, "
                  "pero aquí terminó en el óptimo.")
        zval = z.a if p.sentido == "max" else -z.a
        no_basicas = [j for j, nombre in enumerate(columnas)
                      if nombre not in basicas and tipos[nombre] != "artificial"]
        candidatas = [j for j in no_basicas if r0[j].is_zero()]
        mensaje = "No hay coeficientes negativos en el renglón 0: la solución es óptima."
        n_dec = len(p.c)
        actual_dec = tuple(valores[columnas[j]] for j in range(n_dec))
        for j in candidatas:
            otra = _pivote_alternativo(filas, b, basicas, columnas, j)
            if otra is not None and tuple(otra[columnas[k]] for k in range(n_dec)) != actual_dec:
                alternativa = {columnas[k]: otra[columnas[k]] for k in range(n_dec)}
                break
        multiples = alternativa is not None
        if candidatas and not multiples:
            avisos.append(
                "Hay una variable no básica con coeficiente 0 en el renglón 0, pero al hacerla entrar "
                "no cambia el punto (o crece sin límite sin cambiar Z).")
        if multiples:
            mensaje += (" Hay una variable no básica con coeficiente 0 en el renglón 0: "
                        "existen soluciones óptimas múltiples.")

    return Resultado(
        estado=estado,
        iteraciones=iteraciones,
        preparacion=preparacion,
        valores=valores,
        z=zval,
        multiples=multiples,
        columnas=columnas,
        tipos=tipos,
        base_final=basicas[:],
        mensaje=mensaje,
        sentido=p.sentido,
        signo_fila=signo_fila,
        signos_mod=signos,
        basica_inicial=basica_inicial,
        holgura_de_fila=holgura_de_fila,
        degenerado=degenerado,
        alternativa=alternativa,
        avisos=avisos,
    )


def _pivote_alternativo(filas, b, basicas, columnas, e):
    """Hace entrar la columna e (sobre copias) y devuelve los nuevos valores, o None."""
    m = len(filas)
    mejor = None
    for i in range(m):
        if filas[i][e] > 0:
            q = b[i] / filas[i][e]
            if mejor is None or q < mejor[0]:
                mejor = (q, i)
    if mejor is None:
        return None
    s = mejor[1]
    piv = filas[s][e]
    f = [fila[:] for fila in filas]
    bb = b[:]
    f[s] = [v / piv for v in f[s]]
    bb[s] = bb[s] / piv
    for i in range(m):
        if i != s and f[i][e] != 0:
            k = f[i][e]
            f[i] = [f[i][j] - k * f[s][j] for j in range(len(columnas))]
            bb[i] = bb[i] - k * bb[s]
    nb = basicas[:]
    nb[s] = columnas[e]
    vals = {nombre: Fraction(0) for nombre in columnas}
    for i, nombre in enumerate(nb):
        vals[nombre] = bb[i]
    return vals


_SIG = {"<=": "≤", ">=": "≥", "=": "="}


def _texto_op(destino: int, k, pivote: int) -> str:
    """Texto como 'R0 = R0 + 5·R2' (k es lo que se resta)."""
    if isinstance(k, MNum) and k.m != 0:
        neg = -k
        return f"R{destino} = R{destino} + ({fmt(neg)})·R{pivote}"
    k = k.a if isinstance(k, MNum) else k
    if k < 0:
        return f"R{destino} = R{destino} + {_coef(-k)}R{pivote}"
    return f"R{destino} = R{destino} - {_coef(k)}R{pivote}"


def _coef(k) -> str:
    return "" if k == 1 else f"{_paren(k)}·"


def _paren(k) -> str:
    t = fmt(k)
    return f"({t})" if "/" in t or " " in t else t
