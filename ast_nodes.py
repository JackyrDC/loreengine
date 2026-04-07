# =============================================================================
# ast_nodes.py — Nodos del Árbol de Sintaxis Abstracta (AST) de LoreEngine
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Este archivo define ÚNICAMENTE las clases de nodos del AST.
# No contiene lógica de parsing, análisis semántico ni interpretación.
#
# Jerarquía de nodos (refleja la gramática EBNF del lenguaje):
#
#   NodoAST                      ← clase base abstracta
#   ├── NodoPrograma             ← raíz: lista de declaraciones
#   ├── NodoPersonaje            ← def_personaje
#   │   └── NodoAtributo         ← atributo dentro de personaje
#   ├── NodoEscena               ← def_escena
#   │   └── sentencias:
#   │       ├── NodoMostrar      ← sent_mostrar
#   │       ├── NodoAsignacion   ← sent_asignacion  (var = expr)
#   │       ├── NodoAsignAtrib   ← sent_asignacion  (personaje.attr = expr)
#   │       ├── NodoDecision     ← sent_decision
#   │       │   └── NodoOpcion   ← opcion dentro de decision
#   │       └── NodoSi           ← sent_si (con rama sino opcional)
#   └── expresiones:
#       ├── NodoBinario          ← expresion con operador aritmético o relacional
#       ├── NodoEntero           ← literal entero
#       ├── NodoIdentificador    ← nombre de variable (atributo del héroe)
#       ├── NodoAtribPersonaje   ← personaje.atributo (acceso a NPC)
#       └── NodoDado             ← dado(n)  → entero aleatorio 1..n
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Clase base
# ---------------------------------------------------------------------------

class NodoAST:
    """
    Clase base para todos los nodos del AST.
    Proporciona una interfaz uniforme para el visitor pattern que
    usarán el analizador semántico y el intérprete.
    """

    def __repr__(self) -> str:
        # Implementación por defecto; las subclases la sobreescriben
        return f"{self.__class__.__name__}()"


# ---------------------------------------------------------------------------
# Nodo raíz
# ---------------------------------------------------------------------------

@dataclass
class NodoPrograma(NodoAST):
    """
    Raíz del AST. Contiene todas las declaraciones del programa
    (personajes y escenas) en el orden en que aparecen en el fuente.

    Gramática: programa ::= declaracion+
    """
    declaraciones: List[NodoAST]   # lista de NodoPersonaje y NodoEscena
    linea: int = 1                 # siempre línea 1 (inicio del archivo)

    def __repr__(self) -> str:
        return (
            f"NodoPrograma(declaraciones={len(self.declaraciones)}, "
            f"línea={self.linea})"
        )


# ---------------------------------------------------------------------------
# Declaraciones de personaje
# ---------------------------------------------------------------------------

@dataclass
class NodoAtributo(NodoAST):
    """
    Un atributo numérico dentro de un bloque personaje.

    Gramática: atributo ::= IDENTIFICADOR '=' expresion
    Ejemplo:   vida = 100
    """
    nombre: str          # nombre del atributo (ej: "vida")
    valor: NodoAST       # expresión que representa el valor inicial
    linea: int

    def __repr__(self) -> str:
        return f"NodoAtributo(nombre={self.nombre!r}, valor={self.valor!r}, línea={self.linea})"


@dataclass
class NodoPersonaje(NodoAST):
    """
    Declaración completa de un personaje con sus atributos y rol.

    Gramática:
        def_personaje ::= 'personaje' rol? IDENTIFICADOR '{' atributo* '}'
        rol           ::= 'principal' | 'enemigo' | 'aliado' | 'neutral'

    Ejemplos:
        personaje principal cazador { vida = 100 }
        personaje enemigo   lobo    { vida = 55  }
        personaje aliado    brujo   { vida = 90  }
        personaje neutral   aldeano { vida = 30  }
        personaje heroe { vida = 100 }   ← sin rol → 'neutral' por defecto

    Roles:
        principal — protagonista / agente principal (solo puede haber uno)
        enemigo   — NPC hostil / agente adversario
        aliado    — NPC amigable / agente cooperativo
        neutral   — entidad sin bando / variable de entorno (valor por defecto)
    """
    nombre: str                    # identificador del personaje (ej: "cazador")
    atributos: List[NodoAtributo]  # lista de atributos declarados
    linea: int
    rol: str = "neutral"           # "principal"|"enemigo"|"aliado"|"neutral"

    def __repr__(self) -> str:
        return (
            f"NodoPersonaje(nombre={self.nombre!r}, rol={self.rol!r}, "
            f"atributos={len(self.atributos)}, línea={self.linea})"
        )


