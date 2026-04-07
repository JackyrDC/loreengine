# =============================================================================
# main_consola.py — Punto de entrada de LoreEngine en modo consola
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Uso:
#   python main_consola.py                → ejecuta el ejemplo integrado
#   python main_consola.py historia.lore  → ejecuta el archivo dado
#
# Salida por fases:
#   ─ Fase 1: Léxico     tabla de tokens + conteo + errores léxicos
#   ─ Fase 2: Sintáctico árbol AST + errores/advertencias
#   ─ Fase 3: Semántico  tabla de símbolos + errores semánticos
#   ─ Fase 4: Ejecución  historia interactiva con panel de personaje
#
# Si hay errores fatales en la Fase 2 o cualquier error en la Fase 3,
# el pipeline se detiene antes de ejecutar.
# Errores léxicos y sintácticos no-fatales son reportados pero permiten
# continuar para mostrar el diagnóstico completo al usuario.
# =============================================================================

import sys
import os
import io
import contextlib

# Configurar salida UTF-8 antes de cualquier importación que imprima
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from lexer_loreengine     import analizar as lex_analizar, Token, ErrorLexico
from parser_loreengine    import Parser, imprimir_ast, ErrorSintactico
from semantico_loreengine import AnalizadorSemantico, ErrorSemantico
from interprete_loreengine import Interprete, ErrorEjecucion


# ---------------------------------------------------------------------------
# Constantes visuales
# ---------------------------------------------------------------------------

_ANCHO = 62   # ancho total de las cajas del pipeline


# ---------------------------------------------------------------------------
# Ayudas de presentación del pipeline
# ---------------------------------------------------------------------------

def _caja(texto: str, caracter_borde: str = "═") -> None:
    """Imprime un encabezado enmarcado con el texto centrado."""
    interior = _ANCHO - 4          # espacio entre │  y  │
    print("╔" + caracter_borde * (_ANCHO - 2) + "╗")
    print(f"║  {texto:<{interior}}║")
    print("╚" + caracter_borde * (_ANCHO - 2) + "╝")


def _titulo_fase(numero: int, nombre: str) -> None:
    """Imprime el encabezado decorado de una fase del compilador."""
    print()
    interior = _ANCHO - 4
    etiqueta = f"FASE {numero}: {nombre}"
    print("┌" + "─" * (_ANCHO - 2) + "┐")
    print(f"│  {etiqueta:<{interior}}│")
    print("└" + "─" * (_ANCHO - 2) + "┘")


def _ok(mensaje: str) -> None:
    print(f"  ✓  {mensaje}")


def _err(mensaje: str) -> None:
    print(f"  ✗  {mensaje}")


def _warn(mensaje: str) -> None:
    print(f"  ⚠  {mensaje}")


