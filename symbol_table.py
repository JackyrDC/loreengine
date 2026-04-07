# =============================================================================
# symbol_table.py — Tabla de Símbolos de LoreEngine
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Diseño: pila de ámbitos (scope stack).
#   - La base de la pila es siempre el ámbito "global".
#   - Al entrar a una escena se empuja un nuevo scope con su nombre.
#   - Al salir de la escena se hace pop del scope local.
#   - buscar() recorre la pila de arriba (local) hacia abajo (global),
#     respetando el principio de que lo local sombrea lo global.
#
# Tipos de símbolo en LoreEngine:
#   PERSONAJE  — declarado con 'personaje nombre { ... }'
#   ESCENA     — declarado con 'escena nombre { ... }'
#   ATRIBUTO   — declarado dentro del bloque de un personaje
#   VARIABLE   — asignación dentro de una escena
#   FUNCION    — función integrada del lenguaje (ej: dado)
#
# Cada entrada de la tabla guarda:
#   nombre      — identificador tal como aparece en el fuente
#   tipo        — uno de los cinco tipos anteriores
#   ambito      — nombre del scope donde fue declarado ("global" o escena)
#   linea       — línea del fuente donde se declaró (0 = built-in)
#   propietario — para ATRIBUTO: nombre del personaje al que pertenece
#   tipo_dato   — tipo del valor almacenado ("ENTERO", "CADENA", "NINGUNO")
#   valor       — valor actual del símbolo (para ATRIBUTO y VARIABLE)
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Entrada de la tabla de símbolos
# ---------------------------------------------------------------------------

@dataclass
class Simbolo:
    """
    Representa una entrada de la tabla de símbolos.

    Campos:
        nombre      — identificador del símbolo
        tipo        — PERSONAJE | ESCENA | ATRIBUTO | VARIABLE | FUNCION
        ambito      — scope donde fue declarado ("global" o nombre de escena)
        linea       — línea del fuente (0 para built-ins)
        propietario — nombre del personaje dueño (solo para ATRIBUTO)
        tipo_dato   — tipo del valor: "ENTERO" | "CADENA" | "NINGUNO"
        valor       — valor actual del símbolo (ATRIBUTO y VARIABLE)
    """
    nombre:      str
    tipo:        str            # "PERSONAJE"|"ESCENA"|"ATRIBUTO"|"VARIABLE"|"FUNCION"
    ambito:      str            # "global" o nombre de la escena activa
    linea:       int            # 0 = símbolo built-in del lenguaje
    propietario: str  = ""      # solo para ATRIBUTO
    tipo_dato:   str  = "ENTERO"  # tipo del valor almacenado
    valor:       int  = 0       # valor actual (ATRIBUTO / VARIABLE)

    def __repr__(self) -> str:
        prop = f", propietario={self.propietario!r}" if self.propietario else ""
        return (
            f"Simbolo({self.nombre!r}, tipo={self.tipo!r}, "
            f"tipo_dato={self.tipo_dato!r}, valor={self.valor}, "
            f"ámbito={self.ambito!r}, línea={self.linea}{prop})"
        )


# ---------------------------------------------------------------------------
# Clase principal: TablaSimbolos
# ---------------------------------------------------------------------------

