# =============================================================================
# lexer_loreengine.py — Analizador Léxico de LoreEngine
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Estrategia de tokenización:
#   Se usa re.match() avanzando manualmente por posición (no finditer).
#   Esto permite recuperación modo pánico exacta: al detectar un error
#   se registra y se descarta SOLO UN carácter, retomando desde el siguiente.
#
# Orden de alternativas en el patrón maestro:
#   1. Espacios/saltos (ignorar, pero actualizar contadores de línea)
#   2. CADENA válida (cierre con ") — ANTES que CADENA_ABIERTA
#   3. CADENA_ABIERTA (error L01) — solo captura cuando NO hay cierre
#   3.5 COMENTARIO_BLOQUE /* … */ — antes de OP_ARIT (que incluye /)
#   3.6 COMENTARIO_BLOQUE_ABIERTO /* sin cierre (error L06)
#   3.7 COMENTARIO_LINEA // … — hasta fin de línea
#   4. NUM_MAL (error L02): dígitos seguidos de letras
#   5. DECIMAL (error L03): número con punto decimal
#   6. Flecha -> (antes que el operador -)
#   7. Operadores relacionales de dos caracteres (antes que los de uno)
#   8. Demás tokens válidos
#   9. Caracteres con sugerencia (error L04)
#  10. Carácter desconocido sin sugerencia (error L05) — catch-all
# =============================================================================

import re
from dataclasses import dataclass
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Clases de datos
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """Representa un token reconocido por el lexer."""
    tipo: str
    valor: str
    linea: int
    columna: int

    def __repr__(self) -> str:
        return (
            f"Token({self.tipo}, {self.valor!r}, "
            f"línea={self.linea}, col={self.columna})"
        )


@dataclass
class ErrorLexico:
    """Representa un error léxico detectado durante el análisis."""
    codigo: str     # L01 … L06
    mensaje: str
    valor: str
    linea: int
    columna: int

    def __repr__(self) -> str:
        return (
            f"[{self.codigo}] Error léxico en línea {self.linea}, "
            f"columna {self.columna}: {self.mensaje} → {self.valor!r}"
        )


# ---------------------------------------------------------------------------
# Palabras clave del lenguaje (valor → tipo token en mayúsculas)
# ---------------------------------------------------------------------------

PALABRAS_CLAVE = {
    "personaje": "PERSONAJE",
    "escena":    "ESCENA",
    "mostrar":   "MOSTRAR",
    "decision":  "DECISION",
    "si":        "SI",
    "sino":      "SINO",
    "dado":      "DADO",       # función de dado aleatorio: dado(n)
    # Roles de personaje
    "principal": "PRINCIPAL",  # protagonista / agente principal (solo uno)
    "enemigo":   "ENEMIGO",    # NPC hostil / agente adversario
    "aliado":    "ALIADO",     # NPC amigable / agente cooperativo
    "neutral":   "NEUTRAL",    # entidad sin bando / variable de entorno
}

# ---------------------------------------------------------------------------
# Sugerencias para caracteres comúnmente mal usados
# ---------------------------------------------------------------------------

SUGERENCIAS = {
    ";":  "usa llaves { } para delimitar bloques",
    "'":  'LoreEngine usa comillas dobles " para cadenas',
    "[":  "LoreEngine usa llaves { } en lugar de corchetes [ ]",
    "]":  "LoreEngine usa llaves { } en lugar de corchetes [ ]",
    "&":  "usa operadores relacionales (==, !=, >, <, >=, <=)",
    "|":  "usa operadores relacionales (==, !=, >, <, >=, <=)",
    "#":  'LoreEngine no admite # como comentario; usa // o /* */ para comentarios',
    "!":  "para desigualdad usa !=",
    "@":  "carácter no válido en LoreEngine",
    "$":  "carácter no válido en LoreEngine",
    "%":  "carácter no válido en LoreEngine",
    "^":  "carácter no válido en LoreEngine",
    "~":  "carácter no válido en LoreEngine",
    "\\" :"carácter no válido en LoreEngine",
    "`":  'LoreEngine usa comillas dobles " para cadenas',
}

