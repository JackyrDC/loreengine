# =============================================================================
# main_gui.py — IDE gráfico de LoreEngine
# Curso: IS-913 Diseño de Compiladores — UNAH-COMAYAGUA
# =============================================================================
#
# Layout:
#   Panel izquierdo : editor con números de línea + resaltado de sintaxis
#                     consola de compilación con colores por fase
#   Panel derecho   : stats del personaje (barras de progreso canvas)
#                     área narrativa de la historia
#                     botones de decisión (aparecen dinámicamente)
#   Barra inferior  : estado del pipeline
#
# Hilo principal  → Tkinter (UI)
# Hilo secundario → Interprete (bloquea en _leer_opcion)
# Comunicación    → ui_queue (intérprete → UI) + reply_queue (UI → intérprete)
# =============================================================================

import sys
import os
import threading
import queue
import io
import contextlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from lexer_loreengine     import analizar as lex_analizar
from parser_loreengine    import Parser, ErrorSintactico
from semantico_loreengine import AnalizadorSemantico, ErrorSemantico
from interprete_loreengine import Interprete, ErrorEjecucion
from ast_nodes            import NodoPersonaje


# =============================================================================
# Paleta de colores — estilo Dungeon (oscuro, legible, con toques dorados)
# =============================================================================

C = {
    # Fondos
    "bg":          "#17131f",  # fondo principal (piedra oscura)
    "bg_panel":    "#1e1a2b",  # fondo paneles
    "bg_editor":   "#1a1626",  # editor de código
    "bg_console":  "#110e18",  # consola de compilación
    "bg_narr":     "#1c1825",  # área narrativa
    "bg_stats":    "#191525",  # panel de stats
    "bg_input":    "#110e18",  # fondo entradas

    # Texto
    "text":        "#d4cbbf",  # texto principal (pergamino cálido)
    "text_dim":    "#6e6580",  # atenuado (números de línea, hints)
    "text_title":  "#c9a430",  # títulos de panel (oro)
    "text_gold":   "#f0c040",  # valores de stat (oro brillante)
    "text_scene":  "#e8c878",  # cabecera de escena en narrativa

    # Consola de compilación
    "con_phase":   "#5aacbf",  # encabezado de fase (cyan)
    "con_ok":      "#5aab77",  # éxito (verde bosque)
    "con_err":     "#e05252",  # error (rojo)
    "con_warn":    "#d4a520",  # advertencia (dorado)
    "con_info":    "#a89fc0",  # texto normal consola
    "con_run":     "#7b9fd4",  # info de ejecución (azul suave)

    # Syntax highlighting del editor
    "syn_kw":      "#c78cde",  # keywords (morado claro)
    "syn_str":     "#8fb58c",  # strings (verde musgo)
    "syn_num":     "#8ab4f8",  # números (azul pálido)
    "syn_arrow":   "#e09060",  # flecha -> (naranja)
    "syn_com":     "#6a7f6a",  # comentarios (gris verdoso)

    # Barras de progreso (canvas)
    "bar_bg":      "#0d0b12",  # fondo de la barra
    "bar_high":    "#3d7a52",  # vida alta (verde)
    "bar_mid":     "#8a6e1a",  # media (dorado oscuro)
    "bar_low":     "#7b2030",  # baja (rojo oscuro)

    # Botones
    "btn":         "#2f2550",  # botón normal
    "btn_hov":     "#473d70",  # hover normal
    "btn_run":     "#6e2238",  # botón ejecutar (rojo sangre)
    "btn_run_hov": "#8f2f4a",  # hover ejecutar
    "btn_opt":     "#1f1a38",  # botón opción
    "btn_opt_hov": "#312b55",  # hover opción
    "btn_stop":    "#3a2020",  # botón detener
    "btn_stop_hov":"#5a3030",  # hover detener

    # Bordes y sash
    "border":           "#3a2f52",  # bordes de paneles
    "sash":             "#2a2238",  # separador PanedWindow
    # Paneles NPC — colores por rol
    "border_enemigo":   "#5a2035",  # borde enemigo (rojo-violeta)
    "bg_enemigo":       "#1e1420",  # fondo enemigo
    "title_enemigo":    "#d46080",  # título enemigo (rosa oscuro)
    "border_aliado":    "#1e4a2f",  # borde aliado (verde oscuro)
    "bg_aliado":        "#141e18",  # fondo aliado
    "title_aliado":     "#5aab77",  # título aliado (verde claro)
    "border_neutral":   "#3a3a4a",  # borde neutral (gris)
    "bg_neutral":       "#1a1a28",  # fondo neutral
    "title_neutral":    "#8888aa",  # título neutral (gris azulado)
    # Retrocompat — apuntan al enemigo (usado antes de roles)
    "border_npc":       "#5a2035",
    "bg_npc":           "#1e1420",
    "npc_title":        "#d46080",

    # Números de línea
    "lnum_bg":     "#110e18",
    "lnum_fg":     "#4a3f60",
}

# Fuentes — definidas como tuplas (no requieren root inicializado)
FM     = ("Consolas", 10)           # mono normal (editor)
FM_SM  = ("Consolas", 9)            # mono pequeño (consola, nums)
FU     = ("Segoe UI", 10)           # UI normal
FU_B   = ("Segoe UI", 10, "bold")   # UI bold
FU_T   = ("Segoe UI", 11, "bold")   # título de panel
FN     = ("Georgia", 11)            # narrativa
FN_H   = ("Georgia", 13, "bold")    # cabecera de escena

# Keywords del lenguaje para resaltado
_KW = frozenset({"personaje", "escena", "mostrar", "decision", "si", "sino",
                 "dado", "principal", "enemigo", "aliado", "neutral"})

# Iconos predeterminados por nombre de atributo
_ICONOS = {
    "vida":     "❤",
    "oro":      "🪙",
    "fuerza":   "⚔",
    "magia":    "✨",
    "defensa":  "🛡",
    "agilidad": "💨",
}


# =============================================================================
# Señal interna de parada limpia del hilo intérprete
# =============================================================================

class _PararEjecucion(Exception):
    """Lanzada desde _leer_opcion para detener el hilo del intérprete."""
    pass


# =============================================================================
# Intérprete con métodos de presentación conectados a la GUI
# =============================================================================

