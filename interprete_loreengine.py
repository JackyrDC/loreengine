# =============================================================================
# interprete_loreengine.py — Intérprete del AST de LoreEngine
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Diseño:
#   El intérprete recorre el AST y ejecuta cada nodo directamente.
#   No depende del analizador semántico en tiempo de ejecución; asume que el
#   programa ya fue validado. Gestiona errores en tiempo de ejecución con
#   ErrorEjecucion (no son errores de compilación).
#
# Entorno de ejecución (Entorno):
#   Estructura padre/hijo con cadena de búsqueda. Los atributos del personaje
#   se cargan en el entorno global al inicio. Las asignaciones dentro de
#   escenas modifican el valor en el entorno donde fue definida la variable.
#
# Control de flujo entre escenas:
#   La señal _SenalSalto (excepción interna) es lanzada por _ejecutar_decision()
#   y capturada por el bucle principal de ejecutar(). Permite que una decisión
#   interrumpa el resto de la escena actual y salte a la siguiente.
#
# Separación presentación / lógica:
#   TODOS los métodos de salida y entrada están en una sección claramente
#   marcada y son sobreescribibles por la GUI sin tocar la lógica de ejecución.
#   La GUI hereda Interprete y sobreescribe solo esos métodos.
#
# modo_test:
#   Deshabilita el input() y consume respuestas desde una cola predefinida.
#   Útil para pruebas automáticas sin intervención del usuario.
# =============================================================================

import sys
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, Deque, List, Optional

from ast_nodes import (
    NodoAST, NodoPrograma, NodoPersonaje, NodoAtributo,
    NodoEscena, NodoMostrar, NodoAsignacion, NodoAsignAtrib,
    NodoDecision, NodoOpcion, NodoSi, NodoCondicion, NodoBinario,
    NodoEntero, NodoIdentificador, NodoAtribPersonaje, NodoDado,
    NodoErrorExpr,
)


# ---------------------------------------------------------------------------
# Error de ejecución
# ---------------------------------------------------------------------------

@dataclass
class ErrorEjecucion(Exception):
    """
    Error detectado durante la ejecución del programa.
    No es un error de compilación: ocurre en tiempo de ejecución.
    """
    mensaje: str
    linea:   int

    def __str__(self) -> str:
        return f"[ERROR DE EJECUCIÓN] línea {self.linea}: {self.mensaje}"


# ---------------------------------------------------------------------------
# Señal interna de salto entre escenas (no es un error)
# ---------------------------------------------------------------------------

class _SenalSalto(Exception):
    """
    Señal de control lanzada por _ejecutar_decision() para indicar que
    la ejecución debe continuar en otra escena. No representa un error.
    """
    def __init__(self, destino: str):
        self.destino = destino


# ---------------------------------------------------------------------------
# Entorno de ejecución (runtime)
# ---------------------------------------------------------------------------