# ---------------------------------------------------------------------------
# Patrón maestro compilado
# ---------------------------------------------------------------------------
# Se usa re.match(fuente, pos) con avance manual para poder controlar
# exactamente cuántos caracteres se consumen en cada iteración.
# El orden de las alternativas es CRÍTICO (primera que haga match gana).

PATRON_MAESTRO = re.compile(
    r"""
    # 1. Espacios y saltos de línea (siempre se ignoran)
    (?P<ESPACIO>\s+)
    |
    # 2. CADENA válida — abierta Y cerrada en la misma línea (ANTES de CADENA_ABIERTA)
    (?P<CADENA>"[^"\n]*")
    |
    # 3. CADENA_ABIERTA — comienza con " pero no cierra antes de \n o fin de fuente
    #    Solo llega aquí si el patrón CADENA no hizo match (no hay " de cierre)
    (?P<CADENA_ABIERTA>"[^"\n]*)
    |
    # 3.5. Comentarios — se descartan sin emitir token
    #      BLOQUE debe ir antes de LINEA y antes de OP_ARIT (que incluye /)
    (?P<COMENTARIO_BLOQUE>/\*[\s\S]*?\*/)
    |
    # Bloque de comentario sin cerrar (L06) — captura hasta el final del fuente
    (?P<COMENTARIO_BLOQUE_ABIERTO>/\*[\s\S]*)
    |
    (?P<COMENTARIO_LINEA>//[^\n]*)
    |
    # 4. NUM_MAL — dígito(s) seguido directamente de letra/guion bajo (ej: 123abc)
    (?P<NUM_MAL>\d+[a-zA-Z_\u00c0-\u024fñÑ][a-zA-Z0-9_\u00c0-\u024fñÑ]*)
    |
    # 5. DECIMAL — número con punto decimal (ej: 3.5); no soportado en LoreEngine
    (?P<DECIMAL>\d+\.\d*)
    |
    # 6. Punto de acceso a atributo de personaje (ANTES que CHAR_SUGERENCIA)
    (?P<PUNTO>\.)
    |
    # 7. Flecha narrativa (ANTES que el operador -)
    (?P<FLECHA>->)
    |
    # 8. Operadores relacionales de dos caracteres (ANTES que los de uno)
    (?P<OP_REL_DOS>==|!=|>=|<=)
    |
    # 9. Operadores relacionales de un carácter
    (?P<OP_REL_UNO>[><])
    |
    # 10. Operadores aritméticos
    (?P<OP_ARIT>[+\-*/])
    |
    # 11. Asignación
    (?P<ASIGNACION>=)
    |
    # 12. Símbolos de agrupación
    (?P<LLAVE_AB>\{)
    |
    (?P<LLAVE_CIE>\})
    |
    (?P<PAREN_AB>\()
    |
    (?P<PAREN_CIE>\))
    |
    # 13. Entero (solo dígitos; DESPUÉS de DECIMAL y NUM_MAL para no pisar errores)
    (?P<ENTERO>\d+)
    |
    # 14. Identificador o palabra clave (admite letras con tilde y ñ/Ñ)
    (?P<IDENTIFICADOR>[a-zA-Z_\u00c0-\u024fñÑ][a-zA-Z0-9_\u00c0-\u024fñÑ]*)
    |
    # 15. Caracteres con sugerencia de corrección (L04) — el punto ya NO está aquí
    (?P<CHAR_SUGERENCIA>[;'\[\]&|#!@$%^~\\`])
    |
    # 16. Cualquier otro carácter desconocido — catch-all (L05)
    (?P<CHAR_DESCONOCIDO>.)
    """,
    re.VERBOSE | re.UNICODE,
)

# ---------------------------------------------------------------------------
# Clase principal: Lexer
# ---------------------------------------------------------------------------