class InterpreteLoreGUI(Interprete):
    """
    Sobreescribe los métodos de presentación del Interprete base para
    comunicarse con la GUI a través de colas (thread-safe).

    El hilo del intérprete NUNCA toca widgets directamente.
    Toda actualización de UI pasa por ui_queue → hilo principal.
    """

    def __init__(self, ast, ui_queue: queue.Queue,
                 reply_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(ast)
        self._uq         = ui_queue
        self._rq         = reply_queue
        self._stop       = stop_event
        # Valores anteriores de cada atributo (para calcular deltas)
        self._prev_stats:     dict = {}   # héroe: {nombre → valor}
        self._prev_npc_stats: dict = {}   # NPCs:  {(personaje, nombre) → valor}
        # Caché de attrs iniciales de cada NPC — el panel se crea en su
        # primer cambio de stat, no al arrancar
        self._npc_attrs_cache: dict = {}   # {personaje: [(attr, val), ...]}
        self._npc_initialized: set  = set()  # personajes cuyo panel ya existe

    # ── Carga inicial: emitir stats al arrancar ──────────────────────────────

    def _cargar_programa(self) -> None:
        """Carga atributos y notifica a la GUI de los valores iniciales."""
        super()._cargar_programa()

        # Panel del héroe (primer personaje declarado)
        if self._nombre_personaje and self._nombre_personaje in self._personajes:
            personaje = self._personajes[self._nombre_personaje]
            attrs = [(a.nombre, self._entorno.obtener(a.nombre))
                     for a in personaje.atributos]
            for nombre, valor in attrs:
                self._prev_stats[nombre] = valor
            self._uq.put(("setup_stats", self._nombre_personaje, attrs))

        # Pre-calcular attrs de NPCs pero NO emitir setup_npc todavía.
        # El panel de cada NPC se creará la primera vez que uno de sus
        # atributos cambie (_on_variable_cambiada), para que solo aparezca
        # cuando el NPC entre realmente en la escena.
        for nombre_p, personaje in self._personajes.items():
            if nombre_p == self._nombre_personaje:
                continue
            env = self._entornos.get(nombre_p)
            if not env:
                continue
            attrs = [(a.nombre, env.obtener(a.nombre))
                     for a in personaje.atributos]
            for attr_nombre, valor in attrs:
                self._prev_npc_stats[(nombre_p, attr_nombre)] = valor
            self._npc_attrs_cache[nombre_p] = attrs   # guardar para después

    # ── Métodos de presentación ──────────────────────────────────────────────

    def _mostrar_texto(self, texto: str) -> None:
        self._uq.put(("texto", texto))

    def _mostrar_encabezado_escena(self, nombre: str) -> None:
        # Al entrar a una escena nueva, resetear qué NPCs han aparecido ya.
        # Así los que no actúen en esta escena no crearán panel.
        self._npc_initialized.clear()
        self._uq.put(("escena", nombre))

    def _mostrar_panel_personaje(self) -> None:
        pass   # el panel se mantiene actualizado vía _on_variable_cambiada

    def _mostrar_opciones(self, opciones) -> None:
        self._uq.put(("opciones", opciones))

    def _leer_opcion(self, n: int) -> int:
        """Bloquea el hilo del intérprete hasta que el jugador hace clic."""
        while True:
            if self._stop.is_set():
                raise _PararEjecucion()
            try:
                choice = self._rq.get(timeout=0.1)
                if choice is None:
                    raise _PararEjecucion()
                return choice
            except queue.Empty:
                continue

    def _on_variable_cambiada(self, nombre: str, valor: int,
                              personaje: str = "") -> None:
        es_heroe = (not personaje or personaje == self._nombre_personaje)
        if es_heroe:
            prev = self._prev_stats.get(nombre)
            self._uq.put(("stat", nombre, valor))
            if prev is not None and prev != valor:
                self._uq.put(("stat_cambio", nombre, prev, valor))
            self._prev_stats[nombre] = valor
        else:
            # Primera vez que este NPC aparece → crear su panel ahora
            if personaje not in self._npc_initialized:
                self._npc_initialized.add(personaje)
                env       = self._entornos.get(personaje)
                pers_nodo = self._personajes.get(personaje)
                if env and pers_nodo:
                    # Valores actuales: lo que se muestra en la barra ahora
                    attrs = [(a.nombre, env.obtener(a.nombre))
                             for a in pers_nodo.atributos]
                    # Valores iniciales (declarados): definen el 100% de la barra
                    max_attrs = dict(self._npc_attrs_cache.get(personaje, []))
                    rol = pers_nodo.rol
                else:
                    attrs     = self._npc_attrs_cache.get(personaje, [])
                    max_attrs = dict(attrs)
                    rol       = "neutral"
                self._uq.put(("setup_npc", personaje, attrs, rol, max_attrs))
            key  = (personaje, nombre)
            prev = self._prev_npc_stats.get(key)
            self._uq.put(("stat_npc", personaje, nombre, valor))
            if prev is not None and prev != valor:
                self._uq.put(("stat_cambio_npc", personaje, nombre, prev, valor))
            self._prev_npc_stats[key] = valor

    def _mostrar_fin(self) -> None:
        self._uq.put(("fin",))

    def _mostrar_error(self, mensaje: str) -> None:
        self._uq.put(("error_ejec", mensaje))

    def _mostrar_advertencia(self, mensaje: str) -> None:
        self._uq.put(("warn_ejec", mensaje))


# =============================================================================
# IDE principal
# =============================================================================

class LoreEngineIDE(tk.Tk):
    """Ventana principal del IDE de LoreEngine."""

    # ── Inicialización ───────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.title("LoreEngine IDE")
        self.geometry("1300x760")
        self.minsize(900, 600)
        self.configure(bg=C["bg"])

        # Estado de ejecución
        self._ui_queue    = queue.Queue()
        self._reply_queue = queue.Queue()
        self._stop_event  = threading.Event()
        self._interp_thread: threading.Thread | None = None
        self._ejecutando  = False

        # Referencia a widgets de stats del héroe (nombre → dict con refs)
        self._stat_widgets: dict = {}   # nombre → {canvas, lbl_val, max_val, …}

        # Widgets de stats de NPCs (anidado por personaje)
        self._npc_stat_widgets: dict = {}   # personaje → {attr → {canvas, …}}
        self._npc_panels:       dict = {}   # personaje → Frame del panel
        self._npc_seps:         list = []   # separadores de 1px entre paneles

        # ── Cola secuencial de mensajes narrativos ───────────────────────────
        # Los mensajes de texto/opciones/escena se acolan aquí y se procesan
        # uno a uno. Mientras un texto se escribe letra a letra (_tw_busy=True)
        # el siguiente mensaje espera, garantizando el orden correcto.
        from collections import deque
        self._pending_seq: deque = deque()
        self._tw_busy   = False   # True mientras el typewriter está activo
        self._tw_chars:  list = []
        self._tw_tag:    str  = "narrative"
        self._tw_idx:    int  = 0
        self._tw_timer        = None
        self._tw_delay   = 10   # milisegundos por carácter (ajustable)

        # Debounce para resaltado de sintaxis
        self._hl_timer = None

        # Archivo actual
        self._archivo_actual: str | None = None

        self._configure_ttk_styles()
        self._build_ui()
        self._start_queue_poll()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_ttk_styles(self) -> None:
        """Configura estilos ttk para que combinen con la paleta oscura."""
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Dark.TPanedwindow",
                     background=C["sash"])
        s.configure("Dark.Sash",
                     sashrelief=tk.FLAT, sashpad=2, sashwidth=4,
                     background=C["sash"])
        # Scrollbars oscuras
        s.configure("Dark.Vertical.TScrollbar",
                     background=C["bg_panel"], troughcolor=C["bg"],
                     arrowcolor=C["text_dim"], bordercolor=C["border"],
                     relief=tk.FLAT)
        s.configure("Dark.Horizontal.TScrollbar",
                     background=C["bg_panel"], troughcolor=C["bg"],
                     arrowcolor=C["text_dim"], bordercolor=C["border"],
                     relief=tk.FLAT)

    # ── Construcción del layout ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construye el layout completo de la ventana."""
        # Barra de estado (inferior)
        self._build_statusbar()

        # PanedWindow principal (horizontal)
        self._paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=C["sash"],
            sashrelief=tk.FLAT,
            sashwidth=4,
            sashpad=0,
        )
        self._paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Paneles
        left  = tk.Frame(self._paned, bg=C["bg_panel"])
        right = tk.Frame(self._paned, bg=C["bg"])

        self._paned.add(left,  minsize=320, width=430)
        self._paned.add(right, minsize=400)

        self._build_left(left)
        self._build_right(right)

    # ── Panel izquierdo: editor + consola ────────────────────────────────────

    def _build_left(self, parent: tk.Frame) -> None:
        """Panel izquierdo: editor con números de línea y consola."""
        parent.rowconfigure(1, weight=3)
        parent.rowconfigure(4, weight=2)
        parent.columnconfigure(0, weight=1)

        # Cabecera del editor
        self._lbl_editor_title = tk.Label(
            parent, text="  Editor  ·  LoreEngine",
            bg=C["bg_panel"], fg=C["text_title"],
            font=FU_T, anchor="w", pady=6,
        )
        self._lbl_editor_title.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        # Contenedor del editor
        editor_frame = tk.Frame(parent, bg=C["bg_editor"],
                                highlightthickness=1,
                                highlightbackground=C["border"])
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(1, weight=1)

        # Números de línea — misma fuente y pady que el editor para alineación exacta
        self._line_nums = tk.Text(
            editor_frame,
            width=4, font=FM,
            bg=C["lnum_bg"], fg=C["lnum_fg"],
            bd=0, padx=6, pady=4,
            state=tk.DISABLED,
            cursor="arrow",
            takefocus=False,
        )
        self._line_nums.grid(row=0, column=0, sticky="ns")

        # Redirigir scroll del mouse sobre los números al editor
        self._line_nums.bind(
            "<MouseWheel>",
            lambda e: self._editor.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        # Linux (rueda arriba/abajo como Button-4/5)
        self._line_nums.bind(
            "<Button-4>", lambda *_: self._editor.yview_scroll(-1, "units")
        )
        self._line_nums.bind(
            "<Button-5>", lambda *_: self._editor.yview_scroll(1, "units")
        )

        # Editor principal
        self._editor = tk.Text(
            editor_frame,
            font=FM, wrap=tk.NONE,
            bg=C["bg_editor"], fg=C["text"],
            insertbackground=C["text_gold"],
            selectbackground=C["btn"],
            selectforeground=C["text"],
            bd=0, padx=6, pady=4,
            undo=True,
        )
        self._editor.grid(row=0, column=1, sticky="nsew")

        # Scrollbar vertical del editor
        ed_vscroll = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL,
                                   style="Dark.Vertical.TScrollbar")
        ed_vscroll.grid(row=0, column=2, sticky="ns")
        self._editor.config(yscrollcommand=self._editor_yscroll)
        ed_vscroll.config(command=self._editor.yview)
        self._ed_vscroll = ed_vscroll

        # Scrollbar horizontal del editor
        ed_hscroll = ttk.Scrollbar(editor_frame, orient=tk.HORIZONTAL,
                                   style="Dark.Horizontal.TScrollbar")
        ed_hscroll.grid(row=1, column=1, sticky="ew")
        self._editor.config(xscrollcommand=ed_hscroll.set)
        ed_hscroll.config(command=self._editor.xview)

        # Configurar tags de syntax highlighting
        self._editor.tag_configure("kw",     foreground=C["syn_kw"])
        self._editor.tag_configure("str",    foreground=C["syn_str"])
        self._editor.tag_configure("num",    foreground=C["syn_num"])
        self._editor.tag_configure("arrow",  foreground=C["syn_arrow"])
        self._editor.tag_configure("com",    foreground=C["syn_com"])

        # Eventos del editor
        self._editor.bind("<KeyRelease>", self._on_editor_change)
        self._editor.bind("<ButtonRelease>", self._update_line_numbers)

        # Insertar ejemplo inicial
        self._editor.insert("1.0", _EJEMPLO_INICIAL)
        self._update_line_numbers()
        self._highlight_syntax()

        # ── Barra de botones ─────────────────────────────────────────────────
        btn_bar = tk.Frame(parent, bg=C["bg_panel"], pady=4)
        btn_bar.grid(row=2, column=0, sticky="ew", padx=6)

        self._btn_abrir   = self._make_btn(btn_bar, "📂 Abrir",  self._abrir_archivo)
        self._btn_guardar = self._make_btn(btn_bar, "💾 Guardar", self._guardar_archivo)
        self._btn_run     = self._make_btn(btn_bar, "▶  Compilar y Ejecutar",
                                           self._run_pipeline,
                                           bg=C["btn_run"], hov=C["btn_run_hov"],
                                           bold=True)
        self._btn_stop    = self._make_btn(btn_bar, "■  Detener", self._stop_pipeline,
                                           bg=C["btn_stop"], hov=C["btn_stop_hov"])
        self._btn_stop.config(state=tk.DISABLED)

        self._btn_abrir.pack(side=tk.LEFT, padx=3)
        self._btn_guardar.pack(side=tk.LEFT, padx=3)
        self._btn_run.pack(side=tk.LEFT, padx=8)
        self._btn_stop.pack(side=tk.LEFT, padx=3)

        # ── Consola de compilación ───────────────────────────────────────────
        tk.Label(parent, text="  Consola de compilación",
                 bg=C["bg_panel"], fg=C["text_title"],
                 font=FU_T, anchor="w", pady=5,
                 ).grid(row=3, column=0, sticky="ew")

        console_frame = tk.Frame(parent, bg=C["bg_console"],
                                 highlightthickness=1,
                                 highlightbackground=C["border"])
        console_frame.grid(row=4, column=0, sticky="nsew", padx=6, pady=(0, 6))
        console_frame.rowconfigure(0, weight=1)
        console_frame.columnconfigure(0, weight=1)

        self._console = tk.Text(
            console_frame,
            font=FM_SM, wrap=tk.WORD,
            bg=C["bg_console"], fg=C["con_info"],
            insertbackground=C["text"],
            bd=0, padx=8, pady=6,
            state=tk.DISABLED,
        )
        self._console.grid(row=0, column=0, sticky="nsew")

        con_scroll = ttk.Scrollbar(console_frame, orient=tk.VERTICAL,
                                   style="Dark.Vertical.TScrollbar")
        con_scroll.grid(row=0, column=1, sticky="ns")
        self._console.config(yscrollcommand=con_scroll.set)
        con_scroll.config(command=self._console.yview)

        # Tags de color para la consola
        self._console.tag_configure("phase", foreground=C["con_phase"], font=FM_SM)
        self._console.tag_configure("ok",    foreground=C["con_ok"])
        self._console.tag_configure("err",   foreground=C["con_err"])
        self._console.tag_configure("warn",  foreground=C["con_warn"])
        self._console.tag_configure("info",  foreground=C["con_info"])
        self._console.tag_configure("run",   foreground=C["con_run"])

    # ── Panel derecho: stats + narrativa + opciones ──────────────────────────

    def _build_right(self, parent: tk.Frame) -> None:
        """Panel derecho: estadísticas, narrativa y decisiones."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)   # narrativa se expande

        # ── Stats del personaje ──────────────────────────────────────────────
        self._stats_outer = tk.Frame(parent, bg=C["bg_stats"],
                                     highlightthickness=1,
                                     highlightbackground=C["border"])
        self._stats_outer.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
        self._stats_outer.columnconfigure(0, weight=1)

        tk.Label(self._stats_outer,
                 text="  Personaje",
                 bg=C["bg_stats"], fg=C["text_title"],
                 font=FU_T, anchor="w", pady=4,
                 ).pack(fill=tk.X)

        self._stats_name_lbl = tk.Label(
            self._stats_outer,
            text="  (sin personaje)",
            bg=C["bg_stats"], fg=C["text_dim"],
            font=FU, anchor="w",
        )
        self._stats_name_lbl.pack(fill=tk.X, padx=8)

        # Frame contenedor de las filas de stat
        self._stats_rows_frame = tk.Frame(self._stats_outer, bg=C["bg_stats"])
        self._stats_rows_frame.pack(fill=tk.X, padx=8, pady=(2, 6))

        # ── Narrativa ────────────────────────────────────────────────────────
        narr_outer = tk.Frame(parent, bg=C["bg_narr"],
                              highlightthickness=1,
                              highlightbackground=C["border"])
        narr_outer.grid(row=1, column=0, sticky="nsew", padx=6, pady=3)
        narr_outer.rowconfigure(1, weight=1)
        narr_outer.columnconfigure(0, weight=1)

        tk.Label(narr_outer,
                 text="  Historia",
                 bg=C["bg_narr"], fg=C["text_title"],
                 font=FU_T, anchor="w", pady=4,
                 ).grid(row=0, column=0, columnspan=2, sticky="ew")

        self._narrative = tk.Text(
            narr_outer,
            font=FN, wrap=tk.WORD,
            bg=C["bg_narr"], fg=C["text"],
            insertbackground=C["text"],
            bd=0, padx=14, pady=10,
            state=tk.DISABLED,
            cursor="arrow",
            spacing3=4,   # espacio extra entre párrafos
        )
        self._narrative.grid(row=1, column=0, sticky="nsew")

        narr_scroll = ttk.Scrollbar(narr_outer, orient=tk.VERTICAL,
                                    style="Dark.Vertical.TScrollbar")
        narr_scroll.grid(row=1, column=1, sticky="ns")
        self._narrative.config(yscrollcommand=narr_scroll.set)
        narr_scroll.config(command=self._narrative.yview)

        # Tags de formato narrativo
        self._narrative.tag_configure(
            "scene_hdr",
            foreground=C["text_scene"],
            font=FN_H,
            spacing1=10, spacing3=6,
        )
        self._narrative.tag_configure(
            "narrative",
            foreground=C["text"],
            font=FN,
            lmargin1=4, lmargin2=4,
        )
        self._narrative.tag_configure(
            "narr_error",
            foreground=C["con_err"],
            font=FU,
        )
        self._narrative.tag_configure(
            "sep",
            foreground=C["text_dim"],
            font=FM_SM,
        )
        # Tags para cambios de stats (pérdida=rojo, ganancia=verde)
        self._narrative.tag_configure(
            "stat_baja",
            foreground="#e05252",
            font=("Segoe UI", 9, "italic"),
            lmargin1=20, lmargin2=20,
        )
        self._narrative.tag_configure(
            "stat_sube",
            foreground="#5aab77",
            font=("Segoe UI", 9, "italic"),
            lmargin1=20, lmargin2=20,
        )

        # ── Panel de opciones (oculto por defecto) ───────────────────────────
        self._options_outer = tk.Frame(parent, bg=C["bg_panel"],
                                       highlightthickness=1,
                                       highlightbackground=C["border"])
        # Se muestra con grid cuando hay decisión
        self._options_outer.columnconfigure(0, weight=1)

        tk.Label(self._options_outer,
                 text="  ¿Qué decides hacer?",
                 bg=C["bg_panel"], fg=C["text_title"],
                 font=FU_T, anchor="w", pady=5,
                 ).pack(fill=tk.X)

        self._options_btns_frame = tk.Frame(self._options_outer, bg=C["bg_panel"])
        self._options_btns_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._options_visible = False

    # ── Barra de estado inferior ─────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        """Barra de estado con información del pipeline."""
        self._statusbar = tk.Frame(self, bg=C["border"], height=28)
        self._statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        self._statusbar.pack_propagate(False)

        self._status_lbl = tk.Label(
            self._statusbar,
            text="  Listo  ·  LoreEngine IDE",
            bg=C["border"], fg=C["text_dim"],
            font=FU, anchor="w",
        )
        self._status_lbl.pack(side=tk.LEFT, padx=8)

        self._status_scene = tk.Label(
            self._statusbar,
            text="",
            bg=C["border"], fg=C["text_gold"],
            font=FU_B, anchor="e",
        )
        self._status_scene.pack(side=tk.RIGHT, padx=12)

    # =========================================================================
    # Helpers de construcción
    # =========================================================================

    def _make_btn(self, parent, texto, cmd, bg=None, hov=None,
                  bold=False) -> tk.Button:
        """Crea un botón con efecto hover y estilo dungeon."""
        bg  = bg  or C["btn"]
        hov = hov or C["btn_hov"]
        fn  = FU_B if bold else FU

        btn = tk.Button(
            parent, text=texto, command=cmd,
            bg=bg, fg=C["text"],
            activebackground=hov, activeforeground=C["text"],
            font=fn, relief=tk.FLAT,
            padx=10, pady=5,
            cursor="hand2",
            bd=0,
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=hov))
        btn.bind("<Leave>", lambda e: btn.config(
            bg=bg if str(btn["state"]) != tk.DISABLED else C["btn_stop"]
        ))
        return btn

    # =========================================================================
    # Editor — números de línea y sincronización de scroll
    # =========================================================================

    def _editor_yscroll(self, first, last) -> None:
        """Sincroniza scroll del editor con la barra y los números de línea."""
        self._ed_vscroll.set(first, last)
        self._line_nums.yview_moveto(first)

    def _update_line_numbers(self, event=None) -> None:
        """Regenera los números de línea según el contenido del editor."""
        n_lines = int(self._editor.index(tk.END).split(".")[0]) - 1
        nums = "\n".join(str(i) for i in range(1, n_lines + 1))
        self._line_nums.config(state=tk.NORMAL)
        self._line_nums.delete("1.0", tk.END)
        self._line_nums.insert("1.0", nums)
        self._line_nums.config(state=tk.DISABLED)

    def _on_editor_change(self, event=None) -> None:
        """Actualiza números de línea y programa el resaltado con debounce."""
        self._update_line_numbers()
        if self._hl_timer:
            self.after_cancel(self._hl_timer)
        self._hl_timer = self.after(180, self._highlight_syntax)
        # Actualizar título si hay archivo cargado
        if self._archivo_actual:
            self.title(f"LoreEngine IDE  ·  {os.path.basename(self._archivo_actual)} *")

    def _highlight_syntax(self) -> None:
        """Resalta sintaxis del editor (keywords, strings, números, flecha, comentarios)."""
        for tag in ("kw", "str", "num", "arrow", "com"):
            self._editor.tag_remove(tag, "1.0", tk.END)

        content = self._editor.get("1.0", tk.END)
        lines   = content.split("\n")

        in_block_comment = False   # estado entre líneas para /* */

        for row_idx, line in enumerate(lines):
            row = row_idx + 1
            j   = 0
            in_string = False
            str_start = 0

            # Si seguimos dentro de un bloque /* */ de la línea anterior
            if in_block_comment:
                end_idx = line.find("*/")
                if end_idx == -1:
                    # Toda la línea es comentario
                    self._editor.tag_add("com", f"{row}.0", f"{row}.{len(line)}")
                    continue
                else:
                    # El bloque cierra en esta línea
                    self._editor.tag_add("com", f"{row}.0", f"{row}.{end_idx + 2}")
                    in_block_comment = False
                    j = end_idx + 2
                    # continúa el while para el resto de la línea

            while j < len(line):
                ch = line[j]

                if in_string:
                    if ch == '"':
                        self._editor.tag_add("str", f"{row}.{str_start}",
                                             f"{row}.{j + 1}")
                        in_string = False
                    j += 1
                    continue

                if ch == '"':
                    in_string = True
                    str_start = j
                    j += 1
                    continue

                # Comentario de línea //
                if ch == '/' and j + 1 < len(line) and line[j + 1] == '/':
                    self._editor.tag_add("com", f"{row}.{j}", f"{row}.{len(line)}")
                    break   # el resto de la línea es comentario

                # Comentario de bloque /* … */
                if ch == '/' and j + 1 < len(line) and line[j + 1] == '*':
                    com_start = j
                    end_idx   = line.find("*/", j + 2)
                    if end_idx == -1:
                        # El bloque no cierra en esta línea
                        self._editor.tag_add("com", f"{row}.{com_start}",
                                             f"{row}.{len(line)}")
                        in_block_comment = True
                        break
                    else:
                        self._editor.tag_add("com", f"{row}.{com_start}",
                                             f"{row}.{end_idx + 2}")
                        j = end_idx + 2
                        continue

                # Flecha ->
                if ch == '-' and j + 1 < len(line) and line[j + 1] == '>':
                    self._editor.tag_add("arrow", f"{row}.{j}", f"{row}.{j + 2}")
                    j += 2
                    continue

                # Número
                if ch.isdigit():
                    end_j = j
                    while end_j < len(line) and line[end_j].isdigit():
                        end_j += 1
                    self._editor.tag_add("num", f"{row}.{j}", f"{row}.{end_j}")
                    j = end_j
                    continue

                # Identificador o keyword
                if ch.isalpha() or ch == '_':
                    end_j = j
                    while end_j < len(line) and (line[end_j].isalnum()
                                                 or line[end_j] == '_'):
                        end_j += 1
                    word = line[j:end_j]
                    if word in _KW:
                        self._editor.tag_add("kw", f"{row}.{j}", f"{row}.{end_j}")
                    j = end_j
                    continue

                j += 1

    # =========================================================================
    # Consola de compilación
    # =========================================================================

    def _console_clear(self) -> None:
        self._console.config(state=tk.NORMAL)
        self._console.delete("1.0", tk.END)
        self._console.config(state=tk.DISABLED)

    def _console_write(self, texto: str, tag: str = "info") -> None:
        """Inserta una línea en la consola con el tag de color dado."""
        self._console.config(state=tk.NORMAL)
        self._console.insert(tk.END, texto + "\n", tag)
        self._console.see(tk.END)
        self._console.config(state=tk.DISABLED)

    def _console_sep(self) -> None:
        self._console_write("─" * 44, "info")

    # =========================================================================
    # Panel de stats del personaje
    # =========================================================================

    def _stats_setup(self, nombre_personaje: str,
                     attrs: list[tuple[str, int]]) -> None:
        """Crea las filas de stat a partir de los atributos del personaje."""
        # Limpiar filas previas
        for w in self._stats_rows_frame.winfo_children():
            w.destroy()
        self._stat_widgets.clear()

        self._stats_name_lbl.config(
            text=f"  ⚔  {nombre_personaje.upper()}",
            fg=C["text_gold"],
            font=FU_B,
        )

        for nombre, valor_inicial in attrs:
            icono = _ICONOS.get(nombre, "◆")
            fila  = tk.Frame(self._stats_rows_frame, bg=C["bg_stats"])
            fila.pack(fill=tk.X, pady=2)
            fila.columnconfigure(1, weight=1)

            # Icono + nombre
            tk.Label(
                fila, text=f"{icono} {nombre}",
                bg=C["bg_stats"], fg=C["text"],
                font=FU, width=11, anchor="w",
            ).grid(row=0, column=0, padx=(0, 6))

            # Canvas barra de progreso
            canvas = tk.Canvas(
                fila, height=14, bg=C["bar_bg"],
                highlightthickness=0,
            )
            canvas.grid(row=0, column=1, sticky="ew", padx=(0, 6))

            # Label valor
            lbl_val = tk.Label(
                fila, text=str(valor_inicial),
                bg=C["bg_stats"], fg=C["text_gold"],
                font=FM, width=6, anchor="e",
            )
            lbl_val.grid(row=0, column=2)

            self._stat_widgets[nombre] = {
                "canvas":      canvas,
                "lbl_val":     lbl_val,
                "max_val":     max(valor_inicial, 1),
                "display_val": valor_inicial,  # valor actualmente dibujado
                "target":      valor_inicial,  # valor destino de la animación
                "animating":   False,
            }

            # Dibujar barra inicial cuando el canvas tenga tamaño real
            canvas.bind("<Configure>",
                        lambda e, n=nombre, v=valor_inicial:
                        self._stat_draw_bar(n, v))

    def _stat_draw_bar(self, nombre: str, valor: int) -> None:
        """Dibuja la barra de progreso del atributo en su canvas."""
        if nombre not in self._stat_widgets:
            return
        info   = self._stat_widgets[nombre]
        canvas = info["canvas"]
        max_v  = info["max_val"]
        w      = canvas.winfo_width()
        h      = canvas.winfo_height()
        if w <= 1:
            return

        ratio      = max(0.0, min(1.0, valor / max_v))
        fill_w     = int(w * ratio)

        if ratio > 0.6:
            color = C["bar_high"]
        elif ratio > 0.3:
            color = C["bar_mid"]
        else:
            color = C["bar_low"]

        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, h, fill=C["bar_bg"], outline="")
        if fill_w > 0:
            canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")

    def _stats_update(self, nombre: str, valor: int) -> None:
        """Actualiza el número y arranca la animación de la barra."""
        if nombre not in self._stat_widgets:
            return
        info = self._stat_widgets[nombre]
        if valor > info["max_val"]:
            info["max_val"] = valor
        info["target"] = valor
        info["lbl_val"].config(text=str(valor))   # número actualiza al instante
        if not info["animating"]:
            self._stat_animate(nombre)

    def _stat_animate(self, nombre: str) -> None:
        """
        Avanza la barra un paso hacia el valor destino y se reprograma
        hasta llegar. Produce una animación fluida sin bloquear la UI.
        """
        if nombre not in self._stat_widgets:
            return
        info = self._stat_widgets[nombre]
        cur  = info["display_val"]
        tgt  = info["target"]

        if cur == tgt:
            info["animating"] = False
            return

        info["animating"] = True
        # Paso proporcional: ~8 frames para cualquier distancia
        step = max(1, abs(tgt - cur) // 8)
        if tgt > cur:
            cur = min(cur + step, tgt)
        else:
            cur = max(cur - step, tgt)

        info["display_val"] = cur
        self._stat_draw_bar(nombre, cur)
        self.after(25, lambda n=nombre: self._stat_animate(n))

    # =========================================================================
    # Paneles de stats de NPCs
    # =========================================================================

    def _setup_npc_panel(self, nombre: str, attrs: list,
                         rol: str = "neutral",
                         max_attrs: dict = None) -> None:
        """
        Crea un panel de stats para un NPC con colores según su rol.

        attrs     — valores actuales (lo que se muestra al aparecer el panel)
        max_attrs — valores iniciales declarados (definen el 100% de cada barra)
                    Si no se pasa, el 100% es el valor actual (comportamiento anterior)
        """
        if nombre in self._npc_panels:
            return   # ya existe

        # Paleta de colores y etiqueta según el rol del personaje
        _ROL_COLORES = {
            "enemigo": ("border_enemigo", "bg_enemigo", "title_enemigo", "ENEMIGO", "⚔"),
            "aliado":  ("border_aliado",  "bg_aliado",  "title_aliado",  "ALIADO",  "🤝"),
            "neutral": ("border_neutral", "bg_neutral", "title_neutral", "NPC",     "◆"),
        }
        c_border, c_bg, c_title, etiqueta, icono_rol = _ROL_COLORES.get(
            rol, _ROL_COLORES["neutral"]
        )

        # Separador visual (guardado para poder destruirlo al cambiar escena)
        sep = tk.Frame(self._stats_outer, bg=C[c_border], height=1)
        sep.pack(fill=tk.X, padx=4, pady=(4, 0))
        self._npc_seps.append(sep)

        # Marco del panel NPC
        npc_frame = tk.Frame(
            self._stats_outer,
            bg=C[c_bg],
            highlightthickness=1,
            highlightbackground=C[c_border],
        )
        npc_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        self._npc_panels[nombre] = npc_frame

        tk.Label(
            npc_frame,
            text=f"  {icono_rol}  {nombre.upper()}  ({etiqueta})",
            bg=C[c_bg], fg=C[c_title],
            font=FU_B, anchor="w", pady=3,
        ).pack(fill=tk.X, padx=4)

        rows_frame = tk.Frame(npc_frame, bg=C[c_bg])
        rows_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        self._npc_stat_widgets[nombre] = {}

        for attr_nombre, valor_inicial in attrs:
            icono = _ICONOS.get(attr_nombre, "◆")
            fila  = tk.Frame(rows_frame, bg=C[c_bg])
            fila.pack(fill=tk.X, pady=1)
            fila.columnconfigure(1, weight=1)

            tk.Label(
                fila, text=f"{icono} {attr_nombre}",
                bg=C[c_bg], fg=C["text"],
                font=FU, width=11, anchor="w",
            ).grid(row=0, column=0, padx=(0, 6))

            canvas = tk.Canvas(
                fila, height=12, bg=C["bar_bg"],
                highlightthickness=0,
            )
            canvas.grid(row=0, column=1, sticky="ew", padx=(0, 6))

            lbl_val = tk.Label(
                fila, text=str(valor_inicial),
                bg=C[c_bg], fg=C[c_title],
                font=FM, width=6, anchor="e",
            )
            lbl_val.grid(row=0, column=2)

            # max_val: valor declarado originalmente (100% de la barra).
            # Si el NPC ya perdió vida antes de aparecer, la barra lo refleja.
            max_v = max_attrs.get(attr_nombre, valor_inicial) if max_attrs else valor_inicial
            self._npc_stat_widgets[nombre][attr_nombre] = {
                "canvas":      canvas,
                "lbl_val":     lbl_val,
                "max_val":     max(max_v, 1),
                "display_val": valor_inicial,
                "target":      valor_inicial,
                "animating":   False,
            }

            canvas.bind(
                "<Configure>",
                lambda *_, p=nombre, a=attr_nombre, v=valor_inicial:
                self._npc_stat_draw_bar(p, a, v),
            )

    def _npc_stats_update(self, personaje: str, nombre: str, valor: int) -> None:
        """Actualiza número y arranca animación para un stat de NPC.
        max_val es fijo (valor declarado originalmente) y nunca se aumenta."""
        widgets = self._npc_stat_widgets.get(personaje, {})
        if nombre not in widgets:
            return
        info = widgets[nombre]
        info["target"] = valor
        info["lbl_val"].config(text=str(valor))
        if not info["animating"]:
            self._npc_stat_animate(personaje, nombre)

    def _npc_stat_draw_bar(self, personaje: str, nombre: str, valor: int) -> None:
        """Dibuja la barra de progreso de un stat de NPC."""
        widgets = self._npc_stat_widgets.get(personaje, {})
        if nombre not in widgets:
            return
        info   = widgets[nombre]
        canvas = info["canvas"]
        max_v  = info["max_val"]
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1:
            return
        ratio  = max(0.0, min(1.0, valor / max_v))
        fill_w = int(w * ratio)
        color  = C["bar_high"] if ratio > 0.6 else (
                 C["bar_mid"]  if ratio > 0.3 else C["bar_low"])
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, h, fill=C["bar_bg"], outline="")
        if fill_w > 0:
            canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")

    def _npc_stat_animate(self, personaje: str, nombre: str) -> None:
        """Anima la barra de un NPC hacia su valor destino."""
        widgets = self._npc_stat_widgets.get(personaje, {})
        if nombre not in widgets:
            return
        info = widgets[nombre]
        cur  = info["display_val"]
        tgt  = info["target"]
        if cur == tgt:
            info["animating"] = False
            return
        info["animating"] = True
        step = max(1, abs(tgt - cur) // 8)
        cur  = min(cur + step, tgt) if tgt > cur else max(cur - step, tgt)
        info["display_val"] = cur
        self._npc_stat_draw_bar(personaje, nombre, cur)
        self.after(25, lambda p=personaje, n=nombre: self._npc_stat_animate(p, n))

    def _clear_npc_panels(self) -> None:
        """Destruye todos los paneles NPC y limpia los dicts de estado."""
        for sep in self._npc_seps:
            sep.destroy()
        self._npc_seps.clear()
        for frame in self._npc_panels.values():
            frame.destroy()
        self._npc_panels.clear()
        self._npc_stat_widgets.clear()
        # El intérprete nuevo ya poblará _npc_initialized a través de su propio
        # InterpreteLoreGUI; aquí solo limpiamos la vista

    # =========================================================================
    # Área narrativa
    # =========================================================================

    def _narrative_clear(self) -> None:
        """Limpia la narrativa y cancela cualquier typewriter activo."""
        self._tw_stop()
        self._pending_seq.clear()
        self._narrative.config(state=tk.NORMAL)
        self._narrative.delete("1.0", tk.END)
        self._narrative.config(state=tk.DISABLED)

    def _narrative_insert(self, texto: str, tag: str = "narrative") -> None:
        """Inserta texto en la narrativa de forma instantánea (sin typewriter)."""
        self._narrative.config(state=tk.NORMAL)
        self._narrative.insert(tk.END, texto + "\n", tag)
        self._narrative.see(tk.END)
        self._narrative.config(state=tk.DISABLED)

    def _narrative_show_scene(self, nombre: str) -> None:
        """Inserta un encabezado de escena de forma instantánea."""
        self._narrative.config(state=tk.NORMAL)
        self._narrative.insert(tk.END, f"\n▸  {nombre.upper()}\n", "scene_hdr")
        self._narrative.insert(tk.END, "─" * 38 + "\n", "sep")
        self._narrative.see(tk.END)
        self._narrative.config(state=tk.DISABLED)
        self._status_scene.config(text=f"Escena: {nombre}  ")

    # ── Typewriter (máquina de escribir) ─────────────────────────────────────

    def _tw_enqueue(self, texto: str, tag: str = "narrative") -> None:
        """
        Inicia la escritura letra a letra del texto con el tag dado.
        Llama a _seq_done() automáticamente al terminar.
        """
        self._tw_busy  = True
        self._tw_chars = list(texto + "\n")
        self._tw_tag   = tag
        self._tw_idx   = 0
        self._tw_tick()

    def _tw_tick(self) -> None:
        """Escribe un carácter y se reprograma hasta terminar el texto."""
        if self._tw_idx >= len(self._tw_chars):
            # Texto completo → liberar y procesar siguiente mensaje
            self._seq_done()
            return
        ch = self._tw_chars[self._tw_idx]
        self._narrative.config(state=tk.NORMAL)
        self._narrative.insert(tk.END, ch, self._tw_tag)
        self._narrative.see(tk.END)
        self._narrative.config(state=tk.DISABLED)
        self._tw_idx  += 1
        self._tw_timer = self.after(self._tw_delay, self._tw_tick)

    def _tw_stop(self) -> None:
        """Cancela el typewriter y vuelca el resto del texto de golpe."""
        if self._tw_timer:
            self.after_cancel(self._tw_timer)
            self._tw_timer = None
        restante = "".join(self._tw_chars[self._tw_idx:])
        if restante:
            self._narrative.config(state=tk.NORMAL)
            self._narrative.insert(tk.END, restante, self._tw_tag)
            self._narrative.see(tk.END)
            self._narrative.config(state=tk.DISABLED)
        self._tw_chars = []
        self._tw_idx   = 0
        self._tw_busy  = False

    # =========================================================================
    # Panel de opciones (decisión interactiva)
    # =========================================================================

    def _options_show(self, opciones: list) -> None:
        """Crea los botones de opción y muestra el panel."""
        # Limpiar botones previos
        for w in self._options_btns_frame.winfo_children():
            w.destroy()

        for i, opcion in enumerate(opciones, 1):
            etiqueta = opcion.etiqueta[1:-1]   # quitar comillas
            btn = tk.Button(
                self._options_btns_frame,
                text=f"  [{i}]  {etiqueta}  ",
                command=lambda elec=i: self._option_clicked(elec),
                bg=C["btn_opt"], fg=C["text"],
                activebackground=C["btn_opt_hov"],
                activeforeground=C["text_gold"],
                font=FU_B, relief=tk.FLAT,
                padx=12, pady=8,
                cursor="hand2", anchor="w",
            )
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=C["btn_opt_hov"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=C["btn_opt"]))

        if not self._options_visible:
            self._options_outer.grid(row=2, column=0, sticky="ew",
                                     padx=6, pady=(3, 6))
            self._options_visible = True

    def _options_hide(self) -> None:
        """Oculta el panel de opciones."""
        if self._options_visible:
            self._options_outer.grid_forget()
            self._options_visible = False

    def _option_clicked(self, eleccion: int) -> None:
        """Envía la elección del jugador al hilo del intérprete."""
        self._options_hide()
        self._reply_queue.put(eleccion)

    # =========================================================================
    # Pipeline de compilación y ejecución
    # =========================================================================

    def _run_pipeline(self) -> None:
        """
        Ejecuta las 3 fases de compilación SIEMPRE completas y solo lanza
        el intérprete si ninguna fase produjo errores.

        Esto garantiza que el usuario ve TODOS los errores de una vez,
        sin tener que compilar varias veces para descubrirlos uno a uno.
        """
        # Detener ejecución previa si existe
        if self._ejecutando:
            self._stop_pipeline()
            self.after(300, self._run_pipeline)
            return

        fuente = self._editor.get("1.0", tk.END)

        self._console_clear()
        self._narrative_clear()
        self._options_hide()
        self._clear_npc_panels()
        self._set_status("Compilando…", C["con_warn"])

        # ── Fase 1: Léxico ───────────────────────────────────────────────────
        self._console_write("── Fase 1: Léxico " + "─" * 26, "phase")
        tokens, errs_lex = lex_analizar(fuente)
        n_tokens = sum(1 for t in tokens if t.tipo != "EOF")

        if errs_lex:
            for e in errs_lex:
                self._console_write(f"  ✗  {e}", "err")
            self._console_write(
                f"  {len(errs_lex)} error(es) léxico(s)  ·  "
                f"{n_tokens} token(s) reconocido(s)", "warn")
        else:
            self._console_write(f"  ✓  {n_tokens} token(s) reconocido(s)", "ok")

        # ── Fase 2: Sintáctico ───────────────────────────────────────────────
        # Se ejecuta siempre: el lexer tiene recuperación de errores y entrega
        # tokens válidos aunque haya errores léxicos.
        self._console_write("── Fase 2: Sintáctico " + "─" * 22, "phase")
        parser = Parser(tokens)
        ast, errs_sin, advertencias = parser.parsear()

        if advertencias:
            for adv in advertencias:
                self._console_write(f"  ⚠  {adv}", "warn")

        if errs_sin:
            for e in errs_sin:
                sev = "[FATAL] " if e.fatal else ""
                self._console_write(f"  ✗  {sev}{e}", "err")

        if ast:
            n_pers  = sum(1 for d in ast.declaraciones
                          if isinstance(d, NodoPersonaje))
            n_escen = len(ast.declaraciones) - n_pers
            self._console_write(
                f"  {'✗' if errs_sin else '✓'}  AST: "
                f"{n_pers} personaje(s)  ·  {n_escen} escena(s)",
                "err" if errs_sin else "ok")

        # ── Fase 3: Semántico ────────────────────────────────────────────────
        # Se ejecuta siempre: el parser devuelve un AST parcial incluso con
        # errores, suficiente para que el semántico reporte sus propios errores.
        self._console_write("── Fase 3: Semántico " + "─" * 23, "phase")
        semantico = AnalizadorSemantico()
        tabla, errs_sem = semantico.analizar(ast)

        if errs_sem:
            for e in errs_sem:
                self._console_write(f"  ✗  {e}", "err")
            self._console_write(
                f"  ✗  {len(errs_sem)} error(es) semántico(s)", "err")
        else:
            n_sim = len(tabla.personajes_declarados()) + \
                    len(tabla.escenas_declaradas())
            self._console_write(
                f"  ✓  {n_sim} símbolo(s)  ·  "
                f"{len(tabla.personajes_declarados())} personaje(s)  ·  "
                f"{len(tabla.escenas_declaradas())} escena(s)", "ok")

        # ── Decisión: ejecutar solo si no hay ningún error ───────────────────
        total_errores = len(errs_lex) + len(errs_sin) + len(errs_sem)
        if total_errores > 0:
            self._console_write(
                f"  ✗  {total_errores} error(es) en total — "
                f"corrígelos antes de ejecutar.", "err")
            self._set_status(
                f"{total_errores} error(es) — ejecución bloqueada",
                C["con_err"])
            return

        # ── Fase 4: Ejecución ────────────────────────────────────────────────
        self._console_write("── Ejecución " + "─" * 31, "phase")
        self._console_write("  ▶  Iniciando…", "run")

        self._btn_run.config(state=tk.DISABLED)
        self._btn_stop.config(state=tk.NORMAL)
        self._set_status("Ejecutando…", C["con_run"])
        self._ejecutando = True

        self._start_interp_thread(ast)

    def _stop_pipeline(self) -> None:
        """Detiene el hilo del intérprete limpiamente."""
        if not self._ejecutando:
            return
        self._stop_event.set()
        # Desbloquear _leer_opcion si está esperando
        self._reply_queue.put(None)
        # Cancelar typewriter y vaciar la cola secuencial
        self._tw_stop()
        self._pending_seq.clear()
        self._ejecutando = False
        self._btn_run.config(state=tk.NORMAL)
        self._btn_stop.config(state=tk.DISABLED)
        self._options_hide()
        self._set_status("Detenido", C["con_warn"])
        self._console_write("  ■  Ejecución detenida por el usuario.", "warn")

    def _start_interp_thread(self, ast) -> None:
        """Lanza el intérprete en un hilo secundario."""
        self._stop_event.clear()
        # Drenar colas antes de empezar
        while not self._ui_queue.empty():
            try: self._ui_queue.get_nowait()
            except queue.Empty: break
        while not self._reply_queue.empty():
            try: self._reply_queue.get_nowait()
            except queue.Empty: break

        interp = InterpreteLoreGUI(
            ast, self._ui_queue, self._reply_queue, self._stop_event
        )

        def _run_safe():
            try:
                interp.ejecutar()
            except _PararEjecucion:
                pass
            except Exception as exc:
                self._ui_queue.put(("error_ejec", str(exc)))

        self._interp_thread = threading.Thread(
            target=_run_safe, daemon=True
        )
        self._interp_thread.start()

    # =========================================================================
    # Sistema de cola UI (recibe mensajes del hilo del intérprete)
    # =========================================================================

    def _start_queue_poll(self) -> None:
        self._poll_ui_queue()

    def _poll_ui_queue(self) -> None:
        """
        Drena la ui_queue en cada tick (40ms).
        - Mensajes inmediatos (stat, setup_stats): se aplican al instante.
        - Mensajes secuenciales: van a _pending_seq y se procesan uno a uno,
          esperando a que el typewriter termine antes del siguiente.
        """
        try:
            while True:
                msg = self._ui_queue.get_nowait()
                if msg[0] in ("stat", "setup_stats", "stat_npc"):
                    self._handle_immediate(msg)
                else:
                    self._pending_seq.append(msg)
        except queue.Empty:
            pass

        self._process_pending()
        self.after(40, self._poll_ui_queue)

    def _handle_immediate(self, msg: tuple) -> None:
        """Mensajes que no necesitan esperar al typewriter."""
        action = msg[0]
        if action == "stat":
            self._stats_update(msg[1], msg[2])
        elif action == "setup_stats":
            self._stats_setup(msg[1], msg[2])
        elif action == "stat_npc":
            self._npc_stats_update(msg[1], msg[2], msg[3])

    def _process_pending(self) -> None:
        """Si el typewriter está libre y hay mensajes esperando, procesa el siguiente."""
        if not self._tw_busy and self._pending_seq:
            self._handle_sequential(self._pending_seq.popleft())

    def _seq_done(self) -> None:
        """Llamado cuando un paso secuencial termina (typewriter o acción instantánea)."""
        self._tw_busy = False
        self._process_pending()

    def _handle_sequential(self, msg: tuple) -> None:
        """
        Procesa un mensaje secuencial.
        Acciones de texto usan typewriter (_tw_enqueue) y llaman _seq_done al final.
        Acciones instantáneas llaman _seq_done() inmediatamente.
        """
        action = msg[0]

        if action == "escena":
            # Al entrar a una nueva escena: destruir paneles NPC previos.
            # Solo reaparecerán los NPCs que actúen en esta escena.
            self._clear_npc_panels()
            self._narrative_show_scene(msg[1])
            self._seq_done()

        elif action == "setup_npc":
            # Crear panel NPC en orden secuencial (después del clear de escena)
            # msg = ("setup_npc", nombre, attrs, rol, max_attrs)
            rol       = msg[3] if len(msg) > 3 else "neutral"
            max_attrs = msg[4] if len(msg) > 4 else {}
            self._setup_npc_panel(msg[1], msg[2], rol, max_attrs)
            self._seq_done()

        elif action == "texto":
            # Texto narrativo: typewriter
            self._tw_enqueue(msg[1], "narrative")

        elif action == "stat_cambio":
            # Cambio de stat del héroe: typewriter con color según delta
            _, nombre, prev, nuevo = msg
            delta = nuevo - prev
            icono = _ICONOS.get(nombre, "◆")
            if delta < 0:
                texto = f"{icono} {nombre}  {prev} → {nuevo}  ({delta})"
                tag   = "stat_baja"
            else:
                texto = f"{icono} {nombre}  {prev} → {nuevo}  (+{delta})"
                tag   = "stat_sube"
            self._tw_enqueue(texto, tag)

        elif action == "stat_cambio_npc":
            # Cambio de stat de un NPC: igual pero con prefijo del nombre
            _, personaje, nombre, prev, nuevo = msg
            delta = nuevo - prev
            icono = _ICONOS.get(nombre, "◆")
            prefijo = f"[{personaje.upper()}] "
            if delta < 0:
                texto = f"{prefijo}{icono} {nombre}  {prev} → {nuevo}  ({delta})"
                tag   = "stat_baja"
            else:
                texto = f"{prefijo}{icono} {nombre}  {prev} → {nuevo}  (+{delta})"
                tag   = "stat_sube"
            self._tw_enqueue(texto, tag)

        elif action == "opciones":
            # Botones de decisión: aparecen solo cuando el texto anterior terminó
            self._options_show(msg[1])
            self._seq_done()

        elif action == "fin":
            self._narrative_insert("\n── Fin de la aventura ──", "sep")
            self._set_status("Fin de la aventura  ·  ¡Gracias por jugar!",
                             C["con_ok"])
            self._console_write("  ✓  Historia completada.", "ok")
            self._on_ejecucion_terminada()
            self._seq_done()

        elif action == "error_ejec":
            self._narrative_insert(f"\n✗ ERROR: {msg[1]}", "narr_error")
            self._console_write(f"  ✗  Error de ejecución: {msg[1]}", "err")
            self._set_status("Error de ejecución", C["con_err"])
            self._on_ejecucion_terminada()
            self._seq_done()

        elif action == "warn_ejec":
            self._console_write(f"  ⚠  {msg[1]}", "warn")
            self._seq_done()

    def _on_ejecucion_terminada(self) -> None:
        """Restaura botones al terminar la ejecución (normal o por error)."""
        self._ejecutando = False
        self._btn_run.config(state=tk.NORMAL)
        self._btn_stop.config(state=tk.DISABLED)
        self._options_hide()

    # =========================================================================
    # Barra de estado
    # =========================================================================

    def _set_status(self, texto: str, color: str = None) -> None:
        color = color or C["text_dim"]
        self._status_lbl.config(text=f"  {texto}", fg=color)

    # =========================================================================
    # Operaciones de archivo
    # =========================================================================

    def _abrir_archivo(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Abrir historia LoreEngine",
            filetypes=[("LoreEngine", "*.lore"), ("Texto", "*.txt"),
                       ("Todos", "*.*")],
        )
        if not ruta:
            return
        self._abrir_ruta(ruta)

    def _abrir_ruta(self, ruta: str) -> None:
        """Carga un archivo desde una ruta conocida (usado también por sys.argv)."""
        try:
            with open(ruta, encoding="utf-8") as f:
                contenido = f.read()
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{exc}")
            return

        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", contenido)
        self._update_line_numbers()
        self._highlight_syntax()
        self._archivo_actual = ruta
        self.title(f"LoreEngine IDE  ·  {os.path.basename(ruta)}")
        self._set_status(f"Abierto: {os.path.basename(ruta)}")

    def _guardar_archivo(self) -> None:
        if not self._archivo_actual:
            ruta = filedialog.asksaveasfilename(
                title="Guardar historia",
                defaultextension=".lore",
                filetypes=[("LoreEngine", "*.lore"), ("Texto", "*.txt")],
            )
            if not ruta:
                return
            self._archivo_actual = ruta

        try:
            contenido = self._editor.get("1.0", tk.END)
            with open(self._archivo_actual, "w", encoding="utf-8") as f:
                f.write(contenido)
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo guardar:\n{exc}")
            return

        self.title(f"LoreEngine IDE  ·  {os.path.basename(self._archivo_actual)}")
        self._set_status(f"Guardado: {os.path.basename(self._archivo_actual)}")

    # =========================================================================
    # Cierre de ventana
    # =========================================================================

    def _on_close(self) -> None:
        """Confirma cierre y detiene el hilo del intérprete si está activo."""
        if self._ejecutando:
            self._stop_pipeline()
        self.destroy()


# =============================================================================
# Historia de ejemplo cargada al iniciar el IDE
# =============================================================================

_EJEMPLO_INICIAL = """\
personaje principal cazador {
    vida   = 100
    oro    = 25
    fuerza = 38
}