def _capturar_stdout(func, *args, **kwargs) -> str:
    """Llama a func(*args, **kwargs) y captura lo que imprime en stdout."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Mostrar resultados de cada fase
# ---------------------------------------------------------------------------

def _mostrar_fase_lexico(tokens, errores) -> None:
    """
    Fase 1: imprime tabla de tokens con columnas alineadas y lista de errores.
    """
    _titulo_fase(1, "ANÁLISIS LÉXICO")

    # Filtrar EOF para el conteo y la tabla
    tokens_visibles = [t for t in tokens if t.tipo != "EOF"]

    if not tokens_visibles:
        print("\n  (sin tokens reconocidos)\n")
    else:
        # Anchos de columna dinámicos (mínimo: cabecera)
        at = max((len(t.tipo)         for t in tokens_visibles), default=4)
        av = max((len(repr(t.valor))  for t in tokens_visibles), default=5)
        at = max(at, 4)
        av = max(av, 5)

        sep = "  " + "─" * (at + av + 20)
        enc = f"  {'TIPO':<{at}}  {'VALOR':<{av}}  {'LÍNEA':>5}  {'COL':>4}"
        print()
        print(sep)
        print(enc)
        print(sep)
        for tok in tokens_visibles:
            val_repr = repr(tok.valor)
            print(
                f"  {tok.tipo:<{at}}  {val_repr:<{av}}"
                f"  {tok.linea:>5}  {tok.columna:>4}"
            )
        print(sep)
        print(f"  Total: {len(tokens_visibles)} token(s)\n")

    if errores:
        print(f"  {len(errores)} error(es) léxico(s):\n")
        for e in errores:
            _err(str(e))
        print()
    else:
        _ok("Sin errores léxicos.")
        print()


def _mostrar_fase_sintactico(ast, errores, advertencias) -> None:
    """
    Fase 2: imprime el árbol AST e informa errores y advertencias.
    """
    _titulo_fase(2, "ANÁLISIS SINTÁCTICO")

    if ast is not None:
        print("\n  Árbol AST:\n")
        salida = _capturar_stdout(imprimir_ast, ast)
        for linea in salida.splitlines():
            print("  " + linea)
        print()

    if advertencias:
        print(f"  {len(advertencias)} advertencia(s):\n")
        for adv in advertencias:
            _warn(adv)
        print()

    if errores:
        print(f"  {len(errores)} error(es) sintáctico(s):\n")
        for e in errores:
            severidad = "[FATAL]" if e.fatal else ""
            _err(f"{severidad} {e}")
        print()
    else:
        _ok("Sin errores sintácticos.")
        print()


def _mostrar_fase_semantico(tabla, errores) -> None:
    """
    Fase 3: imprime la tabla de símbolos y lista de errores semánticos.
    """
    _titulo_fase(3, "ANÁLISIS SEMÁNTICO")

    if tabla is not None:
        print("\n  Tabla de símbolos:\n")
        salida = _capturar_stdout(tabla.imprimir)
        for linea in salida.splitlines():
            print("  " + linea)
        print()

    if errores:
        print(f"  {len(errores)} error(es) semántico(s):\n")
        for e in errores:
            _err(str(e))
        print()
    else:
        _ok("Sin errores semánticos.")
        print()


# ---------------------------------------------------------------------------
# Subclase de Interprete con presentación mejorada para consola
# ---------------------------------------------------------------------------

class InterpreteLoreConsola(Interprete):
    """
    Extiende Interprete para ofrecer una experiencia de consola más pulida.
    Sobreescribe solo los métodos de presentación; la lógica no cambia.
    """

    def _mostrar_encabezado_escena(self, nombre: str) -> None:
        """Muestra la escena actual dentro de un marco visual."""
        interior = _ANCHO - 4
        etiqueta = f"ESCENA: {nombre.upper()}"
        print()
        print("╔" + "═" * (_ANCHO - 2) + "╗")
        print(f"║  {etiqueta:<{interior}}║")
        print("╚" + "═" * (_ANCHO - 2) + "╝")

    def _mostrar_texto(self, texto: str) -> None:
        """Muestra el texto narrativo con sangría."""
        print(f"\n  {texto}")

    def _mostrar_opciones(self, opciones) -> None:
        """Muestra las opciones numeradas dentro de un bloque visual."""
        print()
        print("  " + "─" * (_ANCHO - 4))
        print("  ¿Qué decides hacer?")
        print("  " + "─" * (_ANCHO - 4))
        for i, op in enumerate(opciones, 1):
            etiqueta = op.etiqueta[1:-1]   # quitar comillas
            print(f"    [{i}]  {etiqueta}")
        print("  " + "─" * (_ANCHO - 4))

    def _leer_opcion(self, n: int) -> int:
        """
        Lee la elección del jugador con validación completa.
        Maneja Ctrl+C y EOF limpiamente.
        """
        if self._modo_test:
            resp = self._cola_test.popleft() if self._cola_test else "1"
            print(f"  [TEST] Respuesta automática: {resp}")
            try:
                eleccion = int(resp)
                if 1 <= eleccion <= n:
                    return eleccion
            except ValueError:
                pass
            return 1

        while True:
            try:
                raw = input(f"\n  Tu elección (1-{n}): ").strip()
                eleccion = int(raw)
                if 1 <= eleccion <= n:
                    return eleccion
                print(f"  Por favor elige un número entre 1 y {n}.")
            except ValueError:
                print("  Escribe el número de tu elección.")
            except (EOFError, KeyboardInterrupt):
                print("\n\n  Juego interrumpido por el usuario.")
                sys.exit(0)

    def _mostrar_fin(self) -> None:
        """Muestra el mensaje de cierre del juego."""
        interior = _ANCHO - 4
        print()
        print("╔" + "═" * (_ANCHO - 2) + "╗")
        print(f"║  {'FIN DE LA AVENTURA':<{interior}}║")
        print(f"║  {'¡Gracias por jugar!':<{interior}}║")
        print("╚" + "═" * (_ANCHO - 2) + "╝")
        print()

    def _mostrar_error(self, mensaje: str) -> None:
        """Muestra un error de ejecución con formato destacado."""
        print()
        _err(f"ERROR DE EJECUCIÓN: {mensaje}")
        print()


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run_pipeline(fuente: str, nombre_archivo: str = "<fuente>") -> bool:
    """
    Ejecuta el pipeline completo: lex → parse → sem → interp.

    Muestra los resultados de cada fase con separadores visuales.
    Retorna True si la ejecución se completó sin errores fatales.
    """
    print()
    _caja(f"LoreEngine  ─  {nombre_archivo}")

    # ── Fase 1: Léxico ───────────────────────────────────────────────────────
    tokens, errs_lex = lex_analizar(fuente)
    _mostrar_fase_lexico(tokens, errs_lex)

    if errs_lex:
        _warn("Se encontraron errores léxicos.")
        _warn("El análisis continúa con los tokens válidos.\n")

    # ── Fase 2: Sintáctico ───────────────────────────────────────────────────
    parser = Parser(tokens)
    ast, errs_sin, advertencias = parser.parsear()
    _mostrar_fase_sintactico(ast, errs_sin, advertencias)

    hay_fatal = any(e.fatal for e in errs_sin) if errs_sin else False
    if hay_fatal:
        _err("Error(es) fatal(es) en la fase sintáctica. No se puede continuar.\n")
        return False

    if errs_sin:
        _warn("Se encontraron errores sintácticos recuperables.")
        _warn("El análisis continúa con el AST parcial.\n")

    # ── Fase 3: Semántico ────────────────────────────────────────────────────
    semantico = AnalizadorSemantico()
    tabla, errs_sem = semantico.analizar(ast)
    _mostrar_fase_semantico(tabla, errs_sem)

    if errs_sem:
        _err("Error(es) semántico(s) detectados. No se puede ejecutar.\n")
        return False

    # ── Fase 4: Ejecución ────────────────────────────────────────────────────
    _titulo_fase(4, "EJECUCIÓN")
    print()

    interp = InterpreteLoreConsola(ast)
    interp.ejecutar()

    return True


# ---------------------------------------------------------------------------
# Historia de ejemplo integrada
# ---------------------------------------------------------------------------

_EJEMPLO_INTEGRADO = """\
personaje heroe {
    vida   = 100
    oro    = 50
    fuerza = 20
}