class Lexer:
    """
    Analizador léxico de LoreEngine.

    Uso básico:
        lexer = Lexer(codigo_fuente)
        tokens, errores = lexer.tokenizar()
    """

    def __init__(self, fuente: str):
        self.fuente = fuente
        self.tokens: List[Token] = []
        self.errores: List[ErrorLexico] = []

    # -----------------------------------------------------------------------
    # Método principal de tokenización
    # -----------------------------------------------------------------------

    def tokenizar(self) -> Tuple[List[Token], List[ErrorLexico]]:
        """
        Avanza carácter a carácter sobre el fuente usando re.match en cada
        posición. Esto permite recuperación modo pánico exacta:
        en un error multi-carácter se registra el problema pero se avanza
        SOLO 1 posición, dejando que el resto sea re-analizado.
        """
        fuente = self.fuente
        largo = len(fuente)
        pos = 0
        linea_actual = 1
        inicio_linea = 0   # índice en `fuente` donde comienza la línea actual

        while pos < largo:
            m = PATRON_MAESTRO.match(fuente, pos)
            if not m:
                # No debería ocurrir: CHAR_DESCONOCIDO es el catch-all
                pos += 1
                continue

            tipo  = m.lastgroup
            valor = m.group()
            col   = pos - inicio_linea + 1   # columna 1-indexada

            # ── Espacios: actualizar contadores y no emitir token ────────
            if tipo == "ESPACIO":
                saltos = valor.count("\n")
                if saltos:
                    linea_actual += saltos
                    # La nueva línea empieza justo después del último \n
                    inicio_linea = pos + valor.rfind("\n") + 1
                pos = m.end()   # consumir todo el blanco
                continue

            # ── Errores léxicos ──────────────────────────────────────────

            elif tipo == "CADENA_ABIERTA":
                # L01: comilla abierta sin cierre antes de fin de línea
                self.errores.append(ErrorLexico(
                    codigo="L01",
                    mensaje='Cadena no cerrada; falta la comilla de cierre "',
                    valor=valor,
                    linea=linea_actual,
                    columna=col,
                ))
                # Pánico: descartar solo el carácter de apertura (")
                pos += 1

            elif tipo == "COMENTARIO_LINEA":
                # // … hasta fin de línea: descartar silenciosamente
                pos = m.end()

            elif tipo == "COMENTARIO_BLOQUE":
                # /* … */ completo: contar saltos de línea internos y descartar
                saltos = valor.count("\n")
                if saltos:
                    linea_actual += saltos
                    inicio_linea = pos + valor.rfind("\n") + 1
                pos = m.end()

            elif tipo == "COMENTARIO_BLOQUE_ABIERTO":
                # L06: bloque /* sin cerrar (alcanza el final del fuente)
                resumen = valor[:30] + ("…" if len(valor) > 30 else "")
                self.errores.append(ErrorLexico(
                    codigo="L06",
                    mensaje="Bloque de comentario /* no cerrado; falta el cierre */",
                    valor=resumen,
                    linea=linea_actual,
                    columna=col,
                ))
                pos = m.end()   # consumir el resto del fuente

            elif tipo == "NUM_MAL":
                # L02: número malformado con letras adheridas (ej: 123abc)
                self.errores.append(ErrorLexico(
                    codigo="L02",
                    mensaje=(
                        f"Número malformado '{valor}'; "
                        f"los identificadores no pueden comenzar con dígitos"
                    ),
                    valor=valor,
                    linea=linea_actual,
                    columna=col,
                ))
                # Pánico: descartar solo el primer carácter y reintentar
                pos += 1

            elif tipo == "DECIMAL":
                # L03: número decimal no soportado (ej: 3.5)
                self.errores.append(ErrorLexico(
                    codigo="L03",
                    mensaje=(
                        f"Número decimal '{valor}' no soportado; "
                        f"LoreEngine solo admite enteros"
                    ),
                    valor=valor,
                    linea=linea_actual,
                    columna=col,
                ))
                # Pánico: descartar solo el primer carácter
                pos += 1

            elif tipo == "CHAR_SUGERENCIA":
                # L04: carácter reconocible pero incorrecto, con sugerencia
                sugerencia = SUGERENCIAS.get(valor, "carácter no válido en LoreEngine")
                self.errores.append(ErrorLexico(
                    codigo="L04",
                    mensaje=f"Carácter '{valor}' no válido — sugerencia: {sugerencia}",
                    valor=valor,
                    linea=linea_actual,
                    columna=col,
                ))
                pos += 1   # un solo carácter: pánico natural

            elif tipo == "CHAR_DESCONOCIDO":
                # L05: carácter completamente desconocido
                self.errores.append(ErrorLexico(
                    codigo="L05",
                    mensaje=f"Carácter desconocido '{valor}' (U+{ord(valor):04X})",
                    valor=valor,
                    linea=linea_actual,
                    columna=col,
                ))
                pos += 1   # un solo carácter: pánico natural

            # ── Tokens válidos ───────────────────────────────────────────

            elif tipo == "CADENA":
                self.tokens.append(Token("CADENA", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "FLECHA":
                self.tokens.append(Token("FLECHA", valor, linea_actual, col))
                pos = m.end()

            elif tipo in ("OP_REL_DOS", "OP_REL_UNO"):
                self.tokens.append(Token("OP_REL", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "OP_ARIT":
                self.tokens.append(Token("OP_ARIT", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "ASIGNACION":
                self.tokens.append(Token("ASIGNACION", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "LLAVE_AB":
                self.tokens.append(Token("LLAVE_AB", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "LLAVE_CIE":
                self.tokens.append(Token("LLAVE_CIE", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "PAREN_AB":
                self.tokens.append(Token("PAREN_AB", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "PUNTO":
                self.tokens.append(Token("PUNTO", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "PAREN_CIE":
                self.tokens.append(Token("PAREN_CIE", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "ENTERO":
                self.tokens.append(Token("ENTERO", valor, linea_actual, col))
                pos = m.end()

            elif tipo == "IDENTIFICADOR":
                # Determinar si es palabra clave (tipo en mayúsculas) o identificador
                tipo_token = PALABRAS_CLAVE.get(valor, "IDENTIFICADOR")
                self.tokens.append(Token(tipo_token, valor, linea_actual, col))
                pos = m.end()

            else:
                # Grupo no manejado: avanzar para no quedar en bucle infinito
                pos += 1

        # Token centinela de fin de archivo (columna 1 por consistencia)
        ultima_linea = linea_actual
        self.tokens.append(Token("EOF", "", ultima_linea, 1))

        return self.tokens, self.errores
        # Nota: no se necesita segunda pasada para EOF con cadena sin cerrar.
        # El patrón CADENA_ABIERTA ("[ ^"\n]*) en el bucle principal captura
        # todos los casos: cadena con \n antes del cierre Y cadena al final
        # del archivo sin \n. Una segunda pasada solo generaría falsos positivos
        # cuando hay múltiples cadenas y una intermedia está sin cerrar.

    # -----------------------------------------------------------------------
    # Métodos de visualización
    # -----------------------------------------------------------------------

    def imprimir_tabla(self) -> None:
        """Imprime los tokens en formato de tabla con columnas alineadas."""
        if not self.tokens:
            print("  (sin tokens)\n")
            return

        ancho_tipo  = max(len(t.tipo)         for t in self.tokens)
        ancho_valor = max(len(repr(t.valor))  for t in self.tokens)

        sep = "  " + "─" * (ancho_tipo + ancho_valor + 20)
        enc = (
            f"  {'TIPO':<{ancho_tipo}}  "
            f"{'VALOR':<{ancho_valor}}  "
            f"{'LÍNEA':>6}  {'COL':>4}"
        )
        print(sep)
        print(enc)
        print(sep)
        for tok in self.tokens:
            print(
                f"  {tok.tipo:<{ancho_tipo}}  "
                f"{repr(tok.valor):<{ancho_valor}}  "
                f"{tok.linea:>6}  "
                f"{tok.columna:>4}"
            )
        print(sep)
        print(f"  Total: {len(self.tokens)} token(s)\n")

    def imprimir_errores(self) -> None:
        """Imprime los errores léxicos con formato."""
        if not self.errores:
            print("  ✓ Sin errores léxicos.\n")
            return
        print(f"  Se encontraron {len(self.errores)} error(es) léxico(s):\n")
        for err in self.errores:
            print(f"  {err}")
        print()


# ---------------------------------------------------------------------------
# Función auxiliar para uso externo (parser, semántico, etc.)
# ---------------------------------------------------------------------------

def analizar(fuente: str) -> Tuple[List[Token], List[ErrorLexico]]:
    """
    Conveniencia: tokeniza el fuente y retorna (tokens, errores).
    Equivalente a Lexer(fuente).tokenizar().
    """
    return Lexer(fuente).tokenizar()


# ---------------------------------------------------------------------------
# Bloque __main__: pruebas autocontenidas del lexer
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Forzar UTF-8 en la salida estándar (necesario en Windows con cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Prueba 1: código LoreEngine completamente válido ────────────────
    FUENTE_VALIDA = """\
personaje heroe {
    vida   = 100
    oro    = 50
    fuerza = 20
}

escena inicio {
    mostrar "Estás en un bosque oscuro."
    decision {
        "Explorar" -> bosque
        "Salir"    -> final
    }
}

escena bosque {
    si vida > 0 {
        mostrar "Sigues con vida."
    } sino {
        mostrar "Has muerto."
    }
}

escena combate {
    vida = vida - 10
    oro  = oro + (fuerza * 2)
}
"""

    print("=" * 62)
    print(" PRUEBA 1 — Código LoreEngine válido")
    print("=" * 62)
    lex1 = Lexer(FUENTE_VALIDA)
    toks1, errs1 = lex1.tokenizar()
    lex1.imprimir_tabla()
    lex1.imprimir_errores()

    # ── Prueba 2: errores léxicos variados ──────────────────────────────
    FUENTE_ERRORES = """\
personaje roto {
    puntos = 3.5
    codigo = 123abc
    texto  = "cadena sin cerrar
    turno  = 10;
    lista  = [100]
}
"""

    print("=" * 62)
    print(" PRUEBA 2 — Código con errores léxicos")
    print("=" * 62)
    print("Fuente:\n")
    for i, linea in enumerate(FUENTE_ERRORES.splitlines(), 1):
        print(f"  {i:3}: {linea}")
    print()
    lex2 = Lexer(FUENTE_ERRORES)
    toks2, errs2 = lex2.tokenizar()
    lex2.imprimir_tabla()
    lex2.imprimir_errores()

    # ── Prueba 3: recuperación modo pánico (123abc → ENTERO + IDENTIFICADOR)
    FUENTE_PANICO = "vida = 123abc + 5"

    print("=" * 62)
    print(" PRUEBA 3 — Recuperación modo pánico (un carácter a la vez)")
    print("=" * 62)
    print(f"Fuente: {FUENTE_PANICO!r}\n")
    lex3 = Lexer(FUENTE_PANICO)
    toks3, errs3 = lex3.tokenizar()
    lex3.imprimir_tabla()
    lex3.imprimir_errores()

    # ── Prueba 4: EOF con cadena sin cerrar ─────────────────────────────
    FUENTE_EOF = 'escena fin {\n    mostrar "fin inesperado\n}'

    print("=" * 62)
    print(" PRUEBA 4 — EOF con cadena sin cerrar")
    print("=" * 62)
    print("Fuente:\n")
    for i, linea in enumerate(FUENTE_EOF.splitlines(), 1):
        print(f"  {i:3}: {linea}")
    print()
    lex4 = Lexer(FUENTE_EOF)
    toks4, errs4 = lex4.tokenizar()
    lex4.imprimir_tabla()
    lex4.imprimir_errores()

    # ── Prueba 5: cadena válida vs cadena abierta (no falsos positivos) ─
    FUENTE_CADENAS = '''\
mostrar "esto es valido"
mostrar "esto no cierra
mostrar "esto tambien es valido"
'''

    print("=" * 62)
    print(" PRUEBA 5 — Cadena válida vs cadena sin cerrar")
    print("=" * 62)
    print("Fuente:\n")
    for i, linea in enumerate(FUENTE_CADENAS.splitlines(), 1):
        print(f"  {i:3}: {linea}")
    print()
    lex5 = Lexer(FUENTE_CADENAS)
    toks5, errs5 = lex5.tokenizar()
    lex5.imprimir_tabla()
    lex5.imprimir_errores()