personaje enemigo lobo {
    vida   = 55
    fuerza = 22
}

personaje enemigo brujo {
    vida   = 90
    fuerza = 45
}

escena aldea {
    mostrar "La aldea de Mirhen esta cubierta de niebla desde hace tres dias."
    mostrar "Los habitantes no salen de sus casas. Las bestias rondan de noche."
    mostrar "El alcalde te convoca: alguien tiene que limpiar el bosque maldito."
    mostrar "Te equipan con lo que tienen y senalan el camino al norte."
    decision {
        "Internarte de inmediato por el sendero del bosque" -> sendero
        "Preguntar al herrero sobre las criaturas primero"  -> herrero
    }
}

escena herrero {
    mostrar "El herrero es un hombre viejo con manos como rocas."
    mostrar "Dice que el brujo Kael controla a las bestias desde su torre."
    mostrar "Kael fue desterrado hace diez anos. Ha vuelto con rencor."
    mostrar "El herrero te regala un amuleto de proteccion y diez monedas."
    oro    = oro + 10
    fuerza = fuerza + 5
    mostrar "Con el amuleto puesto sientes una corriente calida en el pecho."
    decision {
        "Avanzar por el sendero del bosque" -> sendero
        "Buscar la cueva del contrabandista" -> cueva
    }
}

