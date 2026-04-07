# =============================================================================
# semantico_loreengine.py — Analizador Semántico de LoreEngine
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Estrategia — dos pasadas sobre el AST:
#
#   Pasada 1 (declaraciones):
#     Recorre SOLO las declaraciones de nivel superior (NodoPersonaje y
#     NodoEscena) y registra todos los símbolos en la tabla global.
#     Esto permite que escenas declaradas más abajo sean referenciables
#     desde decisiones que aparecen antes en el fuente.
#     Verifica: M02 (duplicados), M05 (personaje sin atributos), M06 (escena vacía).
#
#   Pasada 2 (verificación):
#     Entra al cuerpo de cada declaración y verifica el uso correcto de
#     identificadores, tipos y referencias.
#     Verifica: M01 (variable no declarada), M03 (escena inexistente en decision),
#               M04 (tipo inválido / NodoErrorExpr).
#
# Códigos de error semántico:
#   M01 — Variable o identificador no declarado
#   M02 — Símbolo redeclarado en el mismo ámbito
#   M03 — Escena referenciada en 'decision' no existe
#   M04 — Tipo inválido en expresión o condición (incl. NodoErrorExpr del parser)
#   M05 — Personaje declarado sin atributos
#   M06 — Escena declarada sin sentencias (vacía)
# =============================================================================

import sys
from dataclasses import dataclass
from typing import List, Optional, Set

from ast_nodes import (
    NodoAST, NodoPrograma, NodoPersonaje, NodoAtributo,
    NodoEscena, NodoMostrar, NodoAsignacion, NodoAsignAtrib,
    NodoDecision, NodoOpcion, NodoSi, NodoCondicion, NodoBinario,
    NodoEntero, NodoIdentificador, NodoAtribPersonaje, NodoDado,
    NodoErrorExpr,
)
from symbol_table import TablaSimbolos, Simbolo


# ---------------------------------------------------------------------------
# Clase de error semántico
# ---------------------------------------------------------------------------

@dataclass
class ErrorSemantico:
    """
    Representa un error detectado durante el análisis semántico.
    No tiene campo 'columna' porque los nodos del AST solo guardan línea.
    """
    codigo:  str    # M01 … M06
    mensaje: str
    linea:   int

    _NOMBRES = {
        "M01": "no_declarado",
        "M02": "redeclarado",
        "M03": "escena_inexistente",
        "M04": "tipo_invalido",
        "M05": "personaje_sin_atributos",
        "M06": "escena_vacia",
        "M07": "principal_duplicado",
    }

    def __repr__(self) -> str:
        nombre = self._NOMBRES.get(self.codigo, self.codigo)
        return (
            f"[{self.codigo}/{nombre}] Error semántico "
            f"en línea {self.linea}: {self.mensaje}"
        )


# ---------------------------------------------------------------------------
# Clase principal: AnalizadorSemantico
# ---------------------------------------------------------------------------