escena inicio {
    mostrar "Te despiertas en una posada al amanecer."
    mostrar "El posadero te mira con expresion seria."
    mostrar "Al sur esta el bosque. Al norte, la montana."
    decision {
        "Explorar el bosque oscuro" -> bosque
        "Subir la montana nevada"   -> montana
    }
}

escena bosque {
    mostrar "El bosque es denso y silencioso."
    si vida > 80 {
        mostrar "Te sientes fuerte. Avanzas sin miedo."
    } sino {
        mostrar "Estas herido. Cada paso es un esfuerzo."
    }
    vida   = vida - 15
    fuerza = fuerza + 5
    mostrar "Encuentras un cofre enterrado entre las raices."
    mostrar "Dentro hay monedas de oro relucientes."
    oro = oro + 30
    decision {
        "Volver a la posada"   -> final
        "Explorar mas adentro" -> final
    }
}

escena montana {
    mostrar "El viento frio muerde tus mejillas."
    mostrar "En la cumbre hay un templo abandonado."
    vida   = vida - 10
    fuerza = fuerza + 10
    oro    = oro + 20
    mostrar "Encuentras un altar con monedas de plata."
    decision {
        "Tomar las monedas y bajar" -> final
        "Meditar ante el altar"     -> final
    }
}

escena final {
    mostrar "Regresas a la posada con nuevas historias."
    mostrar "Los aldeanos escuchan tus aventuras con asombro."
    si oro > 70 {
        mostrar "Eres rico. La gente te llama el Aventurero de Oro."
    } sino {
        mostrar "Tus hazanas valen mas que el oro."
    }
    mostrar "Fin de esta aventura. Hasta la proxima, heroe."
}
"""


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    """Punto de entrada principal del modo consola."""
    if len(sys.argv) >= 2:
        # Modo archivo: python main_consola.py historia.lore
        ruta = sys.argv[1]
        if not os.path.isfile(ruta):
            print(f"\n  ✗  Archivo no encontrado: {ruta!r}")
            sys.exit(1)
        try:
            with open(ruta, encoding="utf-8") as f:
                fuente = f.read()
        except OSError as exc:
            print(f"\n  ✗  No se pudo leer '{ruta}': {exc}")
            sys.exit(1)
        nombre = os.path.basename(ruta)
    else:
        # Modo ejemplo integrado
        print()
        print("  (No se pasó ningún archivo. Ejecutando el ejemplo integrado.)")
        print("  Uso: python main_consola.py historia.lore")
        fuente = _EJEMPLO_INTEGRADO
        nombre = "ejemplo_integrado.lore"

    try:
        run_pipeline(fuente, nombre)
    except KeyboardInterrupt:
        print("\n\n  Juego interrumpido por el usuario.")
        sys.exit(0)


if __name__ == "__main__":
    main()