escena sendero {
    mostrar "El sendero entre los robles huele a tierra mojada y peligro."
    mostrar "A mitad del camino el lobo negro aparece entre los arboles."
    mostrar "Sus ojos son amarillos. Gruye en voz baja."
    mostrar "Lanzas el primer ataque."
    lobo.vida  = lobo.vida - fuerza
    lobo.vida  = lobo.vida - dado(12)
    si lobo.vida > 20 {
        mostrar "El lobo encaja el golpe y contraataca con furia."
        vida = vida - dado(18)
        mostrar "Sus garras te rasgaron el hombro. Duele, pero sigues en pie."
        decision {
            "Seguir el combate hasta el final"      -> combate_lobo
            "Huir hacia la cueva del contrabandista" -> cueva
        }
    } sino {
        mostrar "El lobo cae con un aullido. La primera amenaza eliminada."
        mostrar "Encuentra un collar con monedas entre su pelaje. Raro."
        oro = oro + 8
        decision {
            "Continuar hacia el claro del bosque" -> claro
            "Explorar la cueva cercana primero"   -> cueva
        }
    }
}

escena combate_lobo {
    mostrar "El lobo acorrala. No hay escapatoria."
    mostrar "Respiras hondo y atacas con todo."
    lobo.vida  = lobo.vida - fuerza
    vida       = vida - dado(15)
    si lobo.vida > 0 {
        lobo.vida = lobo.vida - dado(20)
        mostrar "Dos golpes mas y el lobo finalmente cede."
        mostrar "Colapsa en el sendero jadeando. Ya no es una amenaza."
        oro = oro + 5
    } sino {
        mostrar "Un solo golpe certero lo derriba."
        mostrar "La bestia cae. El sendero vuelve a ser tuyo."
    }
    fuerza = fuerza + 3
    mostrar "La lucha te ha templado. Te sientes mas fuerte."
    decision {
        "Avanzar al claro del bosque"      -> claro
        "Rodear y buscar la cueva primero" -> cueva
    }
}