class TablaSimbolos:
    """
    Tabla de símbolos con pila de ámbitos para LoreEngine.

    Uso típico:
        ts = TablaSimbolos()

        # Registrar declaraciones globales
        ts.declarar("heroe", "PERSONAJE", linea=1)
        ts.declarar("vida",  "ATRIBUTO",  linea=2, propietario="heroe", valor=100)
        ts.declarar("inicio","ESCENA",    linea=7)

        # Entrar a una escena
        ts.entrar_ambito("inicio")
        ts.declarar("vida", "VARIABLE", linea=24, valor=80)

        # Buscar y actualizar valor
        sim = ts.buscar("vida")           # retorna el VARIABLE local primero
        ts.actualizar_valor("vida", 90)   # actualiza el valor en el scope actual

        # Salir de la escena
        ts.salir_ambito()

    Al crear la tabla se registran automáticamente las funciones built-in
    del lenguaje (dado) en el scope global con tipo FUNCION.
    """

    def __init__(self):
        # Pila de (nombre_ambito, dict[nombre → Simbolo])
        # El primer elemento es siempre el scope global.
        self._pila: List[tuple] = [("global", {})]

        # Registrar funciones built-in del lenguaje
        self._registrar_builtins()

    # -----------------------------------------------------------------------
    # Registro de funciones integradas
    # -----------------------------------------------------------------------

    def _registrar_builtins(self) -> None:
        """
        Registra las funciones integradas (built-in) del lenguaje en el
        scope global con linea=0 para indicar que son pre-definidas.
        """
        _, scope_global = self._pila[0]
        # dado(n): retorna un entero aleatorio entre 1 y n
        scope_global["dado"] = Simbolo(
            nombre="dado",
            tipo="FUNCION",
            ambito="global",
            linea=0,
            tipo_dato="ENTERO",
        )

    # -----------------------------------------------------------------------
    # Gestión de ámbitos
    # -----------------------------------------------------------------------

    def entrar_ambito(self, nombre: str) -> None:
        """
        Empuja un nuevo scope en la pila. Se llama al comenzar a analizar
        el cuerpo de una escena (o bloque si se extiende el lenguaje).
        """
        self._pila.append((nombre, {}))

    def salir_ambito(self) -> None:
        """
        Saca el scope actual de la pila. No se puede salir del scope global.
        """
        if len(self._pila) > 1:
            self._pila.pop()

    @property
    def ambito_actual(self) -> str:
        """Retorna el nombre del ámbito actualmente activo."""
        return self._pila[-1][0]

    @property
    def en_scope_global(self) -> bool:
        """True si estamos en el ámbito global (sin scope local activo)."""
        return len(self._pila) == 1

    # -----------------------------------------------------------------------
    # Declaración de símbolos
    # -----------------------------------------------------------------------

    def declarar(self, nombre: str, tipo: str, linea: int,
                 propietario: str = "",
                 tipo_dato:   str = "ENTERO",
                 valor:       int = 0) -> bool:
        """
        Declara un nuevo símbolo en el ámbito actual (top de la pila).

        Parámetros:
            nombre      — identificador del símbolo
            tipo        — PERSONAJE | ESCENA | ATRIBUTO | VARIABLE | FUNCION
            linea       — línea del fuente donde se declaró
            propietario — nombre del personaje dueño (solo ATRIBUTO)
            tipo_dato   — tipo del valor ("ENTERO" por defecto)
            valor       — valor inicial del símbolo (0 por defecto)

        Retorna:
            True  — declaración exitosa.
            False — el símbolo ya existe en el ámbito actual (duplicado).
        """
        _, scope_actual = self._pila[-1]
        if nombre in scope_actual:
            return False   # ya declarado en ESTE scope

        scope_actual[nombre] = Simbolo(
            nombre=nombre,
            tipo=tipo,
            ambito=self.ambito_actual,
            linea=linea,
            propietario=propietario,
            tipo_dato=tipo_dato,
            valor=valor,
        )
        return True

    # -----------------------------------------------------------------------
    # Actualización de valores
    # -----------------------------------------------------------------------

    def actualizar_valor(self, nombre: str, nuevo_valor: int) -> bool:
        """
        Actualiza el valor de un símbolo existente en el scope más cercano
        donde esté declarado (respeta la jerarquía de scopes).

        Retorna True si el símbolo fue encontrado y actualizado, False si no existe.
        Útil para reflejar cambios de runtime en la tabla (debug / visualización).
        """
        for _, scope in reversed(self._pila):
            if nombre in scope:
                scope[nombre].valor = nuevo_valor
                return True
        return False

    def actualizar_valor_propietario(self, propietario: str,
                                     nombre: str, nuevo_valor: int) -> bool:
        """
        Actualiza el valor de un ATRIBUTO dado su personaje propietario.
        Busca exclusivamente en el scope global.
        Útil para actualizar atributos de NPCs (notación punto).
        """
        _, scope_global = self._pila[0]
        for sim in scope_global.values():
            if (sim.tipo == "ATRIBUTO"
                    and sim.propietario == propietario
                    and sim.nombre == nombre):
                sim.valor = nuevo_valor
                return True
        return False

    # -----------------------------------------------------------------------
    # Búsqueda de símbolos
    # -----------------------------------------------------------------------

    def buscar(self, nombre: str) -> Optional[Simbolo]:
        """
        Busca un símbolo desde el scope más local hacia el global.
        Retorna el primer Simbolo encontrado o None.
        """
        for _, scope in reversed(self._pila):
            if nombre in scope:
                return scope[nombre]
        return None

    def buscar_en_global(self, nombre: str) -> Optional[Simbolo]:
        """Busca exclusivamente en el scope global (primer nivel de la pila)."""
        _, scope_global = self._pila[0]
        return scope_global.get(nombre)

    def buscar_en_local(self, nombre: str) -> Optional[Simbolo]:
        """
        Busca exclusivamente en el scope actual (si no es el global).
        Retorna None si estamos en el global o si no se encuentra.
        """
        if self.en_scope_global:
            return None
        _, scope_local = self._pila[-1]
        return scope_local.get(nombre)

    def existe(self, nombre: str) -> bool:
        """Retorna True si el símbolo existe en cualquier scope visible."""
        return self.buscar(nombre) is not None

    def existe_en_ambito_actual(self, nombre: str) -> bool:
        """Retorna True si el símbolo está declarado en el scope actual."""
        _, scope = self._pila[-1]
        return nombre in scope

    # -----------------------------------------------------------------------
    # Consultas de tipo
    # -----------------------------------------------------------------------

    def tipo_de(self, nombre: str) -> Optional[str]:
        """
        Retorna el tipo del símbolo si existe, o None.
        Respeta la jerarquía de scopes (local antes que global).
        """
        sim = self.buscar(nombre)
        return sim.tipo if sim else None

    def tipo_dato_de(self, nombre: str) -> Optional[str]:
        """Retorna el tipo_dato del símbolo si existe, o None."""
        sim = self.buscar(nombre)
        return sim.tipo_dato if sim else None

    # -----------------------------------------------------------------------
    # Consultas específicas del dominio LoreEngine
    # -----------------------------------------------------------------------

    def personajes_declarados(self) -> List[str]:
        """Retorna los nombres de todos los personajes declarados (globales)."""
        _, global_scope = self._pila[0]
        return [
            nombre for nombre, sim in global_scope.items()
            if sim.tipo == "PERSONAJE"
        ]

    def escenas_declaradas(self) -> List[str]:
        """Retorna los nombres de todas las escenas declaradas (globales)."""
        _, global_scope = self._pila[0]
        return [
            nombre for nombre, sim in global_scope.items()
            if sim.tipo == "ESCENA"
        ]

    def funciones_declaradas(self) -> List[str]:
        """Retorna los nombres de todas las funciones registradas (globales)."""
        _, global_scope = self._pila[0]
        return [
            nombre for nombre, sim in global_scope.items()
            if sim.tipo == "FUNCION"
        ]

    def atributos_de(self, personaje: str) -> Dict[str, Simbolo]:
        """
        Retorna un diccionario {nombre_atributo → Simbolo} con todos los
        atributos del personaje dado. Busca en el scope global.
        """
        _, global_scope = self._pila[0]
        return {
            nombre: sim
            for nombre, sim in global_scope.items()
            if sim.tipo == "ATRIBUTO" and sim.propietario == personaje
        }

    def es_atributo_de_personaje(self, nombre: str) -> bool:
        """
        Retorna True si `nombre` es un atributo de algún personaje declarado.
        Útil en el semántico para validar identificadores en expresiones.
        """
        sim = self.buscar_en_global(nombre)
        return sim is not None and sim.tipo == "ATRIBUTO"

    def es_funcion(self, nombre: str) -> bool:
        """Retorna True si el nombre corresponde a una función registrada."""
        sim = self.buscar_en_global(nombre)
        return sim is not None and sim.tipo == "FUNCION"

    # -----------------------------------------------------------------------
    # Visualización
    # -----------------------------------------------------------------------

    def imprimir(self) -> None:
        """
        Imprime la tabla de símbolos completa con columnas alineadas.
        Muestra: nombre, tipo, tipo_dato, valor, ámbito, propietario, línea.
        """
        todos: List[Simbolo] = []
        for _, scope in self._pila:
            todos.extend(scope.values())

        if not todos:
            print("  (tabla vacía)")
            return

        # Calcular anchos de columna dinámicamente
        an  = max(len(s.nombre)       for s in todos)
        at  = max(len(s.tipo)         for s in todos)
        atd = max(len(s.tipo_dato)    for s in todos)
        aa  = max(len(s.ambito)       for s in todos)
        ap  = max((len(s.propietario) for s in todos), default=0)
        av  = max(len(str(s.valor))   for s in todos)

        an  = max(an,  6)   # mínimo para la cabecera
        at  = max(at,  4)
        atd = max(atd, 9)
        aa  = max(aa,  6)
        ap  = max(ap,  11)
        av  = max(av,  5)

        sep = "  " + "─" * (an + at + atd + av + aa + ap + 34)
        enc = (
            f"  {'NOMBRE':<{an}}  {'TIPO':<{at}}  "
            f"{'TIPO_DATO':<{atd}}  {'VALOR':>{av}}  "
            f"{'ÁMBITO':<{aa}}  {'PROPIETARIO':<{ap}}  {'LÍNEA':>5}"
        )
        print(sep)
        print(enc)
        print(sep)

        # Filas agrupadas por scope
        primer_scope = True
        for nombre_scope, scope in self._pila:
            if not scope:
                continue
            if not primer_scope:
                ancho_sep = an + at + atd + av + aa + ap + 30
                print(f"  {'·' * ancho_sep}")
            primer_scope = False
            for sim in scope.values():
                prop  = sim.propietario if sim.propietario else "—"
                linea = "built-in" if sim.linea == 0 else str(sim.linea)
                print(
                    f"  {sim.nombre:<{an}}  {sim.tipo:<{at}}  "
                    f"{sim.tipo_dato:<{atd}}  {sim.valor:>{av}}  "
                    f"{sim.ambito:<{aa}}  {prop:<{ap}}  "
                    f"{linea:>8}"
                )
        print(sep)
        print(f"  Total: {len(todos)} símbolo(s)  |  "
              f"{len(self._pila)} scope(s) activo(s)\n")

    def imprimir_scope_actual(self) -> None:
        """Imprime solo el scope actualmente activo (útil para debug)."""
        nombre_scope, scope = self._pila[-1]
        print(f"  Scope '{nombre_scope}': {len(scope)} símbolo(s)")
        for sim in scope.values():
            print(f"    {sim}")
        print()

    def snapshot(self) -> Dict[str, List[Simbolo]]:
        """
        Retorna un diccionario con todos los scopes actuales.
        Útil para el intérprete al inicializar el entorno de ejecución.
        """
        return {
            nombre: list(scope.values())
            for nombre, scope in self._pila
        }