class AnalizadorSemantico:
    """
    Analizador semántico de LoreEngine.

    Uso:
        semantico = AnalizadorSemantico()
        tabla, errores = semantico.analizar(ast)
    """

    def __init__(self):
        self.tabla:   TablaSimbolos      = TablaSimbolos()
        self.errores: List[ErrorSemantico] = []
        # Mapa auxiliar: nombre_personaje → conjunto de nombres de atributos
        # Permite validar dot-notation sin colisiones en la tabla de símbolos
        # cuando dos personajes tienen atributos con el mismo nombre.
        self._attrs_personaje: dict = {}   # Dict[str, Set[str]]
        # Nombre del personaje principal ya declarado (None si aún no hay uno)
        self._nombre_principal: Optional[str] = None

    # -----------------------------------------------------------------------
    # Punto de entrada
    # -----------------------------------------------------------------------

    def analizar(self, programa: NodoPrograma):
        """
        Ejecuta las dos pasadas y retorna (tabla_de_simbolos, errores).
        """
        self._pasada1_declaraciones(programa)
        self._pasada2_verificacion(programa)
        return self.tabla, self.errores

    # -----------------------------------------------------------------------
    # PASADA 1 — Recolección de declaraciones globales
    # -----------------------------------------------------------------------

    def _pasada1_declaraciones(self, programa: NodoPrograma) -> None:
        """
        Recorre todas las declaraciones de nivel superior y las registra
        en el scope global sin entrar a sus cuerpos.
        """
        for decl in programa.declaraciones:
            if isinstance(decl, NodoPersonaje):
                self._registrar_personaje(decl)
            elif isinstance(decl, NodoEscena):
                self._registrar_escena(decl)

    def _registrar_personaje(self, nodo: NodoPersonaje) -> None:
        """Registra un personaje y sus atributos en el scope global."""

        # Declarar el personaje mismo
        if not self.tabla.declarar(nodo.nombre, "PERSONAJE", nodo.linea):
            self._error(
                "M02",
                f"El personaje '{nodo.nombre}' ya fue declarado",
                nodo.linea,
            )

        # M07: solo puede haber un personaje principal
        if nodo.rol == "principal":
            if self._nombre_principal is not None:
                self._error(
                    "M07",
                    f"Solo puede haber un personaje 'principal'; "
                    f"'{self._nombre_principal}' ya fue declarado como principal",
                    nodo.linea,
                )
            else:
                self._nombre_principal = nodo.nombre

        # M05: personaje sin atributos
        if not nodo.atributos:
            self._error(
                "M05",
                f"El personaje '{nodo.nombre}' no tiene atributos definidos",
                nodo.linea,
            )

        # Registrar cada atributo en global (propietario = nombre del personaje).
        # Varios personajes pueden tener atributos con el mismo nombre:
        # se usa dot-notation (goblin.vida vs heroe.vida). La tabla de símbolos
        # guarda solo el primero que llegue; _attrs_personaje rastrea los atributos
        # de cada personaje para la validación de NodoAsignAtrib y NodoAtribPersonaje.
        self._attrs_personaje[nodo.nombre] = set()
        atributos_vistos: Set[str] = set()
        for attr in nodo.atributos:
            if attr.nombre in atributos_vistos:
                # Duplicado DENTRO del mismo personaje → siempre es error
                self._error(
                    "M02",
                    f"Atributo '{attr.nombre}' duplicado en personaje '{nodo.nombre}'",
                    attr.linea,
                )
            else:
                atributos_vistos.add(attr.nombre)
                self._attrs_personaje[nodo.nombre].add(attr.nombre)
                # Extraer valor inicial si es un literal entero simple,
                # para registrarlo en la tabla (los valores complejos quedan en 0).
                valor_inicial = (attr.valor.valor
                                 if isinstance(attr.valor, NodoEntero) else 0)
                # Si el nombre ya existe (de otro personaje), no es error:
                # se accederá vía dot-notation. El primer registro gana en la tabla.
                self.tabla.declarar(
                    attr.nombre, "ATRIBUTO", attr.linea,
                    propietario=nodo.nombre,
                    valor=valor_inicial,
                )

    def _registrar_escena(self, nodo: NodoEscena) -> None:
        """Registra una escena en el scope global."""

        # Declarar la escena
        if not self.tabla.declarar(nodo.nombre, "ESCENA", nodo.linea):
            sim = self.tabla.buscar_en_global(nodo.nombre)
            self._error(
                "M02",
                f"La escena '{nodo.nombre}' ya fue declarada "
                f"(primera declaración en línea {sim.linea if sim else '?'})",
                nodo.linea,
            )

        # M06: escena vacía
        if not nodo.sentencias:
            self._error(
                "M06",
                f"La escena '{nodo.nombre}' está vacía (sin sentencias)",
                nodo.linea,
            )

    # -----------------------------------------------------------------------
    # PASADA 2 — Verificación de uso
    # -----------------------------------------------------------------------

    def _pasada2_verificacion(self, programa: NodoPrograma) -> None:
        """
        Verifica el cuerpo de cada declaración: expresiones, referencias
        de escenas, tipos de variables y condiciones.
        """
        for decl in programa.declaraciones:
            if isinstance(decl, NodoPersonaje):
                self._verificar_personaje(decl)
            elif isinstance(decl, NodoEscena):
                self._verificar_escena(decl)

    # ── Personaje ────────────────────────────────────────────────────────

    def _verificar_personaje(self, nodo: NodoPersonaje) -> None:
        """
        Verifica las expresiones de valor inicial de cada atributo.
        En pasada 2 todos los atributos ya están declarados, por lo que
        pueden referenciarse mutuamente (ej: fuerza = base * 2).
        """
        for attr in nodo.atributos:
            self._verificar_expresion(attr.valor, contexto=nodo.nombre)

    # ── Escena ───────────────────────────────────────────────────────────

    def _verificar_escena(self, nodo: NodoEscena) -> None:
        """Abre scope de escena, verifica sentencias, cierra scope."""
        self.tabla.entrar_ambito(nodo.nombre)
        for sent in nodo.sentencias:
            self._verificar_sentencia(sent)
        self.tabla.salir_ambito()

    # ── Sentencias ───────────────────────────────────────────────────────

    def _verificar_sentencia(self, nodo: NodoAST) -> None:
        """Despacha la verificación según el tipo de sentencia."""
        if isinstance(nodo, NodoMostrar):
            pass   # cadena literal; siempre válida

        elif isinstance(nodo, NodoAsignacion):
            self._verificar_asignacion(nodo)

        elif isinstance(nodo, NodoAsignAtrib):
            self._verificar_asignacion_atrib(nodo)

        elif isinstance(nodo, NodoDecision):
            self._verificar_decision(nodo)

        elif isinstance(nodo, NodoSi):
            self._verificar_si(nodo)

        # NodoErrorExpr a nivel de sentencia (no debería ocurrir, pero por seguridad)
        elif isinstance(nodo, NodoErrorExpr):
            self._error(
                "M04",
                "Sentencia inválida heredada del análisis sintáctico",
                nodo.linea,
            )

    def _verificar_asignacion(self, nodo: NodoAsignacion) -> None:
        """
        Verifica que el destino de la asignación sea una variable accesible
        (ATRIBUTO o VARIABLE) y que la expresión sea semánticamente válida.
        """
        sim = self.tabla.buscar(nodo.nombre)

        if sim is None:
            # M01: identificador completamente desconocido
            self._error(
                "M01",
                f"Variable '{nodo.nombre}' no declarada; "
                f"¿es un atributo del personaje?",
                nodo.linea,
            )
        elif sim.tipo not in ("ATRIBUTO", "VARIABLE"):
            # M04: intentar asignar a algo que no es una variable (ej: escena o personaje)
            self._error(
                "M04",
                f"'{nodo.nombre}' es de tipo {sim.tipo!r} y no puede "
                f"usarse como destino de asignación",
                nodo.linea,
            )

        # Verificar la expresión del lado derecho
        self._verificar_expresion(nodo.expresion, contexto=self.tabla.ambito_actual)

    def _verificar_asignacion_atrib(self, nodo: NodoAsignAtrib) -> None:
        """
        Verifica una asignación de la forma personaje.atributo = expresion.

        M01 si el personaje no está declarado.
        M01 si el atributo no pertenece a ese personaje.
        """
        sim = self.tabla.buscar_en_global(nodo.personaje)
        if sim is None or sim.tipo != "PERSONAJE":
            self._error(
                "M01",
                f"Personaje '{nodo.personaje}' no declarado",
                nodo.linea,
            )
        else:
            attrs = self._attrs_personaje.get(nodo.personaje, set())
            if nodo.atributo not in attrs:
                self._error(
                    "M01",
                    f"'{nodo.atributo}' no es un atributo de '{nodo.personaje}'",
                    nodo.linea,
                )

        self._verificar_expresion(nodo.expresion,
                                  contexto=self.tabla.ambito_actual)

    def _verificar_decision(self, nodo: NodoDecision) -> None:
        """
        Verifica que cada escena destino de las opciones esté declarada.
        M03: escena destino inexistente.
        """
        for opcion in nodo.opciones:
            sim = self.tabla.buscar_en_global(opcion.destino)
            if sim is None or sim.tipo != "ESCENA":
                self._error(
                    "M03",
                    f"La escena destino '{opcion.destino}' en la opción "
                    f"{opcion.etiqueta} no existe",
                    opcion.linea,
                )

    def _verificar_si(self, nodo: NodoSi) -> None:
        """Verifica condición y ambas ramas del condicional."""
        self._verificar_condicion(nodo.condicion)
        for sent in nodo.cuerpo_si:
            self._verificar_sentencia(sent)
        for sent in nodo.cuerpo_sino:
            self._verificar_sentencia(sent)

    # ── Condiciones ──────────────────────────────────────────────────────

    def _verificar_condicion(self, nodo: NodoAST) -> None:
        """
        Verifica una condición relacional.
        Detecta NodoErrorExpr heredado del parser (M04).
        """
        if isinstance(nodo, NodoErrorExpr):
            self._error(
                "M04",
                "Condición inválida (error de análisis sintáctico en línea anterior)",
                nodo.linea,
            )
            return

        if isinstance(nodo, NodoCondicion):
            self._verificar_expresion(nodo.izquierda,
                                      contexto=self.tabla.ambito_actual)
            self._verificar_expresion(nodo.derecha,
                                      contexto=self.tabla.ambito_actual)
        else:
            # Nodo inesperado en posición de condición
            self._error(
                "M04",
                f"Se esperaba una condición relacional, "
                f"se encontró {type(nodo).__name__}",
                getattr(nodo, "linea", 0),
            )

    # ── Expresiones ──────────────────────────────────────────────────────

    def _verificar_expresion(self, nodo: NodoAST,
                              contexto: str = "global") -> None:
        """
        Verifica recursivamente una expresión aritmética.

        Casos:
          NodoEntero        → siempre válido
          NodoIdentificador → debe existir como ATRIBUTO o VARIABLE (M01/M04)
          NodoBinario       → verificar ambos operandos
          NodoErrorExpr     → error M04 heredado del parser
        """
        if isinstance(nodo, NodoEntero):
            return   # literal entero: siempre válido

        elif isinstance(nodo, NodoIdentificador):
            sim = self.tabla.buscar(nodo.nombre)
            if sim is None:
                self._error(
                    "M01",
                    f"Identificador '{nodo.nombre}' no declarado "
                    f"(en contexto '{contexto}')",
                    nodo.linea,
                )
            elif sim.tipo not in ("ATRIBUTO", "VARIABLE"):
                # Ej: usar el nombre de una escena o personaje como valor numérico
                self._error(
                    "M04",
                    f"'{nodo.nombre}' es de tipo {sim.tipo!r} y no puede "
                    f"usarse como valor numérico en una expresión",
                    nodo.linea,
                )

        elif isinstance(nodo, NodoBinario):
            self._verificar_expresion(nodo.izquierda, contexto)
            self._verificar_expresion(nodo.derecha,   contexto)

        elif isinstance(nodo, NodoDado):
            # El argumento de dado() debe ser una expresión válida
            self._verificar_expresion(nodo.argumento, contexto)

        elif isinstance(nodo, NodoAtribPersonaje):
            # personaje.atributo — verificar que ambos existen
            sim = self.tabla.buscar_en_global(nodo.personaje)
            if sim is None or sim.tipo != "PERSONAJE":
                self._error(
                    "M01",
                    f"Personaje '{nodo.personaje}' no declarado",
                    nodo.linea,
                )
            else:
                attrs = self._attrs_personaje.get(nodo.personaje, set())
                if nodo.atributo not in attrs:
                    self._error(
                        "M01",
                        f"'{nodo.atributo}' no es un atributo de "
                        f"'{nodo.personaje}'",
                        nodo.linea,
                    )

        elif isinstance(nodo, NodoErrorExpr):
            self._error(
                "M04",
                "Expresión inválida heredada del análisis sintáctico",
                nodo.linea,
            )

        else:
            # Nodo desconocido en posición de expresión (extensiones futuras)
            self._error(
                "M04",
                f"Nodo inesperado en expresión: {type(nodo).__name__}",
                getattr(nodo, "linea", 0),
            )

    # -----------------------------------------------------------------------
    # Registro interno de errores
    # -----------------------------------------------------------------------

    def _error(self, codigo: str, mensaje: str, linea: int) -> None:
        self.errores.append(ErrorSemantico(codigo=codigo,
                                           mensaje=mensaje,
                                           linea=linea))