escena cueva {
    mostrar "La cueva del contrabandista huele a vino agrio y madera podrida."
    mostrar "Hay cajones apilados hasta el techo. Toneles. Sacos de harina."
    mostrar "Y en el fondo, una caja de herramientas con una nota encima."
    mostrar "La nota dice: Kael pago por nuestro silencio. No busques mas."
    oro = oro + 30
    mostrar "Debajo de los sacos encuentras las monedas del contrabandista."
    si fuerza > 40 {
        mostrar "Eres lo bastante fuerte para mover los toneles y hallar su escondite."
        fuerza = fuerza + 8
        mostrar "Detras hay una espada corta bien afilada. La tomas."
    } sino {
        mostrar "Los toneles son demasiado pesados. Dejas la cueva con el oro."
    }
    decision {
        "Ir al claro a enfrentar al brujo"      -> claro
        "Volver al sendero y buscar otro camino" -> sendero_alt
    }
}

escena sendero_alt {
    mostrar "Tomas un sendero secundario que bordea el rio negro."
    mostrar "El agua refleja la torre del brujo a lo lejos."
    mostrar "En la orilla encuentras una pocion de hierba de luna."
    vida = vida + 20
    mostrar "Al beberla sientes como tus heridas se cierran lentamente."
    mostrar "El camino desemboca en el claro central del bosque."
    decision {
        "Entrar al claro" -> claro
    }
}

