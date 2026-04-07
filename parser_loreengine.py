# =============================================================================
# parser_loreengine.py — Analizador Sintáctico de LoreEngine  (v2)
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Mejoras implementadas respecto a v1:
#
#   [M1] _consumir(): avanza siempre como último recurso → progreso garantizado
#   [M2] NodoErrorExpr en lugar de NodoEntero(0) como centinela de error
#   [M3] Validación temprana de referencias de decision tras el parse
#   [M4] _sincronizar_bloque() vs _sincronizar_global() (granularidad doble)
#   [M5] ErrorSintactico.fatal: bool — distinción recuperable vs fatal
#   [M6] _ultimo_error_pos suprime errores en cascada de factor→termino→expresion
#   [M7] Tabla de precedencia explícita documentada
#   [M8] _parsear_bloque_sentencias() abstracto (elimina repetición en 5 sitios)
#   [M9] Modo debug con trazador de reglas (_trazar/_salir_regla)
#  [M10] advertencias: List[str] — AST parcial notificado, no silencioso
#
# Recuperación de errores — tres estrategias:
#   1. Sincronización por ancla de bloque (LLAVE_CIE) o global (PERSONAJE/ESCENA)
#   2. Inserción implícita de '}': no consumir cuando falta cierre
#   3. Eliminación de token inesperado cuando el siguiente sí encaja
#
# Precedencia aritmética (mayor número = mayor precedencia):
#   Nivel 1 — expresion  : + -   (izquierda-asociativo)
#   Nivel 2 — termino    : * /   (izquierda-asociativo)
#   Nivel 3 — factor     : entero, identificador, (expr)
# =============================================================================

import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Optional, Set

from lexer_loreengine import Token, analizar
from ast_nodes import (
    NodoAST, NodoPrograma, NodoPersonaje, NodoAtributo,
    NodoEscena, NodoMostrar, NodoAsignacion, NodoAsignAtrib,
    NodoDecision, NodoOpcion, NodoSi, NodoCondicion, NodoBinario,
    NodoEntero, NodoIdentificador, NodoAtribPersonaje, NodoDado,
    NodoErrorExpr,
)

# ---------------------------------------------------------------------------
# Clase de error sintáctico  [M5]
# ---------------------------------------------------------------------------

@dataclass
class ErrorSintactico:
    """
    Representa un error detectado durante el análisis sintáctico.

    fatal=True  → el parser no puede recuperarse en el contexto actual;
                  se abandona la declaración completa.
    fatal=False → el parser puede recuperarse e intentar continuar.
    """
    codigo:  str
    mensaje: str
    linea:   int
    columna: int
    fatal:   bool = False   # [M5]

    _NOMBRES = {
        "S01": "esperado",
        "S02": "inesperado",
        "S03": "falta_cuerpo",
        "S04": "falta_opcion",
        "S05": "expr_invalida",
    }

    def __repr__(self) -> str:
        nombre   = self._NOMBRES.get(self.codigo, self.codigo)
        severidad = "[FATAL]" if self.fatal else ""
        return (
            f"[{self.codigo}/{nombre}]{severidad} Error sintáctico "
            f"en línea {self.linea}, columna {self.columna}: {self.mensaje}"
        )


# ---------------------------------------------------------------------------
# Tokens ancla para sincronización
# ---------------------------------------------------------------------------

_ANCLAS_GLOBALES  = frozenset({"PERSONAJE", "ESCENA", "EOF"})
_INICIO_SENTENCIA = frozenset({"MOSTRAR", "DECISION", "SI", "IDENTIFICADOR"})

# ---------------------------------------------------------------------------
# Clase principal: Parser
# ---------------------------------------------------------------------------