# ---------------------------------------------------------------------------
# Sentencias dentro de escenas
# ---------------------------------------------------------------------------

@dataclass
class NodoMostrar(NodoAST):
    """
    Sentencia de salida de texto al jugador.

    Gramática: sent_mostrar ::= 'mostrar' CADENA
    Ejemplo:   mostrar "Estás en el bosque."
    """
    cadena: str    # texto con las comillas incluidas, ej: '"Hola mundo"'
    linea: int

    def __repr__(self) -> str:
        return f"NodoMostrar(cadena={self.cadena!r}, línea={self.linea})"


@dataclass
class NodoAsignacion(NodoAST):
    """
    Asignación de una expresión a una variable.

    Gramática: sent_asignacion ::= IDENTIFICADOR '=' expresion
    Ejemplo:   vida = vida - 10
    """
    nombre: str      # variable destino
    expresion: NodoAST
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoAsignacion(nombre={self.nombre!r}, "
            f"expresion={self.expresion!r}, línea={self.linea})"
        )


@dataclass
class NodoOpcion(NodoAST):
    """
    Una opción dentro de un bloque decision.

    Gramática: opcion ::= CADENA '->' IDENTIFICADOR
    Ejemplo:   "Explorar" -> bosque
    """
    etiqueta: str    # texto de la opción, ej: '"Explorar"'
    destino: str     # nombre de la escena destino, ej: "bosque"
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoOpcion(etiqueta={self.etiqueta!r}, "
            f"destino={self.destino!r}, línea={self.linea})"
        )


@dataclass
class NodoDecision(NodoAST):
    """
    Punto de decisión interactiva: muestra opciones al jugador
    y salta a la escena correspondiente.

    Gramática: sent_decision ::= 'decision' '{' opcion+ '}'
    """
    opciones: List[NodoOpcion]
    linea: int

    def __repr__(self) -> str:
        return f"NodoDecision(opciones={len(self.opciones)}, línea={self.linea})"


@dataclass
class NodoSi(NodoAST):
    """
    Condicional con rama 'sino' opcional.

    Gramática:
        sent_si ::= 'si' condicion '{' sentencia* '}'
                    ('sino' '{' sentencia* '}')?
    """
    condicion: NodoAST              # siempre un NodoCondicion
    cuerpo_si: List[NodoAST]        # sentencias de la rama verdadera
    cuerpo_sino: List[NodoAST]      # sentencias de la rama falsa (puede ser [])
    linea: int

    def __repr__(self) -> str:
        tiene_sino = len(self.cuerpo_sino) > 0
        return (
            f"NodoSi(condicion={self.condicion!r}, "
            f"si={len(self.cuerpo_si)} sent., "
            f"sino={'sí' if tiene_sino else 'no'}, línea={self.linea})"
        )


# ---------------------------------------------------------------------------
# Declaración de escena
# ---------------------------------------------------------------------------

@dataclass
class NodoEscena(NodoAST):
    """
    Declaración completa de una escena con su cuerpo de sentencias.

    Gramática: def_escena ::= 'escena' IDENTIFICADOR '{' sentencia* '}'
    """
    nombre: str                  # identificador de la escena (ej: "inicio")
    sentencias: List[NodoAST]    # cuerpo: NodoMostrar, NodoAsignacion, etc.
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoEscena(nombre={self.nombre!r}, "
            f"sentencias={len(self.sentencias)}, línea={self.linea})"
        )


# ---------------------------------------------------------------------------
# Expresiones aritméticas y condiciones
# ---------------------------------------------------------------------------