class Entorno:
    """
    Almacena los valores de las variables en tiempo de ejecución.
    Implementa una cadena de entornos padre/hijo para scoping.

    En LoreEngine:
      - El entorno global contiene los atributos del personaje.
      - No se crea entorno hijo por escena (las asignaciones modifican global).
      - La arquitectura está lista para futuros scopes locales.
    """

    def __init__(self, padre: Optional['Entorno'] = None):
        self._valores: Dict[str, int] = {}
        self._padre   = padre

    # ── Definición (crea en el scope actual) ─────────────────────────────

    def definir(self, nombre: str, valor: int) -> None:
        """Crea una nueva variable en ESTE entorno."""
        self._valores[nombre] = valor

    # ── Asignación (actualiza en el scope donde se definió) ───────────────

    def asignar(self, nombre: str, valor: int) -> bool:
        """
        Actualiza el valor de una variable existente.
        Busca desde el scope actual hacia el padre (cadena).
        Retorna False si la variable no existe en ningún scope.
        """
        if nombre in self._valores:
            self._valores[nombre] = valor
            return True
        if self._padre is not None:
            return self._padre.asignar(nombre, valor)
        return False

    def asignar_o_definir(self, nombre: str, valor: int) -> None:
        """
        Asigna si existe en algún scope; define en el actual si no existe.
        Usado por sent_asignacion en escenas para compatibilidad.
        """
        if not self.asignar(nombre, valor):
            self.definir(nombre, valor)

    # ── Lectura ───────────────────────────────────────────────────────────

    def obtener(self, nombre: str, linea: int = 0) -> int:
        """
        Retorna el valor de la variable. Lanza ErrorEjecucion si no existe.
        """
        if nombre in self._valores:
            return self._valores[nombre]
        if self._padre is not None:
            return self._padre.obtener(nombre, linea)
        raise ErrorEjecucion(
            f"Variable '{nombre}' no definida en tiempo de ejecución", linea
        )

    def tiene(self, nombre: str) -> bool:
        """True si la variable existe en este scope o en algún padre."""
        if nombre in self._valores:
            return True
        return self._padre.tiene(nombre) if self._padre else False

    # ── Inspección ────────────────────────────────────────────────────────

    def valores_actuales(self) -> Dict[str, int]:
        """Retorna una copia plana de todos los valores visibles."""
        resultado: Dict[str, int] = {}
        if self._padre:
            resultado.update(self._padre.valores_actuales())
        resultado.update(self._valores)  # los locales sobreescriben
        return resultado


# ---------------------------------------------------------------------------
# Intérprete principal
# ---------------------------------------------------------------------------