escena claro {
    mostrar "El claro es un circulo perfecto. Los arboles no crecen en el borde."
    mostrar "En el centro, la torre de piedra negra de Kael se eleva en la niebla."
    mostrar "La puerta esta abierta. Una trampa, claramente."
    brujo.fuerza = brujo.fuerza + dado(8)
    mostrar "Desde arriba, la voz del brujo Kael resuena como trueno."
    mostrar "Dice: Solo un necio entra a mi torre sin ser invitado."
    decision {
        "Entrar por la puerta principal"           -> torre_entrada
        "Buscar una ventana en el lado trasero"    -> torre_flanco
        "Intentar negociar desde afuera"           -> negociacion
    }
}

escena negociacion {
    mostrar "Gritas que vienes en nombre de la aldea de Mirhen."
    mostrar "Un silencio largo. Luego la voz del brujo de nuevo."
    si oro > 50 {
        mostrar "El brujo acepta hablar. El precio: cincuenta monedas."
        oro = oro - 50
        mostrar "La puerta se abre sola. Subes al salon sin resistencia."
        mostrar "Kael te escucha. Dice que se marchara si destruyes el contrato."
        mostrar "En el suelo hay un pergamino con su firma."
        mostrar "Lo quemas. El brujo cumple su palabra y desaparece en humo."
        decision {
            "Volver a la aldea con las buenas noticias" -> final_diplomatico
        }
    } sino {
        mostrar "Kael rie. Dice que no tienes suficiente para comprar su piedad."
        mostrar "Lanza un rayo desde la ventana que astilla el suelo a tus pies."
        vida = vida - dado(12)
        mostrar "La negociacion ha fracasado. Solo queda el combate."
        decision {
            "Entrar por la fuerza" -> torre_entrada
            "Flanquear por atras"  -> torre_flanco
        }
    }
}