# ---------------------------------------------------------------------------
# Funciones de visualización
# ---------------------------------------------------------------------------

def imprimir_errores_semanticos(errores: List[ErrorSemantico]) -> None:
    """Imprime los errores semánticos con formato."""
    if not errores:
        print("  ✓ Sin errores semánticos.\n")
        return
    # Agrupar por código para el resumen
    por_codigo: dict = {}
    for err in errores:
        por_codigo.setdefault(err.codigo, []).append(err)

    print(f"  Se encontraron {len(errores)} error(es) semántico(s):\n")
    for err in errores:
        print(f"  {err}")
    print()
    print("  Resumen por código:")
    for codigo, lista in sorted(por_codigo.items()):
        nombre = ErrorSemantico._NOMBRES.get(codigo, codigo)
        print(f"    {codigo}/{nombre}: {len(lista)} error(es)")
    print()


# ---------------------------------------------------------------------------
# Función auxiliar para uso externo (pipeline completo)
# ---------------------------------------------------------------------------

def analizar(fuente: str):
    """
    Conveniencia: ejecuta el pipeline léxico + sintáctico + semántico.
    Retorna (ast, tabla, errs_lex, errs_sin, errs_sem, advertencias_sin).
    """
    from lexer_loreengine   import analizar as lex_analizar
    from parser_loreengine  import Parser

    tokens, errs_lex = lex_analizar(fuente)
    parser           = Parser(tokens)
    ast, errs_sin, advertencias = parser.parsear()

    semantico        = AnalizadorSemantico()
    tabla, errs_sem  = semantico.analizar(ast)

    return ast, tabla, errs_lex, errs_sin, errs_sem, advertencias