class Interprete:
    """
    Ejecuta un NodoPrograma ya validado semánticamente.

    Uso básico:
        interp = Interprete(ast)
        interp.ejecutar()

    Modo test (sin input()):
        interp = Interprete(ast, modo_test=True, respuestas_test=["1","2"])
        interp.ejecutar()

    Extensión para GUI:
        class InterpreteGUI(Interprete):
            def _mostrar_texto(self, texto): ...
            def _leer_opcion(self, n): ...
    """

    def __init__(self, ast: NodoPrograma,
                 modo_test: bool = False,
                 respuestas_test: Optional[List[str]] = None):
        self._ast       = ast
        self._modo_test = modo_test
        self._cola_test: Deque[str] = deque(respuestas_test or [])

        # Índices de personajes y escenas (nombre → nodo)
        self._personajes: Dict[str, NodoPersonaje] = {}
        self._escenas:    Dict[str, NodoEscena]    = {}

        # Un entorno por personaje (nombre → Entorno con sus atributos)
        self._entornos: Dict[str, Entorno] = {}

        # Entorno global de ejecución — apuntará al entorno del primer personaje
        # (retro-compatibilidad: referencias bare como 'vida' siguen funcionando)
        self._entorno = Entorno()

        # Nombre del personaje principal (rol="principal", o el primero si no hay)
        self._nombre_personaje: str = ""

        # Nombre de la escena que se está ejecutando actualmente
        self._escena_actual: str = ""

    # -----------------------------------------------------------------------
    # Carga del programa
    # -----------------------------------------------------------------------

    def _cargar_programa(self) -> None:
        """
        Pasada de inicialización:
          1. Indexa todos los NodoPersonaje y NodoEscena por nombre.
          2. Crea un Entorno independiente por cada personaje y carga
             sus atributos. El entorno del primer personaje (héroe) se
             asigna también a self._entorno para retro-compatibilidad
             con referencias bare (vida, oro, fuerza).
        """
        # Pasada 1 — indexar; determinar personaje principal
        primer_declarado = ""
        for decl in self._ast.declaraciones:
            if isinstance(decl, NodoPersonaje):
                self._personajes[decl.nombre] = decl
                if not primer_declarado:
                    primer_declarado = decl.nombre
                if decl.rol == "principal":
                    self._nombre_personaje = decl.nombre
            elif isinstance(decl, NodoEscena):
                self._escenas[decl.nombre] = decl

        # Si ninguno tiene rol="principal", usar el primero declarado
        if not self._nombre_personaje:
            self._nombre_personaje = primer_declarado

        # Pasada 2 — crear entorno por personaje y cargar sus atributos
        for personaje in self._personajes.values():
            env = Entorno()
            self._entornos[personaje.nombre] = env
            # Evaluamos usando este env (por si un atributo referencia otro
            # del mismo personaje). Intercambiamos temporalmente self._entorno.
            entorno_previo = self._entorno
            self._entorno = env
            for attr in personaje.atributos:
                try:
                    valor = self._evaluar(attr.valor)
                except ErrorEjecucion:
                    valor = 0
                env.definir(attr.nombre, valor)
            self._entorno = entorno_previo

        # El entorno del principal es el entorno global para referencias bare.
        if self._nombre_personaje and self._nombre_personaje in self._entornos:
            self._entorno = self._entornos[self._nombre_personaje]

    # -----------------------------------------------------------------------
    # Ejecución principal
    # -----------------------------------------------------------------------

    def ejecutar(self) -> None:
        """
        Arranca la ejecución desde la primera escena declarada y continúa
        hasta que no haya más escenas o el programa termine normalmente.
        """
        self._cargar_programa()

        if not self._escenas:
            self._mostrar_error("No hay escenas declaradas en el programa.")
            return

        # La primera escena es la primera declarada en el fuente
        nombre_siguiente = next(iter(self._escenas))

        while nombre_siguiente:
            if nombre_siguiente not in self._escenas:
                self._mostrar_error(
                    f"Escena '{nombre_siguiente}' no encontrada. "
                    f"Escenas disponibles: {list(self._escenas.keys())}"
                )
                break

            self._escena_actual = nombre_siguiente

            try:
                self._ejecutar_escena(self._escenas[nombre_siguiente])
                nombre_siguiente = None   # terminó normalmente: fin del juego

            except _SenalSalto as salto:
                nombre_siguiente = salto.destino   # saltar a la nueva escena

            except ErrorEjecucion as err:
                self._mostrar_error(str(err))
                break

        self._mostrar_fin()

    # -----------------------------------------------------------------------
    # Ejecución de escena
    # -----------------------------------------------------------------------

    def _ejecutar_escena(self, nodo: NodoEscena) -> None:
        """
        Procesa todas las sentencias de una escena en orden.
        Si alguna sentencia lanza _SenalSalto, se propaga hacia ejecutar().
        """
        self._mostrar_encabezado_escena(nodo.nombre)
        self._mostrar_panel_personaje()

        for sent in nodo.sentencias:
            self._ejecutar_sentencia(sent)
            # _SenalSalto se propaga automáticamente desde _ejecutar_decision()

    # -----------------------------------------------------------------------
    # Despacho de sentencias
    # -----------------------------------------------------------------------

    def _ejecutar_sentencia(self, nodo: NodoAST) -> None:
        """Despacha la ejecución según el tipo de sentencia."""
        if isinstance(nodo, NodoMostrar):
            self._ejecutar_mostrar(nodo)

        elif isinstance(nodo, NodoAsignacion):
            self._ejecutar_asignacion(nodo)

        elif isinstance(nodo, NodoAsignAtrib):
            self._ejecutar_asignacion_atrib(nodo)

        elif isinstance(nodo, NodoDecision):
            self._ejecutar_decision(nodo)   # puede lanzar _SenalSalto

        elif isinstance(nodo, NodoSi):
            self._ejecutar_si(nodo)

        elif isinstance(nodo, NodoErrorExpr):
            # Nodo centinela del parser: advertir y omitir
            self._mostrar_advertencia(
                f"Sentencia inválida en línea {nodo.linea} (ignorada)"
            )

    # ── mostrar ──────────────────────────────────────────────────────────

    def _ejecutar_mostrar(self, nodo: NodoMostrar) -> None:
        """Muestra el texto de la cadena (sin las comillas del fuente)."""
        texto = nodo.cadena[1:-1]   # quitar comillas delimitadoras
        self._mostrar_texto(texto)

    # ── asignacion ───────────────────────────────────────────────────────

    def _ejecutar_asignacion(self, nodo: NodoAsignacion) -> None:
        """
        Evalúa la expresión y actualiza la variable en el entorno.
        Usa asignar_o_definir para compatibilidad con variables aún no
        declaradas explícitamente (extensiones futuras del lenguaje).
        """
        valor = self._evaluar(nodo.expresion)
        self._entorno.asignar_o_definir(nodo.nombre, valor)
        # Actualizar panel de stats tras cada cambio en un atributo
        self._on_variable_cambiada(nodo.nombre, valor)

    # ── asignacion_atrib (dot-notation) ──────────────────────────────────

    def _ejecutar_asignacion_atrib(self, nodo: NodoAsignAtrib) -> None:
        """
        Evalúa la expresión y actualiza el atributo del personaje indicado
        en su entorno propio. Notifica el cambio via _on_variable_cambiada.
        """
        env = self._entornos.get(nodo.personaje)
        if env is None:
            raise ErrorEjecucion(
                f"Personaje '{nodo.personaje}' no encontrado en tiempo de "
                f"ejecución (entornos: {list(self._entornos.keys())})",
                nodo.linea,
            )
        valor = self._evaluar(nodo.expresion)
        env.asignar_o_definir(nodo.atributo, valor)
        self._on_variable_cambiada(nodo.atributo, valor, personaje=nodo.personaje)

    # ── decision ─────────────────────────────────────────────────────────

    def _ejecutar_decision(self, nodo: NodoDecision) -> None:
        """
        Muestra las opciones al jugador, lee su elección y lanza _SenalSalto
        hacia la escena destino. Las sentencias posteriores en la escena actual
        no se ejecutan (el salto las interrumpe).
        """
        self._mostrar_opciones(nodo.opciones)
        eleccion = self._leer_opcion(len(nodo.opciones))
        opcion   = nodo.opciones[eleccion - 1]
        raise _SenalSalto(opcion.destino)

    # ── si / sino ────────────────────────────────────────────────────────

    def _ejecutar_si(self, nodo: NodoSi) -> None:
        """Evalúa la condición y ejecuta la rama correspondiente."""
        if self._evaluar_condicion(nodo.condicion):
            for sent in nodo.cuerpo_si:
                self._ejecutar_sentencia(sent)
        else:
            for sent in nodo.cuerpo_sino:
                self._ejecutar_sentencia(sent)

    # -----------------------------------------------------------------------
    # Evaluación de expresiones aritméticas
    # -----------------------------------------------------------------------

    def _evaluar(self, nodo: NodoAST) -> int:
        """
        Evalúa una expresión y retorna su valor entero.
        Lanza ErrorEjecucion si la expresión no es evaluable.
        """
        if isinstance(nodo, NodoEntero):
            return nodo.valor

        elif isinstance(nodo, NodoIdentificador):
            return self._entorno.obtener(nodo.nombre, nodo.linea)

        elif isinstance(nodo, NodoBinario):
            izq = self._evaluar(nodo.izquierda)
            der = self._evaluar(nodo.derecha)
            op  = nodo.operador

            if op == '+':
                return izq + der
            elif op == '-':
                return izq - der
            elif op == '*':
                return izq * der
            elif op == '/':
                if der == 0:
                    raise ErrorEjecucion(
                        "División por cero", nodo.linea
                    )
                return izq // der   # LoreEngine usa división entera

        elif isinstance(nodo, NodoDado):
            n = self._evaluar(nodo.argumento)
            if n <= 0:
                raise ErrorEjecucion(
                    f"dado() requiere un valor positivo; se recibió {n}",
                    nodo.linea,
                )
            return random.randint(1, n)

        elif isinstance(nodo, NodoAtribPersonaje):
            env = self._entornos.get(nodo.personaje)
            if env is None:
                raise ErrorEjecucion(
                    f"Personaje '{nodo.personaje}' no encontrado en tiempo "
                    f"de ejecución",
                    nodo.linea,
                )
            return env.obtener(nodo.atributo, nodo.linea)

        elif isinstance(nodo, NodoErrorExpr):
            raise ErrorEjecucion(
                "Expresión inválida heredada del análisis sintáctico",
                nodo.linea,
            )

        raise ErrorEjecucion(
            f"Tipo de nodo no evaluable: {type(nodo).__name__}",
            getattr(nodo, "linea", 0),
        )

    # -----------------------------------------------------------------------
    # Evaluación de condiciones relacionales
    # -----------------------------------------------------------------------

    def _evaluar_condicion(self, nodo: NodoAST) -> bool:
        """
        Evalúa una condición relacional y retorna True o False.
        Lanza ErrorEjecucion si la condición no es evaluable.
        """
        if isinstance(nodo, NodoCondicion):
            izq = self._evaluar(nodo.izquierda)
            der = self._evaluar(nodo.derecha)
            op  = nodo.operador

            if op == '==': return izq == der
            if op == '!=': return izq != der
            if op == '>':  return izq >  der
            if op == '<':  return izq <  der
            if op == '>=': return izq >= der
            if op == '<=': return izq <= der

        elif isinstance(nodo, NodoErrorExpr):
            raise ErrorEjecucion(
                "Condición inválida heredada del análisis sintáctico",
                nodo.linea,
            )

        raise ErrorEjecucion(
            f"Condición no evaluable: {type(nodo).__name__}",
            getattr(nodo, "linea", 0),
        )

    # =======================================================================
    # MÉTODOS DE PRESENTACIÓN — sobreescribibles por la GUI
    # =======================================================================
    #
    # La GUI hereda Interprete y sobreescribe estos métodos.
    # La lógica de ejecución (todo lo de arriba) nunca se modifica.
    # =======================================================================

    def _mostrar_texto(self, texto: str) -> None:
        """Muestra texto narrativo al jugador."""
        print(f"\n  {texto}")

    def _mostrar_encabezado_escena(self, nombre: str) -> None:
        """Muestra el nombre de la escena actual como separador visual."""
        ancho = 52
        print("\n" + "═" * ancho)
        print(f"  Escena: {nombre.upper()}")
        print("═" * ancho)

    def _mostrar_panel_personaje(self) -> None:
        """
        Muestra el panel de estadísticas del personaje activo.
        La GUI lo sobreescribe con barras de progreso en tiempo real.
        """
        if not self._nombre_personaje:
            return
        personaje = self._personajes.get(self._nombre_personaje)
        if not personaje:
            return

        nombre = self._nombre_personaje.upper()
        # Iconos predeterminados por nombre de atributo
        _ICONOS = {
            "vida":    "❤ ",
            "oro":     "🪙",
            "fuerza":  "⚔ ",
            "magia":   "✨",
            "defensa": "🛡",
            "agilidad":"💨",
        }
        print()
        print("  ┌─────────────────────────────┐")
        print(f"  │ PERSONAJE: {nombre:<18}│")
        for attr in personaje.atributos:
            icono = _ICONOS.get(attr.nombre, "◆ ")
            try:
                valor = self._entorno.obtener(attr.nombre)
            except ErrorEjecucion:
                valor = "?"
            print(f"  │  {icono} {attr.nombre:<10}: {str(valor):>5}         │")
        print("  └─────────────────────────────┘")

    def _mostrar_opciones(self, opciones: List[NodoOpcion]) -> None:
        """Muestra las opciones numeradas de un bloque decision."""
        print("\n  ¿Qué decides hacer?\n")
        for i, op in enumerate(opciones, 1):
            etiqueta = op.etiqueta[1:-1]   # quitar comillas
            print(f"    [{i}] {etiqueta}")
        print()

    def _leer_opcion(self, n: int) -> int:
        """
        Lee la elección del jugador (número entre 1 y n).
        En modo_test consume de la cola de respuestas.
        La GUI sobreescribe esto para esperar un clic de botón.
        """
        if self._modo_test:
            resp = self._cola_test.popleft() if self._cola_test else "1"
            print(f"  [TEST] Respuesta automática: {resp}")
            eleccion = int(resp)
            if 1 <= eleccion <= n:
                return eleccion
            return 1   # fallback seguro

        while True:
            try:
                raw      = input("  Tu elección: ").strip()
                eleccion = int(raw)
                if 1 <= eleccion <= n:
                    return eleccion
                print(f"  Por favor elige entre 1 y {n}.")
            except ValueError:
                print("  Escribe el número de tu elección.")
            except EOFError:
                return 1

    def _on_variable_cambiada(self, nombre: str, valor: int,
                              personaje: str = "") -> None:
        """
        Callback llamado después de cada asignación.
        'personaje' identifica a quién pertenece el atributo:
          - "" o nombre del héroe → atributo del héroe (bare reference)
          - nombre de NPC         → atributo de ese personaje (dot-notation)
        La GUI sobreescribe esto para actualizar barras en tiempo real.
        """
        pass   # en consola no se necesita; la GUI lo sobreescribe

    def _mostrar_fin(self) -> None:
        """Muestra el mensaje de fin del juego."""
        print("\n" + "═" * 52)
        print("  Fin de la aventura. ¡Gracias por jugar!")
        print("═" * 52 + "\n")

    def _mostrar_error(self, mensaje: str) -> None:
        """Muestra un error de ejecución."""
        print(f"\n  !! ERROR: {mensaje}\n")

    def _mostrar_advertencia(self, mensaje: str) -> None:
        """Muestra una advertencia sin interrumpir la ejecución."""
        print(f"\n  [!] Advertencia: {mensaje}\n")