escena torre_flanco {
    mostrar "Rodeas la torre en silencio. El musgo amortigua tus pasos."
    mostrar "Una ventana baja. Subes con cuidado."
    mostrar "Aterrizas en una biblioteca. Estantes de libros prohibidos."
    fuerza = fuerza + 5
    mostrar "Hojeas uno rapidamente. Aprendes un truco de combate."
    mostrar "Escuchas pasos arriba. El brujo sabe que estas aqui."
    decision {
        "Subir las escaleras a enfrentarlo" -> combate_brujo
        "Buscar un arma magica en la biblioteca" -> biblioteca
    }
}

escena biblioteca {
    mostrar "Los libros contienen hechizos pero tu no eres mago."
    mostrar "Sin embargo encuentras un baston de roble reforzado en plata."
    fuerza = fuerza + 12
    mostrar "El baston vibra en tu mano. Esta cargado de energia residual."
    mostrar "Oyes al brujo bajar las escaleras. Ya no tienes tiempo."
    decision {
        "Enfrentarlo aqui en la biblioteca" -> combate_brujo
    }
}

escena torre_entrada {
    mostrar "Entras por la puerta principal. El salon esta lleno de niebla."
    mostrar "Velas que flotan sin soporte. Cuadros de personas que te miran."
    mostrar "Al fondo de la escalera de caracol, el brujo Kael desciende."
    mostrar "Tiene el pelo blanco y los ojos de un color que no existe."
    mostrar "Dice: Pensaba que tardarias mas. Vamos a terminar con esto."
    vida = vida - dado(10)
    mostrar "Una rafaga magica te alcanza antes de que puedas esquivar."
    decision {
        "Subir a su nivel y atacar cuerpo a cuerpo" -> combate_brujo
        "Usar el entorno: tirar una vela sobre los libros" -> trampa_fuego
    }
}