# ---------------------------------------------------------------------------
# Bloque __main__: pruebas autocontenidas
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Prueba 1: programa completamente válido ─────────────────────────
    FUENTE_VALIDA = """\
personaje heroe {
    vida   = 100
    oro    = 50
    fuerza = 20
}

escena inicio {
    mostrar "Bienvenido."
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

escena final {
    mostrar "Fin de la aventura."
}
"""

    print("=" * 64)
    print(" PRUEBA 1 — Programa válido")
    print("=" * 64)
    ast1, tabla1, _, _, errs1, _ = analizar(FUENTE_VALIDA)
    print("\n  Tabla de símbolos:\n")
    tabla1.imprimir()
    imprimir_errores_semanticos(errs1)

    # ── Prueba 2: M01 variable no declarada ─────────────────────────────
    FUENTE_M01 = """\
personaje heroe { vida = 100 }

escena combate {
    magia = magia - 5
    oro   = poder + vida
}
"""
    print("=" * 64)
    print(" PRUEBA 2 — M01: variable no declarada")
    print("=" * 64)
    _, tabla2, _, _, errs2, _ = analizar(FUENTE_M01)
    imprimir_errores_semanticos(errs2)

    # ── Prueba 3: M02 símbolo redeclarado ───────────────────────────────
    FUENTE_M02 = """\
personaje heroe { vida = 100  vida = 200 }

escena inicio { mostrar "Hola." }
escena inicio { mostrar "Otra vez." }
"""
    print("=" * 64)
    print(" PRUEBA 3 — M02: símbolo redeclarado")
    print("=" * 64)
    _, _, _, _, errs3, _ = analizar(FUENTE_M02)
    imprimir_errores_semanticos(errs3)

    # ── Prueba 4: M03 escena inexistente en decision ─────────────────────
    FUENTE_M03 = """\
personaje heroe { vida = 100 }

escena menu {
    decision {
        "Ir al bosque"   -> bosque
        "Ir al castillo" -> castillo
    }
}
"""
    print("=" * 64)
    print(" PRUEBA 4 — M03: escena inexistente en decision")
    print("=" * 64)
    _, _, _, _, errs4, _ = analizar(FUENTE_M03)
    imprimir_errores_semanticos(errs4)

    # ── Prueba 5: M04 tipo inválido (usar escena como valor) ────────────
    FUENTE_M04 = """\
personaje heroe { vida = 100 }

escena prueba {
    vida = inicio + 5
}

escena inicio { mostrar "Hola." }
"""
    print("=" * 64)
    print(" PRUEBA 5 — M04: tipo inválido en expresión")
    print("=" * 64)
    _, _, _, _, errs5, _ = analizar(FUENTE_M04)
    imprimir_errores_semanticos(errs5)

    # ── Prueba 6: M05 personaje sin atributos ───────────────────────────
    FUENTE_M05 = """\
personaje fantasma { }

escena inicio { mostrar "El fantasma aparece." }
"""
    print("=" * 64)
    print(" PRUEBA 6 — M05: personaje sin atributos")
    print("=" * 64)
    _, _, _, _, errs6, _ = analizar(FUENTE_M05)
    imprimir_errores_semanticos(errs6)

    # ── Prueba 7: M06 escena vacía ───────────────────────────────────────
    FUENTE_M06 = """\
personaje heroe { vida = 100 }

escena vacia { }

escena inicio { mostrar "Inicio." }
"""
    print("=" * 64)
    print(" PRUEBA 7 — M06: escena vacía")
    print("=" * 64)
    _, _, _, _, errs7, _ = analizar(FUENTE_M06)
    imprimir_errores_semanticos(errs7)

    # ── Prueba 8: múltiples errores combinados ───────────────────────────
    FUENTE_MULTI = """\
personaje heroe { vida = 100 }
personaje heroe { fuerza = 20 }

escena inicio {
    vida = mana + 5
    decision {
        "Huir" -> escape
    }
}

escena inicio { mostrar "Duplicada." }
"""
    print("=" * 64)
    print(" PRUEBA 8 — Errores combinados (M01, M02, M03)")
    print("=" * 64)
    _, tabla8, _, _, errs8, _ = analizar(FUENTE_MULTI)
    tabla8.imprimir()
    imprimir_errores_semanticos(errs8)