@dataclass
class NodoCondicion(NodoAST):
    """
    Condición relacional usada en sentencias 'si'.

    Gramática: condicion ::= expresion op_relacional expresion
    Ejemplo:   vida > 0
    """
    izquierda: NodoAST    # expresión del lado izquierdo
    operador: str         # "==", "!=", ">", "<", ">=", "<="
    derecha: NodoAST      # expresión del lado derecho
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoCondicion({self.izquierda!r} {self.operador} "
            f"{self.derecha!r}, línea={self.linea})"
        )


@dataclass
class NodoBinario(NodoAST):
    """
    Operación aritmética binaria.

    Gramática:
        expresion ::= termino (('+' | '-') termino)*
        termino   ::= factor (('*' | '/') factor)*
    Ejemplo:   fuerza * 2
    """
    izquierda: NodoAST
    operador: str     # "+", "-", "*", "/"
    derecha: NodoAST
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoBinario({self.izquierda!r} {self.operador} "
            f"{self.derecha!r}, línea={self.linea})"
        )


@dataclass
class NodoEntero(NodoAST):
    """
    Literal entero.

    Gramática: factor ::= ENTERO
    Ejemplo:   100
    """
    valor: int
    linea: int

    def __repr__(self) -> str:
        return f"NodoEntero({self.valor}, línea={self.linea})"


@dataclass
class NodoIdentificador(NodoAST):
    """
    Referencia a una variable o atributo de personaje.

    Gramática: factor ::= IDENTIFICADOR
    Ejemplo:   vida   (dentro de una expresión)
    """
    nombre: str
    linea: int

    def __repr__(self) -> str:
        return f"NodoIdentificador({self.nombre!r}, línea={self.linea})"


@dataclass
class NodoDado(NodoAST):
    """
    Función dado(n): retorna un entero aleatorio entre 1 y n.

    Gramática: factor ::= 'dado' '(' expresion ')'
    Ejemplo:   dado(6)   → entero entre 1 y 6
               dado(20)  → entero entre 1 y 20
    """
    argumento: NodoAST   # expresión que define el máximo del dado
    linea: int

    def __repr__(self) -> str:
        return f"NodoDado(argumento={self.argumento!r}, línea={self.linea})"


@dataclass
class NodoAtribPersonaje(NodoAST):
    """
    Acceso al atributo de un personaje específico mediante notación de punto.

    Gramática: factor ::= IDENTIFICADOR '.' IDENTIFICADOR
    Ejemplo:   goblin.vida   → valor del atributo 'vida' del personaje 'goblin'
    """
    personaje: str   # nombre del personaje (ej: "goblin")
    atributo:  str   # nombre del atributo  (ej: "vida")
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoAtribPersonaje({self.personaje!r}.{self.atributo!r}, "
            f"línea={self.linea})"
        )


@dataclass
class NodoAsignAtrib(NodoAST):
    """
    Asignación a un atributo de un personaje específico.

    Gramática: sent_asignacion ::= IDENTIFICADOR '.' IDENTIFICADOR '=' expresion
    Ejemplo:   goblin.vida = goblin.vida - 10
    """
    personaje: str     # personaje destino (ej: "goblin")
    atributo:  str     # atributo destino  (ej: "vida")
    expresion: NodoAST
    linea: int

    def __repr__(self) -> str:
        return (
            f"NodoAsignAtrib({self.personaje!r}.{self.atributo!r} = "
            f"{self.expresion!r}, línea={self.linea})"
        )


@dataclass
class NodoErrorExpr(NodoAST):
    """
    Centinela que marca el lugar donde una expresión no pudo parsearse.
    Permite que el parser devuelva un nodo válido en lugar de None,
    evitando propagación de None y ASTs incompletos sin advertencia.
    El analizador semántico lo detecta y lo trata como error M04.
    """
    linea: int

    def __repr__(self) -> str:
        return f"NodoErrorExpr(línea={self.linea})"