escena trampa_fuego {
    mostrar "Derramas aceite de una lampara y lanzas una vela."
    mostrar "El fuego prende en los tapices. El brujo se distrae."
    brujo.vida = brujo.vida - 25
    mostrar "Aprovechas la confusion y lo golpeas por la espalda."
    mostrar "Kael ruge de dolor. Pero no cae."
    decision {
        "Continuar el ataque directo" -> combate_brujo
    }
}

escena combate_brujo {
    mostrar "El combate con Kael llena la torre de relámpagos y polvo."
    brujo.vida  = brujo.vida - fuerza
    brujo.vida  = brujo.vida - dado(15)
    vida        = vida - brujo.fuerza
    si brujo.vida > 35 {
        mostrar "Kael resiste. Su magia te repele con fuerza brutal."
        vida = vida - dado(20)
        si vida > 30 {
            mostrar "Estas malherido pero en pie. Un ultimo esfuerzo."
            decision {
                "Atacar sin detenerte" -> golpe_final
                "Retirarte a recuperarte" -> sendero_alt
            }
        } sino {
            mostrar "Apenas puedes mantenerte en pie. El brujo levanta la mano."
            mostrar "Sientes que todo se acaba."
            decision {
                "Resistir con lo que queda" -> golpe_final
                "Rendirte" -> derrota
            }
        }
    } sino {
        mostrar "Kael esta debilitado. La magia se le escapa de las manos."
        decision {
            "Asestar el golpe definitivo" -> golpe_final
            "Exigirle que se rinda"       -> rendicion_brujo
        }
    }
}

escena rendicion_brujo {
    mostrar "Kael cae de rodillas. Su orgullo se quiebra como cristal."
    mostrar "Dice: Esta bien. Me marcho. Mirhen nunca mas me vera."
    mostrar "A cambio pide que no destruyas sus libros."
    si fuerza > 50 {
        mostrar "No te fias. Lo amarras y tomas todo lo de valor."
        oro    = oro + 60
        fuerza = fuerza + 5
        mostrar "Los libros magicos vendran bien en la ciudad."
    } sino {
        mostrar "Aceptas el trato. El brujo desaparece dejando una nube de humo azul."
        oro = oro + 40
        mostrar "Deja atras una bolsa de monedas como gesto de buena voluntad."
    }
    decision {
        "Regresar a la aldea" -> final_victorioso
    }
}

escena golpe_final {
    mostrar "Con toda la fuerza que te queda lanzas el ataque decisivo."
    brujo.vida  = brujo.vida - fuerza
    brujo.vida  = brujo.vida - dado(30)
    vida        = vida - dado(8)
    si brujo.vida > 0 {
        mostrar "Kael usa sus ultimas energias para contraatacar."
        mostrar "La explosion te lanza contra la pared. Sientes huesos crujir."
        vida = vida - 25
        si vida > 0 {
            mostrar "Pero el brujo tambien cayo. La batalla ha terminado."
            oro    = oro + 70
            fuerza = fuerza + 10
            decision {
                "Salir de la torre hacia la aldea" -> final_victorioso
            }
        } sino {
            decision {
                "Ver el desenlace final" -> derrota
            }
        }
    } sino {
        mostrar "Kael colapsa. La magia se disipa. La niebla empieza a levantarse."
        mostrar "Del bolsillo del brujo cae una bolsa pesada de monedas."
        oro    = oro + 70
        fuerza = fuerza + 10
        decision {
            "Abandonar la torre y volver a Mirhen" -> final_victorioso
        }
    }
}

escena derrota {
    mostrar "Las fuerzas te abandonan en el suelo de piedra fria."
    mostrar "Kael te mira desde arriba sin emocion."
    mostrar "Dice: Vuelve cuando seas digno de este desafio."
    mostrar "La niebla sigue sobre Mirhen. Tu aventura termina aqui."
    mostrar "Pero en alguna taberna, alguien contara tu historia."
    mostrar "Y otro cazador se levantara para intentarlo."
}

escena final_diplomatico {
    mostrar "El brujo ha desaparecido. La niebla se levanta lentamente."
    mostrar "Los aldeanos salen a la calle por primera vez en dias."
    mostrar "El alcalde te abraza. Los ninos corren entre las casas."
    mostrar "Resolviste el problema sin derramar sangre. Eso es sabiduria."
    si oro > 60 {
        mostrar "Ademas llevas suficiente oro para vivir un ano sin trabajar."
        mostrar "Te quedas en Mirhen una semana. La gente te trata como a un heroe."
    } sino {
        mostrar "No eres rico, pero eres respetado. Hay peores recompensas."
    }
    mostrar "Las Tierras de Mirhen son libres de nuevo. Gracias a ti."
}

escena final_victorioso {
    mostrar "Sales de la torre con el amanecer a tus espaldas."
    mostrar "La niebla se disuelve sobre el bosque. Los pajaros vuelven a cantar."
    mostrar "En la aldea te reciben con antorchas y canciones."
    si vida > 60 {
        mostrar "Llegas en pie, con heridas leves. Un autentico cazador de bestias."
    } sino {
        mostrar "Llegas malherido pero con la cabeza alta. Lo conseguiste."
    }
    si oro > 80 {
        mostrar "Y con los bolsillos llenos de oro. Una noche redonda."
        mostrar "El alcalde organiza un banquete en tu honor."
        mostrar "Los bardos ya componen la balada del cazador de Mirhen."
    } sino {
        mostrar "El oro escasea pero el honor sobra. Te invitan a quedarte."
    }
    si fuerza > 55 {
        mostrar "Ademas, cada batalla te hizo mas fuerte."
        mostrar "Eres ahora una leyenda viva en estas tierras."
    }
    mostrar "Mirhen respira libre. El brujo Kael no volvera."
    mostrar "Y si vuelve, saben a quien llamar."
}
"""


# =============================================================================
# Punto de entrada
# =============================================================================

def main() -> None:
    """Lanza el IDE gráfico de LoreEngine.
    Si se pasa una ruta como argumento (ej: al hacer doble clic en un .lore),
    abre ese archivo automáticamente al iniciar.
    """
    app = LoreEngineIDE()
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
        if os.path.isfile(ruta):
            # after(0) garantiza que la ventana esté completamente inicializada
            app.after(0, lambda: app._abrir_ruta(ruta))
    app.mainloop()


if __name__ == "__main__":
    main()