# ---------------------------------------------------------------------------
# Función auxiliar para uso externo (pipeline completo)
# ---------------------------------------------------------------------------

def ejecutar_fuente(fuente: str,
                    modo_test: bool = False,
                    respuestas_test: Optional[List[str]] = None) -> Interprete:
    """
    Pipeline completo: lex → parse → semántico → interpretar.
    Retorna el intérprete tras la ejecución (para inspección en tests).
    """
    from lexer_loreengine  import analizar as lex_analizar
    from parser_loreengine import Parser
    from semantico_loreengine import AnalizadorSemantico

    tokens, errs_lex = lex_analizar(fuente)
    if errs_lex:
        print(f"  {len(errs_lex)} error(es) léxico(s). Abortando.")
        for e in errs_lex:
            print(f"  {e}")
        return None

    parser = Parser(tokens)
    ast, errs_sin, _ = parser.parsear()
    if errs_sin:
        print(f"  {len(errs_sin)} error(es) sintáctico(s). Abortando.")
        for e in errs_sin:
            print(f"  {e}")
        return None

    semantico = AnalizadorSemantico()
    _, errs_sem = semantico.analizar(ast)
    if errs_sem:
        print(f"  {len(errs_sem)} error(es) semántico(s). Abortando.")
        for e in errs_sem:
            print(f"  {e}")
        return None

    interp = Interprete(ast, modo_test=modo_test,
                        respuestas_test=respuestas_test)
    interp.ejecutar()
    return interp