# ---------------------------------------------------------------------------
# Bloque __main__: prueba de construcción manual del AST
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print(" PRUEBA — Construcción manual de un AST mínimo")
    print("=" * 60)

    # Construir el AST equivalente a:
    #
    #   personaje heroe { vida = 100  oro = 50 }
    #
    #   escena inicio {
    #       mostrar "Bienvenido."
    #       si vida > 0 {
    #           mostrar "Sigues vivo."
    #       } sino {
    #           mostrar "Has muerto."
    #       }
    #       decision {
    #           "Explorar" -> bosque
    #           "Salir"    -> final
    #       }
    #   }

    # ── Personaje ──────────────────────────────────────────────────────
    attr_vida  = NodoAtributo("vida",  NodoEntero(100, 1), linea=2)
    attr_oro   = NodoAtributo("oro",   NodoEntero(50,  1), linea=3)
    personaje  = NodoPersonaje("heroe", [attr_vida, attr_oro], linea=1)

    # ── Escena inicio ──────────────────────────────────────────────────
    mostrar1 = NodoMostrar('"Bienvenido."', linea=7)

    condicion = NodoCondicion(
        izquierda=NodoIdentificador("vida", linea=8),
        operador=">",
        derecha=NodoEntero(0, linea=8),
        linea=8,
    )
    cuerpo_si   = [NodoMostrar('"Sigues vivo."',  linea=9)]
    cuerpo_sino = [NodoMostrar('"Has muerto."',   linea=11)]
    nodo_si = NodoSi(condicion, cuerpo_si, cuerpo_sino, linea=8)

    opcion1 = NodoOpcion('"Explorar"', "bosque", linea=14)
    opcion2 = NodoOpcion('"Salir"',    "final",  linea=15)
    decision = NodoDecision([opcion1, opcion2], linea=13)

    escena = NodoEscena("inicio", [mostrar1, nodo_si, decision], linea=6)

    # ── Programa raíz ──────────────────────────────────────────────────
    programa = NodoPrograma([personaje, escena], linea=1)

    # ── Imprimir representaciones ──────────────────────────────────────
    print("\n  repr() de cada nodo:\n")

    nodos = [
        ("NodoPrograma",      programa),
        ("NodoPersonaje",     personaje),
        ("NodoAtributo",      attr_vida),
        ("NodoEscena",        escena),
        ("NodoMostrar",       mostrar1),
        ("NodoCondicion",     condicion),
        ("NodoBinario",       NodoBinario(
                                  NodoIdentificador("fuerza", 1),
                                  "*",
                                  NodoEntero(2, 1),
                                  linea=1)),
        ("NodoEntero",        NodoEntero(42, linea=1)),
        ("NodoIdentificador", NodoIdentificador("oro", linea=1)),
        ("NodoSi",            nodo_si),
        ("NodoDecision",      decision),
        ("NodoOpcion",        opcion1),
        ("NodoAsignacion",    NodoAsignacion(
                                  "vida",
                                  NodoBinario(
                                      NodoIdentificador("vida", 1),
                                      "-",
                                      NodoEntero(10, 1),
                                      linea=1),
                                  linea=1)),
    ]

    ancho = max(len(nombre) for nombre, _ in nodos)
    for nombre, nodo in nodos:
        print(f"  {nombre:<{ancho}}  →  {nodo!r}")

    # ── Verificar estructura del árbol ─────────────────────────────────
    print("\n  Verificaciones de estructura:\n")

    assert isinstance(programa.declaraciones[0], NodoPersonaje), "primera decl. debe ser NodoPersonaje"
    assert isinstance(programa.declaraciones[1], NodoEscena),    "segunda decl. debe ser NodoEscena"
    assert len(personaje.atributos) == 2,                        "heroe debe tener 2 atributos"
    assert len(escena.sentencias)   == 3,                        "inicio debe tener 3 sentencias"
    assert isinstance(escena.sentencias[1], NodoSi),             "segunda sentencia debe ser NodoSi"
    assert len(nodo_si.cuerpo_sino) == 1,                        "rama sino debe tener 1 sentencia"
    assert len(decision.opciones)   == 2,                        "decision debe tener 2 opciones"
    assert opcion1.destino == "bosque",                          "destino de opcion1 debe ser 'bosque'"

    print("  ✓ Todas las verificaciones pasaron.")
    print("  ✓ ast_nodes.py listo para ser importado por el parser.\n")