class Parser:
    """
    Analizador sintáctico recursivo descendente de LoreEngine.

    Uso básico:
        parser = Parser(tokens)
        ast, errores, advertencias = parser.parsear()

    Modo debug (traza reglas activas):
        parser = Parser(tokens, debug=True)
    """

    def __init__(self, tokens: List[Token], debug: bool = False):
        self._tokens   = tokens
        self._pos      = 0
        self._debug    = debug
        self._prof     = 0             # profundidad del trazador  [M9]
        self._ultimo_error_pos = -1    # posición del último error, anti-cascada [M6]
        self.errores:      List[ErrorSintactico] = []
        self.advertencias: List[str]             = []  # [M10]

    # -----------------------------------------------------------------------
    # Acceso al flujo de tokens
    # -----------------------------------------------------------------------

    def _actual(self) -> Token:
        """Retorna el token actual sin consumirlo."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return Token("EOF", "", 0, 0)

    def _siguiente(self) -> Token:
        """Lookahead de 1: retorna el token después del actual."""
        sig = self._pos + 1
        if sig < len(self._tokens):
            return self._tokens[sig]
        return Token("EOF", "", 0, 0)

    def _avanzar(self) -> Token:
        """Consume y retorna el token actual."""
        tok = self._actual()
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def _es_tipo(self, *tipos: str) -> bool:
        return self._actual().tipo in tipos

    # -----------------------------------------------------------------------
    # [M1] _consumir(): progreso garantizado en todos los casos
    # -----------------------------------------------------------------------

    def _consumir(self, tipo: str, codigo_err: str,
                  mensaje: str, fatal: bool = False) -> Optional[Token]:
        """
        Consume el token actual si coincide con `tipo`.

        Estrategias de recuperación (en orden):
          1. Match exacto → consumir y retornar.
          2. Inserción implícita de '}' → no avanzar, retornar None.
          3. Eliminación: si el siguiente es el esperado, descartar el actual.
          4. Último recurso: registrar error y avanzar UN carácter (SIEMPRE
             garantiza progreso para evitar bucles infinitos). [M1]
        """
        tok = self._actual()

        # Caso feliz
        if tok.tipo == tipo:
            return self._avanzar()

        # Estrategia 2 — inserción implícita de '}'
        if tipo == "LLAVE_CIE" and tok.tipo in (_ANCLAS_GLOBALES | _INICIO_SENTENCIA):
            self._registrar_error(codigo_err, mensaje, tok, fatal)
            return None   # no avanzamos; el llamador lo reintentará

        # Estrategia 3 — eliminación del token inesperado
        sig = self._siguiente()
        if sig.tipo == tipo:
            self._registrar_error(
                "S02",
                f"Token inesperado {tok.valor!r} ({tok.tipo}); se descarta",
                tok, fatal=False,
            )
            self._avanzar()          # descartar el problemático
            return self._avanzar()   # consumir el esperado

        # Estrategia 4 — último recurso: avanzar para garantizar progreso [M1]
        self._registrar_error(codigo_err, mensaje, tok, fatal)
        if tok.tipo != "EOF":
            self._avanzar()           # ← avance que faltaba en v1
        return None

    # -----------------------------------------------------------------------
    # [M4] Sincronización con granularidad doble
    # -----------------------------------------------------------------------

    def _sincronizar_bloque(self) -> None:
        """
        Sincronización dentro de un bloque: descarta tokens hasta encontrar
        LLAVE_CIE, el inicio de una nueva declaración o EOF.
        Usada cuando el error ocurre dentro de { ... }.
        """
        while not self._es_tipo("LLAVE_CIE", "PERSONAJE", "ESCENA", "EOF"):
            self._avanzar()

    def _sincronizar_global(self) -> None:
        """
        Sincronización global: descarta tokens hasta encontrar PERSONAJE,
        ESCENA o EOF. Usada cuando el error ocurre fuera de cualquier bloque.
        """
        while not self._es_tipo(*_ANCLAS_GLOBALES):
            self._avanzar()

    # -----------------------------------------------------------------------
    # Registro de errores y advertencias  [M5, M10]
    # -----------------------------------------------------------------------

    def _registrar_error(self, codigo: str, mensaje: str,
                         tok: Token, fatal: bool = False) -> None:
        self.errores.append(ErrorSintactico(
            codigo=codigo, mensaje=mensaje,
            linea=tok.linea, columna=tok.columna,
            fatal=fatal,
        ))

    def _advertir(self, mensaje: str) -> None:
        """Registra una advertencia sobre un AST parcial o nodo incompleto."""
        self.advertencias.append(f"[ADVERTENCIA] {mensaje}")

    # -----------------------------------------------------------------------
    # [M6] Supresión de errores en cascada
    # -----------------------------------------------------------------------

    def _es_cascada(self) -> bool:
        """
        Retorna True si ya se registró un error en la posición actual.
        Evita que _parse_termino/_parse_expresion generen errores adicionales
        cuando _parse_factor() ya reportó el problema.
        """
        return self._pos == self._ultimo_error_pos

    def _marcar_error_pos(self) -> None:
        """Marca la posición actual como fuente de error para anti-cascada."""
        self._ultimo_error_pos = self._pos

    # -----------------------------------------------------------------------
    # [M9] Trazador de reglas (debug)
    # -----------------------------------------------------------------------

    @contextmanager
    def _regla(self, nombre: str):
        """Context manager que traza la entrada/salida de cada regla."""
        if self._debug:
            tok = self._actual()
            ind = "  " * self._prof
            print(
                f"{ind}→ {nombre}  "
                f"[{tok.tipo}: {tok.valor!r} L{tok.linea}]"
            )
        self._prof += 1
        try:
            yield
        finally:
            self._prof -= 1
            if self._debug:
                tok = self._actual()
                ind = "  " * self._prof
                print(f"{ind}← {nombre}  [{tok.tipo}: {tok.valor!r}]")

    # -----------------------------------------------------------------------
    # [M8] Abstracción de parsing de bloques de sentencias
    # -----------------------------------------------------------------------

    def _parsear_bloque_sentencias(self, contexto: str) -> List[NodoAST]:
        """
        Parsea un bloque '{ sentencia* }' y retorna la lista de sentencias.
        Concentra la lógica repetida en _parse_escena, _parse_si (x2),
        y _parse_si sin rama sino. Siempre deja el token de cierre consumido.

        contexto: nombre descriptivo para mensajes de error (ej: 'escena inicio')
        """
        with self._regla(f"bloque_sentencias({contexto})"):
            if not self._consumir("LLAVE_AB", "S01",
                                  f"Se esperaba '{{' para abrir '{contexto}'"):
                self._sincronizar_bloque()
                return []

            sentencias = []
            while not self._es_tipo("LLAVE_CIE", "EOF"):
                if self._es_tipo("PERSONAJE", "ESCENA"):
                    # Nueva declaración sin cerrar el bloque anterior
                    self._advertir(
                        f"Bloque '{contexto}' sin '}}' de cierre; "
                        f"se encontró {self._actual().tipo!r} en línea "
                        f"{self._actual().linea}"
                    )
                    break
                sent = self._parse_sentencia()
                if sent is not None:
                    sentencias.append(sent)

            self._consumir("LLAVE_CIE", "S01",
                           f"Se esperaba '}}' para cerrar '{contexto}'")
            return sentencias

    # -----------------------------------------------------------------------
    # Punto de entrada
    # -----------------------------------------------------------------------

    def parsear(self):
        """
        Analiza los tokens y retorna (NodoPrograma, errores, advertencias).
        Tras el parse se ejecuta la validación temprana de referencias. [M3]
        """
        ast = self._parse_programa()
        self._validar_referencias(ast)          # [M3]
        return ast, self.errores, self.advertencias

    # -----------------------------------------------------------------------
    # Reglas de la gramática
    # -----------------------------------------------------------------------

    # programa ::= declaracion+
    def _parse_programa(self) -> NodoPrograma:
        with self._regla("programa"):
            linea = self._actual().linea
            declaraciones = []

            while not self._es_tipo("EOF"):
                decl = self._parse_declaracion()
                if decl is not None:
                    declaraciones.append(decl)

            return NodoPrograma(declaraciones, linea)

    # ───────────────────────────────────────────────────────────────────────
    # declaracion ::= def_personaje | def_escena
    def _parse_declaracion(self) -> Optional[NodoAST]:
        with self._regla("declaracion"):
            tok = self._actual()

            if tok.tipo == "PERSONAJE":
                return self._parse_personaje()
            elif tok.tipo == "ESCENA":
                return self._parse_escena()
            else:
                self._registrar_error(
                    "S02",
                    f"Se esperaba 'personaje' o 'escena', "
                    f"se encontró {tok.valor!r} ({tok.tipo})",
                    tok, fatal=False,
                )
                self._avanzar()
                self._sincronizar_global()
                return None

    # ───────────────────────────────────────────────────────────────────────
    # def_personaje ::= 'personaje' rol? IDENTIFICADOR '{' atributo* '}'
    # rol           ::= 'principal' | 'enemigo' | 'aliado' | 'neutral'
    def _parse_personaje(self) -> Optional[NodoPersonaje]:
        with self._regla("def_personaje"):
            tok_kw = self._avanzar()
            linea  = tok_kw.linea

            # Rol opcional entre 'personaje' y el nombre
            _ROLES = {"PRINCIPAL", "ENEMIGO", "ALIADO", "NEUTRAL"}
            if self._actual().tipo in _ROLES:
                rol = self._avanzar().valor   # consume el token de rol
            else:
                rol = "neutral"               # valor por defecto

            tok_nombre = self._consumir(
                "IDENTIFICADOR", "S01",
                "Se esperaba el nombre del personaje", fatal=False,
            )
            nombre = tok_nombre.valor if tok_nombre else "__sin_nombre__"

            if not self._consumir("LLAVE_AB", "S01",
                                  f"Se esperaba '{{' después de '{nombre}'",
                                  fatal=True):
                self._sincronizar_global()
                return NodoPersonaje(nombre, [], linea, rol=rol)

            atributos = []
            while not self._es_tipo("LLAVE_CIE", "EOF"):
                if self._es_tipo("PERSONAJE", "ESCENA"):
                    self._advertir(
                        f"Personaje '{nombre}' sin '}}'; "
                        f"se encontró {self._actual().tipo!r} en línea "
                        f"{self._actual().linea}"
                    )
                    break
                attr = self._parse_atributo()
                if attr is not None:
                    atributos.append(attr)

            self._consumir("LLAVE_CIE", "S01",
                           f"Se esperaba '}}' para cerrar el personaje '{nombre}'")

            return NodoPersonaje(nombre, atributos, linea, rol=rol)

    # ───────────────────────────────────────────────────────────────────────
    # atributo ::= IDENTIFICADOR '=' expresion
    def _parse_atributo(self) -> Optional[NodoAtributo]:
        with self._regla("atributo"):
            tok = self._actual()

            if not self._es_tipo("IDENTIFICADOR"):
                self._registrar_error(
                    "S02",
                    f"Se esperaba nombre de atributo, "
                    f"se encontró {tok.valor!r} ({tok.tipo})",
                    tok,
                )
                self._avanzar()
                return None

            tok_nombre = self._avanzar()
            linea      = tok_nombre.linea

            if not self._consumir("ASIGNACION", "S01",
                                  f"Se esperaba '=' después de '{tok_nombre.valor}'"):
                return None

            expr = self._parse_expresion()
            # [M2] Nunca retornar None desde atributo; usar NodoErrorExpr
            if expr is None:
                self._advertir(
                    f"Atributo '{tok_nombre.valor}' línea {linea}: "
                    f"expresión inválida; se inserta NodoErrorExpr"
                )
                expr = NodoErrorExpr(linea)

            return NodoAtributo(tok_nombre.valor, expr, linea)

    # ───────────────────────────────────────────────────────────────────────
    # def_escena ::= 'escena' IDENTIFICADOR '{' sentencia* '}'  [M8]
    def _parse_escena(self) -> Optional[NodoEscena]:
        with self._regla("def_escena"):
            tok_kw = self._avanzar()
            linea  = tok_kw.linea

            tok_nombre = self._consumir(
                "IDENTIFICADOR", "S01",
                "Se esperaba el nombre de la escena", fatal=False,
            )
            nombre = tok_nombre.valor if tok_nombre else "__sin_nombre__"

            sentencias = self._parsear_bloque_sentencias(f"escena '{nombre}'")
            return NodoEscena(nombre, sentencias, linea)

    # ───────────────────────────────────────────────────────────────────────
    # sentencia ::= sent_mostrar | sent_decision | sent_si
    #             | sent_asignacion | sent_asignacion_atrib
    def _parse_sentencia(self) -> Optional[NodoAST]:
        with self._regla("sentencia"):
            tok = self._actual()

            if tok.tipo == "MOSTRAR":
                return self._parse_mostrar()
            elif tok.tipo == "DECISION":
                return self._parse_decision()
            elif tok.tipo == "SI":
                return self._parse_si()
            elif tok.tipo == "IDENTIFICADOR":
                # Lookahead: si el siguiente token es PUNTO → asignación a atributo NPC
                if self._siguiente().tipo == "PUNTO":
                    return self._parse_asignacion_atrib()
                else:
                    return self._parse_asignacion()
            else:
                self._registrar_error(
                    "S02",
                    f"Sentencia inválida: {tok.valor!r} ({tok.tipo})",
                    tok,
                )
                self._avanzar()   # [M1] avance garantizado
                return None

    # ───────────────────────────────────────────────────────────────────────
    # sent_mostrar ::= 'mostrar' CADENA
    def _parse_mostrar(self) -> Optional[NodoMostrar]:
        with self._regla("sent_mostrar"):
            tok_kw = self._avanzar()
            linea  = tok_kw.linea

            tok_cadena = self._consumir(
                "CADENA", "S01",
                "Se esperaba una cadena después de 'mostrar'",
            )
            if tok_cadena is None:
                # [M10] Nodo parcial advertido
                self._advertir(
                    f"'mostrar' en línea {linea} sin cadena; se omite la sentencia"
                )
                return None

            return NodoMostrar(tok_cadena.valor, linea)

    # ───────────────────────────────────────────────────────────────────────
    # sent_asignacion ::= IDENTIFICADOR '=' expresion
    def _parse_asignacion(self) -> Optional[NodoAsignacion]:
        with self._regla("sent_asignacion"):
            tok_nombre = self._avanzar()
            linea      = tok_nombre.linea
            nombre     = tok_nombre.valor

            if not self._consumir("ASIGNACION", "S01",
                                  f"Se esperaba '=' después de '{nombre}'"):
                return None

            expr = self._parse_expresion()
            if expr is None:
                # [M2] usar centinela en lugar de propagar None
                self._advertir(
                    f"Asignación '{nombre}' línea {linea}: "
                    f"expresión inválida; se inserta NodoErrorExpr"
                )
                expr = NodoErrorExpr(linea)

            return NodoAsignacion(nombre, expr, linea)

    # ───────────────────────────────────────────────────────────────────────
    # sent_asignacion_atrib ::= IDENTIFICADOR '.' IDENTIFICADOR '=' expresion
    def _parse_asignacion_atrib(self) -> Optional[NodoAsignAtrib]:
        with self._regla("sent_asignacion_atrib"):
            tok_pers = self._avanzar()          # consume personaje
            linea    = tok_pers.linea
            personaje = tok_pers.valor

            self._consumir("PUNTO", "S01",
                           f"Se esperaba '.' después de '{personaje}'")

            tok_attr = self._consumir(
                "IDENTIFICADOR", "S01",
                f"Se esperaba nombre de atributo después de '{personaje}.'",
            )
            atributo = tok_attr.valor if tok_attr else "__sin_nombre__"

            if not self._consumir(
                "ASIGNACION", "S01",
                f"Se esperaba '=' en asignación a '{personaje}.{atributo}'",
            ):
                return None

            expr = self._parse_expresion()
            if expr is None:
                self._advertir(
                    f"Asignación '{personaje}.{atributo}' línea {linea}: "
                    f"expresión inválida; se inserta NodoErrorExpr"
                )
                expr = NodoErrorExpr(linea)

            return NodoAsignAtrib(personaje, atributo, expr, linea)

    # ───────────────────────────────────────────────────────────────────────
    # sent_decision ::= 'decision' '{' opcion+ '}'
    def _parse_decision(self) -> Optional[NodoDecision]:
        with self._regla("sent_decision"):
            tok_kw = self._avanzar()
            linea  = tok_kw.linea

            if not self._consumir("LLAVE_AB", "S01",
                                  "Se esperaba '{' después de 'decision'"):
                self._sincronizar_bloque()
                return NodoDecision([], linea)

            opciones = []
            while not self._es_tipo("LLAVE_CIE", "EOF"):
                if self._es_tipo("PERSONAJE", "ESCENA"):
                    break
                op = self._parse_opcion()
                if op is not None:
                    opciones.append(op)

            if not opciones:
                self._registrar_error(
                    "S04",
                    "El bloque 'decision' no tiene ninguna opción válida",
                    tok_kw,
                )

            self._consumir("LLAVE_CIE", "S01",
                           "Se esperaba '}' para cerrar 'decision'")
            return NodoDecision(opciones, linea)

    # ───────────────────────────────────────────────────────────────────────
    # opcion ::= CADENA '->' IDENTIFICADOR
    def _parse_opcion(self) -> Optional[NodoOpcion]:
        with self._regla("opcion"):
            tok = self._actual()

            if not self._es_tipo("CADENA"):
                self._registrar_error(
                    "S02",
                    f"Se esperaba cadena para la opción, "
                    f"se encontró {tok.valor!r} ({tok.tipo})",
                    tok,
                )
                self._avanzar()
                return None

            tok_etiq = self._avanzar()
            linea    = tok_etiq.linea

            if not self._consumir("FLECHA", "S01",
                                  f"Se esperaba '->' después de {tok_etiq.valor!r}"):
                return None

            tok_dest = self._consumir(
                "IDENTIFICADOR", "S01",
                "Se esperaba el nombre de la escena destino después de '->'",
            )
            if tok_dest is None:
                return None

            return NodoOpcion(tok_etiq.valor, tok_dest.valor, linea)

    # ───────────────────────────────────────────────────────────────────────
    # sent_si ::= 'si' condicion '{' sentencia* '}' ('sino' '{' sentencia* '}')?
    # [M2] [M8]
    def _parse_si(self) -> Optional[NodoSi]:
        with self._regla("sent_si"):
            tok_kw = self._avanzar()
            linea  = tok_kw.linea

            cond = self._parse_condicion()
            # [M2] Si la condición falló, usar NodoErrorExpr en lugar de NodoEntero(0)
            if cond is None:
                self._advertir(
                    f"'si' en línea {linea}: condición inválida; "
                    f"se inserta NodoErrorExpr"
                )
                cond = NodoErrorExpr(linea)
                self._sincronizar_bloque()   # [M4] sync granular hacia '{'

            cuerpo_si = self._parsear_bloque_sentencias(f"si (línea {linea})")  # [M8]

            cuerpo_sino: List[NodoAST] = []
            if self._es_tipo("SINO"):
                self._avanzar()
                cuerpo_sino = self._parsear_bloque_sentencias(
                    f"sino (línea {linea})"
                )  # [M8]

            return NodoSi(cond, cuerpo_si, cuerpo_sino, linea)

    # ───────────────────────────────────────────────────────────────────────
    # condicion ::= expresion op_relacional expresion
    def _parse_condicion(self) -> Optional[NodoCondicion]:
        with self._regla("condicion"):
            linea = self._actual().linea
            izq   = self._parse_expresion()

            if izq is None:
                return None

            if not self._es_tipo("OP_REL"):
                self._registrar_error(
                    "S01",
                    f"Se esperaba operador relacional (==, !=, >, <, >=, <=), "
                    f"se encontró {self._actual().valor!r}",
                    self._actual(),
                )
                return None

            op  = self._avanzar().valor
            der = self._parse_expresion()

            if der is None:
                self._advertir(
                    f"Condición línea {linea}: falta expresión derecha; "
                    f"se inserta NodoErrorExpr"
                )
                der = NodoErrorExpr(linea)

            return NodoCondicion(izq, op, der, linea)

    # ───────────────────────────────────────────────────────────────────────
    # Expresiones — tabla de precedencia explícita  [M7]
    #
    #  Nivel | Regla      | Operadores | Asociatividad
    #  ──────┼────────────┼────────────┼──────────────
    #    1   | expresion  | + -        | izquierda
    #    2   | termino    | * /        | izquierda
    #    3   | factor     | (ninguno)  | —
    #
    # Para agregar nuevos operadores (ej: '%' en nivel 2):
    #   → añadir el símbolo en el while de _parse_termino()
    # Para agregar un nivel nuevo (ej: '**' de mayor precedencia):
    #   → insertar _parse_potencia() entre termino y factor
    # ───────────────────────────────────────────────────────────────────────

    # expresion ::= termino (('+' | '-') termino)*
    def _parse_expresion(self) -> Optional[NodoAST]:
        with self._regla("expresion"):
            linea = self._actual().linea
            nodo  = self._parse_termino()

            if nodo is None:
                return None

            while self._es_tipo("OP_ARIT") and self._actual().valor in ("+", "-"):
                op  = self._avanzar().valor
                der = self._parse_termino()
                if der is None:
                    # [M6] suprimir cascada: termino ya reportó su error
                    if not self._es_cascada():
                        self._registrar_error(
                            "S05",
                            f"Se esperaba término después de '{op}'",
                            self._actual(),
                        )
                    break
                nodo = NodoBinario(nodo, op, der, linea)

            return nodo

    # termino ::= factor (('*' | '/') factor)*
    def _parse_termino(self) -> Optional[NodoAST]:
        with self._regla("termino"):
            linea = self._actual().linea
            nodo  = self._parse_factor()

            if nodo is None:
                return None

            while self._es_tipo("OP_ARIT") and self._actual().valor in ("*", "/"):
                op  = self._avanzar().valor
                der = self._parse_factor()
                if der is None:
                    # [M6] suprimir cascada
                    if not self._es_cascada():
                        self._registrar_error(
                            "S05",
                            f"Se esperaba factor después de '{op}'",
                            self._actual(),
                        )
                    break
                nodo = NodoBinario(nodo, op, der, linea)

            return nodo

    # factor ::= ENTERO | IDENTIFICADOR | IDENTIFICADOR '.' IDENTIFICADOR
    #          | DADO '(' expresion ')' | '(' expresion ')'
    def _parse_factor(self) -> Optional[NodoAST]:
        with self._regla("factor"):
            tok = self._actual()

            if tok.tipo == "ENTERO":
                self._avanzar()
                return NodoEntero(int(tok.valor), tok.linea)

            elif tok.tipo == "DADO":
                # dado(n) → NodoDado
                self._avanzar()
                self._consumir("PAREN_AB", "S01",
                               "Se esperaba '(' después de 'dado'")
                arg = self._parse_expresion()
                if arg is None:
                    self._advertir(
                        f"dado(): expresión inválida en línea {tok.linea}; "
                        f"se inserta NodoErrorExpr"
                    )
                    arg = NodoErrorExpr(tok.linea)
                self._consumir("PAREN_CIE", "S01",
                               "Se esperaba ')' para cerrar 'dado(...)'")
                return NodoDado(arg, tok.linea)

            elif tok.tipo == "IDENTIFICADOR":
                # Lookahead: si sigue PUNTO → personaje.atributo
                if self._siguiente().tipo == "PUNTO":
                    tok_pers = self._avanzar()      # consume personaje
                    self._avanzar()                 # consume PUNTO
                    tok_attr = self._consumir(
                        "IDENTIFICADOR", "S01",
                        f"Se esperaba atributo después de '{tok_pers.valor}.'",
                    )
                    atributo = tok_attr.valor if tok_attr else "__sin_nombre__"
                    return NodoAtribPersonaje(tok_pers.valor, atributo,
                                             tok_pers.linea)
                else:
                    self._avanzar()
                    return NodoIdentificador(tok.valor, tok.linea)

            elif tok.tipo == "PAREN_AB":
                self._avanzar()
                expr = self._parse_expresion()
                self._consumir("PAREN_CIE", "S01",
                               "Se esperaba ')' para cerrar la expresión")
                return expr

            else:
                # [M6] Marcar posición para suprimir cascada hacia arriba
                self._marcar_error_pos()
                self._registrar_error(
                    "S05",
                    f"Expresión inválida: {tok.valor!r} ({tok.tipo}); "
                    f"se esperaba número, variable, 'dado(...)' o '('",
                    tok,
                )
                # No avanzar aquí: el llamador decidirá el contexto de recuperación
                return None

    # -----------------------------------------------------------------------
    # [M3] Validación temprana de referencias de decision
    # -----------------------------------------------------------------------

    def _validar_referencias(self, programa: NodoPrograma) -> None:
        """
        Segunda pasada ligera DESPUÉS del parse principal:
        - Recolecta todos los nombres de escenas declaradas.
        - Verifica que cada destino de opción apunte a una escena existente.
        Estos son errores semánticos leves; se reportan como advertencias
        para no duplicar el trabajo del AnalizadorSemantico (semantico_loreengine.py).
        """
        escenas_declaradas: Set[str] = set()

        # Pasada 1: recolectar nombres de escenas
        for decl in programa.declaraciones:
            if isinstance(decl, NodoEscena):
                escenas_declaradas.add(decl.nombre)

        # Pasada 2: verificar destinos de decision
        for decl in programa.declaraciones:
            if isinstance(decl, NodoEscena):
                self._verificar_referencias_escena(
                    decl.sentencias, escenas_declaradas, decl.nombre
                )

    def _verificar_referencias_escena(self,
                                       sentencias: List[NodoAST],
                                       escenas: Set[str],
                                       ctx: str) -> None:
        """Recorre sentencias verificando destinos de decisiones."""
        for sent in sentencias:
            if isinstance(sent, NodoDecision):
                for opcion in sent.opciones:
                    if opcion.destino not in escenas:
                        self._advertir(
                            f"Escena '{ctx}', decisión línea {sent.linea}: "
                            f"destino '{opcion.destino}' no está declarado "
                            f"(verificación temprana; semántico lo confirmará)"
                        )
            elif isinstance(sent, NodoSi):
                self._verificar_referencias_escena(sent.cuerpo_si,   escenas, ctx)
                self._verificar_referencias_escena(sent.cuerpo_sino, escenas, ctx)


# ---------------------------------------------------------------------------
# Nodo auxiliar para visualización del bloque sino
# ---------------------------------------------------------------------------

class _BannerSino(NodoAST):
    """Nodo de visualización para la rama sino en imprimir_ast()."""
    def __init__(self, sentencias: list):
        self.sentencias = sentencias

    def __repr__(self) -> str:
        return f"_BannerSino([{len(self.sentencias)} sent.])"


# ---------------------------------------------------------------------------
# Funciones de visualización
# ---------------------------------------------------------------------------

def imprimir_ast(nodo: NodoAST, prefijo: str = "",
                 es_ultimo: bool = True, _raiz: bool = True) -> None:
    """Imprime el AST con ramas └── / ├──."""
    etiq  = _etiqueta(nodo)
    hijos = _hijos(nodo)

    if _raiz:
        print(etiq)
        for i, hijo in enumerate(hijos):
            imprimir_ast(hijo, "", i == len(hijos) - 1, _raiz=False)
    else:
        rama = "└── " if es_ultimo else "├── "
        ext  = "    " if es_ultimo else "│   "
        print(prefijo + rama + etiq)
        for i, hijo in enumerate(hijos):
            imprimir_ast(hijo, prefijo + ext, i == len(hijos) - 1, _raiz=False)


def _etiqueta(nodo: NodoAST) -> str:
    if isinstance(nodo, _BannerSino):
        return f"sino  [{len(nodo.sentencias)} sent.]"
    match nodo:
        case NodoPrograma():
            return f"NodoPrograma  [{len(nodo.declaraciones)} declaración(es)]"
        case NodoPersonaje():
            return f"NodoPersonaje  '{nodo.nombre}'  (línea {nodo.linea})"
        case NodoAtributo():
            val = _etiqueta(nodo.valor) if isinstance(
                nodo.valor, (NodoEntero, NodoIdentificador, NodoErrorExpr)
            ) else "..."
            return f"NodoAtributo   '{nodo.nombre}'  =  {val}  (línea {nodo.linea})"
        case NodoEscena():
            return f"NodoEscena     '{nodo.nombre}'  (línea {nodo.linea})"
        case NodoMostrar():
            return f"NodoMostrar    {nodo.cadena}  (línea {nodo.linea})"
        case NodoAsignacion():
            return f"NodoAsignacion '{nodo.nombre}'  =  ...  (línea {nodo.linea})"
        case NodoDecision():
            return f"NodoDecision   [{len(nodo.opciones)} opción(es)]  (línea {nodo.linea})"
        case NodoOpcion():
            return f"NodoOpcion     {nodo.etiqueta}  ->  '{nodo.destino}'  (línea {nodo.linea})"
        case NodoSi():
            sino = "con sino" if nodo.cuerpo_sino else "sin sino"
            return f"NodoSi         [{sino}]  (línea {nodo.linea})"
        case NodoCondicion():
            return f"NodoCondicion  '{nodo.operador}'  (línea {nodo.linea})"
        case NodoBinario():
            return f"NodoBinario    '{nodo.operador}'  (línea {nodo.linea})"
        case NodoEntero():
            return f"NodoEntero({nodo.valor})"
        case NodoIdentificador():
            return f"NodoIdentificador('{nodo.nombre}')"
        case NodoErrorExpr():
            return f"NodoErrorExpr  ⚠  (línea {nodo.linea})"
        case _:
            return repr(nodo)


def _hijos(nodo: NodoAST) -> list:
    if isinstance(nodo, _BannerSino):
        return nodo.sentencias
    match nodo:
        case NodoPrograma():
            return nodo.declaraciones
        case NodoPersonaje():
            return nodo.atributos
        case NodoAtributo():
            if isinstance(nodo.valor, (NodoBinario, NodoCondicion, NodoErrorExpr)):
                return [nodo.valor]
            return []
        case NodoEscena():
            return nodo.sentencias
        case NodoMostrar() | NodoOpcion() | NodoEntero() | NodoIdentificador() | NodoErrorExpr():
            return []
        case NodoAsignacion():
            return [nodo.expresion]
        case NodoDecision():
            return nodo.opciones
        case NodoSi():
            hijos = list(nodo.cuerpo_si)
            if nodo.cuerpo_sino:
                hijos.append(_BannerSino(nodo.cuerpo_sino))
            return hijos
        case NodoCondicion():
            return [nodo.izquierda, nodo.derecha]
        case NodoBinario():
            return [nodo.izquierda, nodo.derecha]
        case _:
            return []


def imprimir_errores_sintacticos(errores: List[ErrorSintactico]) -> None:
    if not errores:
        print("  ✓ Sin errores sintácticos.\n")
        return
    fatales      = [e for e in errores if e.fatal]
    recuperables = [e for e in errores if not e.fatal]
    print(f"  {len(errores)} error(es) sintáctico(s)  "
          f"[{len(fatales)} fatal(es), {len(recuperables)} recuperable(s)]:\n")
    for err in errores:
        print(f"  {err}")
    print()


# ---------------------------------------------------------------------------
# Función auxiliar para uso externo
# ---------------------------------------------------------------------------

def parsear(fuente: str, debug: bool = False):
    """
    Conveniencia: lexer + parser sobre el fuente.
    Retorna (ast, errores_lexicos, errores_sintacticos, advertencias).
    """
    tokens, errs_lex = analizar(fuente)
    parser = Parser(tokens, debug=debug)
    ast, errs_sin, advertencias = parser.parsear()
    return ast, errs_lex, errs_sin, advertencias


# ---------------------------------------------------------------------------
# Bloque __main__: pruebas
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Prueba 1: programa válido ───────────────────────────────────────
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

    print("=" * 64)
    print(" PRUEBA 1 — Programa válido")
    print("=" * 64)
    ast1, _, errs1, adv1 = parsear(FUENTE_VALIDA)
    print()
    imprimir_ast(ast1)
    print()
    imprimir_errores_sintacticos(errs1)

    # ── Prueba 2: errores con recuperación y advertencias ───────────────
    FUENTE_ERRORES = """\