# ---------------------------------------------------------------------------
# Bloque __main__: pruebas autocontenidas
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Prueba 1: uso típico completo con valores y tipos ───────────────
    print("=" * 72)
    print(" PRUEBA 1 — Flujo completo: personaje + escenas + built-ins")
    print("=" * 72)

    ts = TablaSimbolos()

    # Los built-ins ya están registrados al crear la tabla
    print(f"\n  Funciones built-in registradas: {ts.funciones_declaradas()}")
    print(f"  dado es FUNCION: {ts.es_funcion('dado')}\n")

    # Registrar personaje y sus atributos con valores iniciales
    ts.declarar("heroe",  "PERSONAJE", linea=1,  tipo_dato="NINGUNO")
    ts.declarar("vida",   "ATRIBUTO",  linea=2,  propietario="heroe",  valor=100)
    ts.declarar("oro",    "ATRIBUTO",  linea=3,  propietario="heroe",  valor=50)
    ts.declarar("fuerza", "ATRIBUTO",  linea=4,  propietario="heroe",  valor=20)

    # Registrar NPC con atributos de nombre único (la tabla usa el nombre como
    # clave; atributos compartidos con el héroe se gestionan vía dot-notation
    # en el semántico usando _attrs_personaje, no en la tabla directamente).
    ts.declarar("goblin",  "PERSONAJE", linea=6,  tipo_dato="NINGUNO")
    ts.declarar("g_vida",  "ATRIBUTO",  linea=7,  propietario="goblin", valor=40)
    ts.declarar("g_fuerza","ATRIBUTO",  linea=8,  propietario="goblin", valor=15)

    # Registrar escenas
    ts.declarar("inicio",  "ESCENA", linea=10, tipo_dato="NINGUNO")
    ts.declarar("bosque",  "ESCENA", linea=20, tipo_dato="NINGUNO")
    ts.declarar("combate", "ESCENA", linea=30, tipo_dato="NINGUNO")

    print("  Tabla tras declaraciones globales:\n")
    ts.imprimir()

    # ── Prueba 2: actualizar valores durante la ejecución ───────────────
    print("=" * 72)
    print(" PRUEBA 2 — Actualización de valores (simulando ejecución)")
    print("=" * 72)

    # Simular: vida del héroe baja de 100 a 75
    ts.actualizar_valor("vida", 75)
    print(f"\n  Después de actualizar_valor('vida', 75):")
    print(f"    vida del heroe → {ts.buscar_en_global('vida').valor}")

    # Simular: vida del goblin baja de 40 a 18 (por notación punto)
    ts.actualizar_valor_propietario("goblin", "g_vida", 18)
    print(f"  Después de actualizar_valor_propietario('goblin', 'g_vida', 18):")
    sims_goblin = ts.atributos_de("goblin")
    print(f"    goblin.g_vida → {sims_goblin['g_vida'].valor}\n")

    # ── Prueba 3: scope local con shadowing ─────────────────────────────
    print("=" * 72)
    print(" PRUEBA 3 — Scope local y shadowing")
    print("=" * 72)

    ts.entrar_ambito("combate")
    ts.declarar("vida", "VARIABLE", linea=31, valor=75)   # sombrea al ATRIBUTO

    print("\n  Tabla con scope de 'combate' activo:\n")
    ts.imprimir()

    sim_local  = ts.buscar("vida")
    sim_global = ts.buscar_en_global("vida")
    print(f"  buscar('vida') → tipo={sim_local.tipo!r}, valor={sim_local.valor}"
          f"  (scope local)")
    print(f"  buscar_en_global('vida') → tipo={sim_global.tipo!r}, "
          f"valor={sim_global.valor}  (scope global)\n")

    ts.salir_ambito()
    print(f"  Tras salir_ambito(): buscar('vida').tipo = "
          f"{ts.buscar('vida').tipo!r}  (vuelve al ATRIBUTO global)\n")

    # ── Prueba 4: consultas de dominio ───────────────────────────────────
    print("=" * 72)
    print(" PRUEBA 4 — Consultas de dominio LoreEngine")
    print("=" * 72)

    print(f"\n  personajes_declarados() → {ts.personajes_declarados()}")
    print(f"  escenas_declaradas()    → {ts.escenas_declaradas()}")
    print(f"  funciones_declaradas()  → {ts.funciones_declaradas()}")
    print(f"  atributos_de('heroe')   → {list(ts.atributos_de('heroe').keys())}")
    print(f"  atributos_de('goblin')  → {list(ts.atributos_de('goblin').keys())}  (con prefijo único)")
    print(f"  tipo_dato_de('dado')    → {ts.tipo_dato_de('dado')!r}")
    print(f"  es_funcion('dado')      → {ts.es_funcion('dado')}")
    print(f"  es_funcion('vida')      → {ts.es_funcion('vida')}\n")

    # ── Prueba 5: detección de duplicados ───────────────────────────────
    print("=" * 72)
    print(" PRUEBA 5 — Detección de duplicados")
    print("=" * 72)

    ts2 = TablaSimbolos()
    ok1 = ts2.declarar("vida", "ATRIBUTO", linea=2, propietario="heroe", valor=100)
    ok2 = ts2.declarar("vida", "ATRIBUTO", linea=5, propietario="heroe", valor=200)
    print(f"\n  Primera declaración de 'vida'  → {'OK' if ok1 else 'DUPLICADO'}")
    print(f"  Segunda declaración de 'vida'  → {'OK' if ok2 else 'DUPLICADO'}")

    ts2.entrar_ambito("escena_x")
    ok3 = ts2.declarar("vida", "VARIABLE", linea=10, valor=80)
    ts2.salir_ambito()
    print(f"  'vida' como VARIABLE en scope local → {'OK' if ok3 else 'DUPLICADO'}")
    print(f"  (no es duplicado: está en scope diferente)\n")

    print("  ✓ symbol_table.py actualizado y listo.\n")