# ---------------------------------------------------------------------------
# Bloque __main__: pruebas autocontenidas
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Prueba 1: historia completa con decisión ────────────────────────
    HISTORIA_1 = """\
personaje heroe {
    vida   = 100
    oro    = 50
    fuerza = 20
}

escena inicio {
    mostrar "Estás en un bosque oscuro."
    mostrar "El viento susurra entre los árboles."
    decision {
        "Explorar el bosque" -> bosque
        "Regresar al pueblo" -> pueblo
    }
}

escena bosque {
    mostrar "Te adentras en el bosque."
    si vida > 50 {
        mostrar "Te sientes fuerte. Continúas."
    } sino {
        mostrar "Estás herido. Debes tener cuidado."
    }
    vida = vida - 20
    oro  = oro + (fuerza * 2)
    mostrar "Encuentras un cofre con monedas."
    decision {
        "Volver al inicio" -> inicio
        "Ir al pueblo"     -> pueblo
    }
}

escena pueblo {
    mostrar "Llegas al pueblo sano y salvo."
    mostrar "Los aldeanos te reciben con alegría."
}
"""

    print("=" * 60)
    print(" PRUEBA 1 — Historia completa con decisión (modo_test)")
    print("=" * 60)
    # Ruta: inicio → bosque → pueblo (respuestas: 1 para bosque, 2 para pueblo)
    interp1 = ejecutar_fuente(
        HISTORIA_1,
        modo_test=True,
        respuestas_test=["1", "2"],
    )
    if interp1:
        print(f"\n  Estado final del entorno:")
        for nombre, valor in interp1._entorno.valores_actuales().items():
            print(f"    {nombre} = {valor}")
        print()

    # ── Prueba 2: condicional que cambia según atributo ──────────────────
    HISTORIA_2 = """\
personaje guerrero {
    vida   = 30
    fuerza = 15
}

escena batalla {
    mostrar "El enemigo ataca."
    vida = vida - 25
    si vida > 0 {
        mostrar "¡Sobrevives al ataque!"
    } sino {
        mostrar "Has caído en combate."
    }
}
"""

    print("=" * 60)
    print(" PRUEBA 2 — Condicional con atributo modificado")
    print("=" * 60)
    interp2 = ejecutar_fuente(HISTORIA_2, modo_test=True)
    if interp2:
        print(f"  vida final: {interp2._entorno.obtener('vida')}\n")

    # ── Prueba 3: Entorno — cadena padre/hijo ────────────────────────────
    print("=" * 60)
    print(" PRUEBA 3 — Entorno: cadena padre/hijo")
    print("=" * 60)
    global_env = Entorno()
    global_env.definir("vida", 100)
    global_env.definir("oro",  50)

    local_env = Entorno(padre=global_env)
    local_env.definir("bonus", 10)

    print(f"  local.obtener('vida')   = {local_env.obtener('vida')}")
    print(f"  local.obtener('bonus')  = {local_env.obtener('bonus')}")
    print(f"  local.obtener('oro')    = {local_env.obtener('oro')}")

    local_env.asignar("vida", 75)   # modifica en el padre
    print(f"  tras asignar vida=75 en local:")
    print(f"    global.obtener('vida') = {global_env.obtener('vida')}")

    print(f"\n  valores_actuales() desde local:")
    for k, v in local_env.valores_actuales().items():
        print(f"    {k} = {v}")
    print()

    # ── Prueba 4: modo_test con múltiples escenas ────────────────────────
    HISTORIA_4 = """\
personaje aventurero {
    vida = 100
    oro  = 0
}

escena inicio {
    mostrar "Aventura comienza."
    decision {
        "Ir a la mina"    -> mina
        "Ir al mercado"   -> mercado
    }
}

escena mina {
    oro = oro + 30
    mostrar "Encontraste 30 monedas en la mina."
    decision {
        "Ir al mercado" -> mercado
    }
}

escena mercado {
    mostrar "Gastas tus monedas en suministros."
    oro = oro - 10
}
"""

    print("=" * 60)
    print(" PRUEBA 4 — Ruta: inicio → mina → mercado")
    print("=" * 60)
    interp4 = ejecutar_fuente(
        HISTORIA_4,
        modo_test=True,
        respuestas_test=["1", "1"],
    )
    if interp4:
        print(f"\n  Estado final: "
              f"vida={interp4._entorno.obtener('vida')}  "
              f"oro={interp4._entorno.obtener('oro')}\n")