personaje heroe {
    vida = 100
    oro  = 50

escena inicio {
    mostrar "Bienvenido"
    decision {
        "Opción A" -> escena_a
    }
}

escena rota {
    si vida > {
        mostrar "mal"
    }
    mostrar 42
}
"""

    print("=" * 64)
    print(" PRUEBA 2 — Errores con recuperación")
    print("=" * 64)
    ast2, _, errs2, adv2 = parsear(FUENTE_ERRORES)
    print()
    imprimir_ast(ast2)
    print()
    imprimir_errores_sintacticos(errs2)
    if adv2:
        print(f"  {len(adv2)} advertencia(s):\n")
        for a in adv2:
            print(f"  {a}")
        print()

    # ── Prueba 3: debug mode (trazado de reglas) ─────────────────────────
    FUENTE_MINI = "escena test { vida = oro + 5 }"

    print("=" * 64)
    print(" PRUEBA 3 — Modo debug (trazado de reglas)")
    print("=" * 64)
    print(f"Fuente: {FUENTE_MINI!r}\n")
    ast3, _, errs3, _ = parsear(FUENTE_MINI, debug=True)
    print()
    imprimir_ast(ast3)
    print()
    imprimir_errores_sintacticos(errs3)

    # ── Prueba 4: referencias inválidas en decision (M3) ─────────────────
    FUENTE_REF = """\
escena menu {
    decision {
        "Ir al bosque" -> bosque
        "Ir al castillo" -> castillo
    }
}
"""
    print("=" * 64)
    print(" PRUEBA 4 — Validación temprana de referencias (M3)")
    print("=" * 64)
    ast4, _, errs4, adv4 = parsear(FUENTE_REF)
    print()
    imprimir_ast(ast4)
    print()
    imprimir_errores_sintacticos(errs4)
    if adv4:
        print(f"  {len(adv4)} advertencia(s):\n")
        for a in adv4:
            print(f"  {a}")
        print()
