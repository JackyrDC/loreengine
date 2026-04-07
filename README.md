<div style="background-color: #001a4d; padding: 40px 20px; border-radius: 10px; text-align: center; margin-bottom: 40px; border: 2px solid #0066ff;">
  <img src="assets/img/logo.svg" alt="LoreEngine Logo" width="280" height="280" style="margin-bottom: 20px;">
  <h1 style="color: #00d4ff; margin: 20px 0 10px 0; font-size: 2.5em;">LoreEngine</h1>
  <p style="color: #b0b0b0; margin: 10px 0; font-size: 1.1em;">Un lenguaje de dominio específico para crear experiencias narrativas interactivas</p>
  <p style="color: #0066ff; margin: 15px 0 0 0;">
    <a href="README.es.md" style="color: #00d4ff; text-decoration: none; margin: 0 15px; font-weight: bold;">Español</a> •
    <a href="README.en.md" style="color: #0066ff; text-decoration: none; margin: 0 15px; font-weight: bold;">English</a>
  </p>
</div>

---

## Descripción Breve

LoreEngine es un lenguaje de programación diseñado específicamente para desarrollar historias interactivas. Permite definir personajes con atributos dinámicos, escenas narrativas y decisiones ramificadas que el jugador puede tomar. El lenguaje combina la simplicidad de una sintaxis declarativa con el poder de la lógica procedural.

**Características principales:**
- Declaración intuitiva de personajes y atributos
- Gestión de escenas y flujo narrativo
- Sistema de decisiones ramificadas
- Operadores matemáticos y de comparación
- Números aleatorios mediante la función `dado(n)`
- Pipeline de compilación de 4 fases (léxico, sintáctico, semántico, ejecución)

**Ejemplo rápido:**

```lore
personaje principal Aventurero {
  salud: 100
  mana: 50
}

escena Inicio {
  mostrar "Bienvenido, aventurero."
  mostrar "Tu salud: " + Aventurero.salud
}
```

**Línea de comandos:**

```bash
python main_consola.py historia.lore
```

---

## Estructura de Archivos

- `README.md` (este archivo) - Índice multilingüe
- `README.es.md` - Documentación completa en español
- `README.en.md` - Complete English documentation
- `lexer_loreengine.py` - Analizador léxico
- `parser_loreengine.py` - Analizador sintáctico
- `semantico_loreengine.py` - Analizador semántico
- `interprete_loreengine.py` - Intérprete
- `symbol_table.py` - Tabla de símbolos
- `ast_nodes.py` - Definición de nodos AST
- `main_consola.py` - Interfaz de línea de comandos
- `main_gui.py` - Interfaz gráfica

---

## Requisitos

- Python 3.7 o superior
- Ninguna dependencia externa

---

## Instalación Rápida

```bash
cd loreengine
python main_consola.py
```

---

## Créditos

**Curso:** Diseño de Compiladores (IS-913)  
**Universidad:** UNAH-COMAYAGUA

---

**Para documentación completa, selecciona tu idioma arriba.**

---

## Visión General del Lenguaje

### Filosofía de Diseño

LoreEngine se construye sobre los siguientes principios:

- **Narrativa primero**: La sintaxis prioriza la estructura de la historia sobre la implementación técnica
- **Declarativa**: Los personajes y escenas se declaran una sola vez y se referencian en todo el programa
- **Interactiva**: Soporte integrado para opciones del jugador e historias ramificadas
- **Fuertemente tipada**: Sistema de tipos limitado pero bien definido (enteros, cadenas, atributos)
- **Ejecución determinista**: Los programas se compilan a través de cuatro fases distintas antes de ejecutarse

### Conceptos Centrales

El lenguaje organiza las narrativas alrededor de tres conceptos fundamentales:

- **Personajes (Personajes)**: Entidades nombradas con atributos que evolucionan durante el juego
- **Escenas (Escenas)**: Contextos narrativos donde se ejecutan diálogos y lógica
- **Decisiones (Decisiones)**: Opciones del jugador que determinan el flujo narrativo

---

## Instalación y Configuración

### Requisitos

- Python 3.7 o superior
- Windows, macOS o Linux

### Instrucciones de Instalación

1. Navega al directorio de LoreEngine:
   ```
   cd loreengine
   ```

2. No se requieren dependencias externas. Todos los módulos se implementan utilizando la biblioteca estándar de Python.

3. Verifica la instalación comprobando la presencia de estos archivos centrales:
   - `lexer_loreengine.py`
   - `parser_loreengine.py`
   - `semantico_loreengine.py`
   - `interprete_loreengine.py`

---

## Primeros Pasos

### Ejecutando tu Primer Programa

#### Modo Consola

Ejecuta un programa de LoreEngine en la consola:

```bash
python main_consola.py historia.lore
```

O ejecuta el ejemplo integrado:

```bash
python main_consola.py
```

#### Modo GUI

Para una interfaz gráfica:

```bash
python main_gui.py
```

### Ejemplo Mínimo

Crea un archivo llamado `historia.lore` con el siguiente contenido:

```lore
personaje Protagonista {
  energía: 100
}

escena Inicio {
  mostrar "Bienvenido a la aventura."
  mostrar "Tu energía: " + Protagonista.energía
}
```

Ejecútalo:

```bash
python main_consola.py historia.lore
```

---

## Conceptos del Lenguaje

### Personajes (Personajes)

Los personajes son la base de cualquier narrativa de LoreEngine. Cada personaje tiene un nombre único y un conjunto de atributos que definen su estado.

#### Declaración de Personajes

```lore
personaje NombreDelPersonaje {
  atributo1: valor_inicial
  atributo2: valor_inicial
  ...
}
```

#### Roles de Personajes

Los personajes pueden tener modificadores de rol:

- `principal`: El protagonista o agente principal (solo uno por programa)
- `enemigo`: Un NPC hostil o personaje adversario
- `aliado`: Un personaje aliado

#### Acceso a Atributos

Los atributos se acceden utilizando notación de punto:

```lore
Personaje.atributo
```

### Escenas (Escenas)

Las escenas definen contextos narrativos donde se desarrolla la historia. Cada escena contiene una secuencia de sentencias que se ejecutan en orden.

#### Declaración de Escenas

```lore
escena NombreDeLaEscena {
  sentencia_1
  sentencia_2
  ...
}
```

#### Ejecución de Escenas

Las escenas se ejecutan secuencialmente a menos que sean interrumpidas por una decisión que ramifique a otra escena.

### Decisiones y Opciones

Las decisiones presentan a los jugadores opciones que determinan el flujo narrativo. Cada decisión ramifica a exactamente una siguiente escena basada en la selección del jugador.

#### Sintaxis de Decisiones

```lore
decision NombreDeLaDecision {
  opción "Texto de opción 1" -> EscenaSiguiente1
  opción "Texto de opción 2" -> EscenaSiguiente2
  opción "Texto de opción 3" -> EscenaSiguiente3
}
```

Cuando se ejecuta una decisión, el jugador selecciona una opción y el programa ramifica a la escena correspondiente. El resto de las sentencias de la escena se omiten.

---

## Referencia de Sintaxis

### Sentencias

#### Sentencia de Impresión (mostrar)

Muestra texto al jugador. Acepta expresiones que evalúan a cadenas o números.

```lore
mostrar "Texto fijo"
mostrar variable
mostrar "Calculado: " + valor
mostrar personaje.atributo
```

#### Asignación

Asigna un valor a una variable o atributo de personaje.

```lore
variable = expresión
personaje.atributo = expresión
```

#### Sentencia Condicional (si)

Ejecuta sentencias condicionalmente basadas en una expresión booleana.

```lore
si condición {
  sentencia_1
  sentencia_2
}

si condición {
  sentencia_1
}
sino {
  sentencia_2
}
```

#### Sentencia de Casos (dado)

Ejecuta diferentes bloques de sentencias basados en qué condición es verdadera. Si ninguna condición coincide y existe un bloque por defecto (`sino`), se ejecuta; de lo contrario, no sucede nada.

```lore
dado {
  si condición1 {
    bloque_sentencias_1
  }
  si condición2 {
    bloque_sentencias_2
  }
  sino {
    bloque_por_defecto
  }
}
```

### Expresiones

#### Literales

- **Entero**: `42`, `-15`, `0`
- **Cadena**: `"Texto entrecomillado"`

#### Operadores

##### Operadores Aritméticos

| Operador | Operación | Ejemplo |
|----------|-----------|---------|
| `+` | Suma o Concatenación de Cadenas | `5 + 3` = `8` |
| `-` | Resta | `10 - 4` = `6` |
| `*` | Multiplicación | `3 * 7` = `21` |
| `/` | División Entera | `15 / 3` = `5` |

##### Operadores Relacionales

| Operador | Significado | Ejemplo |
|----------|-------------|---------|
| `==` | Igual | `x == 5` |
| `!=` | No igual | `x != 0` |
| `<` | Menor que | `x < 10` |
| `>` | Mayor que | `x > 0` |
| `<=` | Menor o igual | `x <= 100` |
| `>=` | Mayor o igual | `x >= 50` |

#### Precedencia de Operadores

Las operaciones siguen la precedencia matemática estándar, de mayor a menor:

1. Paréntesis `( )`
2. Multiplicación `*`, División `/`
3. Suma `+`, Resta `-`

```lore
mostrar 2 + 3 * 4      // imprime 14, no 20
mostrar (2 + 3) * 4    // imprime 20
```

#### Concatenación de Cadenas

Las cadenas se concatenan utilizando el operador `+`:

```lore
mostrar "El jugador tiene " + puntos + " puntos"
```

---

## Sistema de Tipos

LoreEngine implementa un sistema de tipos simple pero explícito:

### Tipo Entero

Todos los valores numéricos son enteros (32-bit con signo).

```lore
edad: 25
salud: 100
```

### Tipo Cadena

Las cadenas son secuencias de caracteres encerradas en comillas dobles.

```lore
nombre: "Aragorn"
mostrar "Hola, mundo"
```

### Atributos

Los atributos de personajes se tipan en la declaración y retienen su tipo durante toda la ejecución.

```lore
personaje Mago {
  inteligencia: 18
  mana: 50
}
```

### Seguridad de Tipos

El analizador semántico valida:

- Todas las referencias de variables se refieren a variables declaradas
- Los accesos a atributos de personajes son válidos
- Las expresiones en condiciones están correctamente tipadas
- Sin conflictos de nombres de atributos dentro de un personaje

---

## Funciones Estándar

### Generación de Números Aleatorios

La función `dado(n)` devuelve un entero aleatorio de 1 a n (inclusive).

#### Sintaxis

```lore
dado(valor_máximo)
```

#### Ejemplo

```lore
mostrar "Tirada de d20: " + dado(20)
```

#### Comportamiento

- `dado(6)` devuelve un entero aleatorio entre 1 y 6
- `dado(100)` devuelve un entero aleatorio entre 1 y 100
- Solo se soportan enteros positivos

---

## Ejemplos

### Ejemplo 1: Historia Simple

```lore
personaje Aventurero {
  salud: 100
  mana: 50
}

escena Inicio {
  mostrar "Eres un aventurero en un mundo peligroso."
  mostrar "Tu salud: " + Aventurero.salud
  mostrar "Tu mana: " + Aventurero.mana
}
```

### Ejemplo 2: Historia Interactiva con Decisiones

```lore
personaje principal Heroe {
  coraje: 50
  inteligencia: 60
}

escena Bosque {
  mostrar "Te encuentras en un bosque oscuro."
  mostrar "Escuchas un rugido."
}

escena Lucha {
  mostrar "¡Atacas al monstruo valientemente!"
  Heroe.coraje = Heroe.coraje + 10
  mostrar "Tu coraje aumentó a " + Heroe.coraje
}

escena Huida {
  mostrar "Corres lo más rápido que puedes."
  Heroe.coraje = Heroe.coraje - 5
  mostrar "Tu coraje disminuyó a " + Heroe.coraje
}

decision Encuentro {
  opción "Luchar" -> Lucha
  opción "Huir" -> Huida
}
```

### Ejemplo 3: Lógica Condicional

```lore
personaje Comerciante {
  oro: 100
}

escena Mercado {
  Comerciante.oro = Comerciante.oro + 50
  
  si Comerciante.oro > 150 {
    mostrar "Tienes dinero suficiente para comprar un arma."
  }
  sino {
    mostrar "Necesitas más dinero."
  }
}
```

### Ejemplo 4: Sistema de Combate con Resultados Aleatorios

```lore
personaje Guerrero {
  fuerza: 15
  vida: 80
}

escena Batalla {
  mostrar "Comienzo del combate..."
  mostrar "Tu fuerza es: " + Guerrero.fuerza
  
  dado {
    si dado(100) < 50 {
      mostrar "¡Golpe crítico!"
      Guerrero.fuerza = Guerrero.fuerza + 5
    }
    sino {
      mostrar "Ataque normal."
    }
  }
  
  mostrar "Tu fuerza ahora es: " + Guerrero.fuerza
}
```

---

## Pipeline de Compilación

Los programas de LoreEngine se compilan a través de cuatro fases distintas antes de ejecutarse. Cada fase se construye sobre la anterior.

### Fase 1: Análisis Léxico (Léxico)

El lexer tokeniza el código fuente en unidades reconocibles.

**Responsabilidades:**
- Escanea la entrada carácter por carácter
- Reconoce palabras clave, identificadores, literales y operadores
- Reporta errores léxicos con información precisa de línea y columna
- Rastrea números de línea y columna para reporte de errores

**Errores Léxicos:**
- `L01`: Literal de cadena no cerrado
- `L02`: Número seguido de letras (número malformado)
- `L03`: Números decimales (no soportados)
- `L04`: Carácter con sugerencias de corrección
- `L05`: Carácter desconocido
- `L06`: Comentario de bloque no cerrado

**Salida:**
- Flujo de tokens
- Conteo de tokens procesados
- Lista de errores léxicos

### Fase 2: Análisis Sintáctico (Sintáctico)

El parser construye un Árbol de Sintaxis Abstracta (AST) a partir del flujo de tokens.

**Responsabilidades:**
- Valida la secuencia de tokens contra las reglas de gramática
- Construye una representación jerárquica del programa
- Implementa recuperación de errores para diagnosticar múltiples errores
- Distingue errores fatales (el programa no puede usarse) de advertencias recuperables

**Errores Sintácticos:**
- `S01`: Token esperado faltante
- `S02`: Token inesperado
- `S03`: Bloque de sentencias faltante
- `S04`: Opción de decisión inválida
- `S05`: Expresión inválida

**Estrategias de Recuperación de Errores:**
1. Sincronización de bloque: Omitir hasta la siguiente llave coincidente o ancla global
2. Inserción implícita: Asumir tokens faltantes cuando es consistente
3. Eliminación de token: Omitir tokens inesperados cuando el siguiente es válido

**Salida:**
- Árbol de Sintaxis Abstracta (AST)
- Errores y advertencias sintácticos
- Diagnósticos del parser

### Fase 3: Análisis Semántico (Semántico)

El analizador semántico valida la lógica del programa y construye una tabla de símbolos.

**Enfoque de Dos Pasadas:**

Pasada 1 (Declaraciones):
- Registra todas las declaraciones de personaje y escena
- Habilita referencias anticipadas (las escenas pueden referenciarse antes de su definición)
- Detecta declaraciones duplicadas

Pasada 2 (Verificación):
- Valida referencias de variables y atributos
- Comprueba consistencia de tipos
- Asegura que todas las escenas referenciadas existan

**Errores Semánticos:**
- `M01`: Variable o identificador no declarado
- `M02`: Símbolo redeclarado
- `M03`: Escena referenciada no existe
- `M04`: Tipo inválido en expresión
- `M05`: Personaje sin atributos
- `M06`: Escena vacía (sin sentencias)
- `M07`: Múltiples personajes principales

**Salida:**
- Tabla de símbolos
- Errores semánticos
- Estado de validación del programa

### Fase 4: Ejecución (Ejecución)

El intérprete ejecuta el AST en el entorno de tiempo de ejecución.

**Responsabilidades:**
- Mantiene el estado de variables y atributos de personajes
- Ejecuta sentencias en orden
- Gestiona flujo de control (transiciones de escena, decisiones)
- Proporciona interacción del usuario (entrada/salida)

**Errores en Tiempo de Ejecución:**
- Violaciones de acceso a variable
- Atributos indefinidos
- Operaciones inválidas

**Salida:**
- Experiencia narrativa interactiva
- Reportes de errores en tiempo de ejecución si se encuentran

### Flujo del Pipeline

```
Código Fuente
    |
    v
[Fase 1: Lexer] ---> Tokens (+ errores léxicos)
    |
    v
[Fase 2: Parser] ---> AST (+ errores sintácticos)
    |
    v (si no hay errores sintácticos fatales)
[Fase 3: Analizador Semántico] ---> Tabla de Símbolos (+ errores semánticos)
    |
    v (si no hay errores semánticos)
[Fase 4: Intérprete] ---> Salida de Narrativa
```

**Importante:** Si la Fase 2 produce errores sintácticos fatales O la Fase 3 produce algún error semántico, la ejecución se detiene y el programa no se ejecuta.

---

## Manejo de Errores

### Errores Léxicos

Ocurren cuando el código fuente contiene caracteres inválidos o tokens malformados.

**Recuperación:** Recuperación en modo pánico descarta un carácter y reanuda el análisis.

**Ejemplo:**
```
[L01] Error léxico en línea 5, columna 12: Cadena no terminada → '"Sin cerrar'
```

### Errores Sintácticos

Ocurren cuando la secuencia de tokens viola las reglas de gramática.

**Recuperación:** Sincronización utilizando anclas de bloque para continuar el análisis.

**Ejemplo:**
```
[S02] Error sintáctico en línea 10, columna 5: Token inesperado 'LLAVE_ABIERTA'
```

### Errores Semánticos

Ocurren cuando la lógica del programa es inválida (variables indefinidas, desajustes de tipo).

**Recuperación:** Ninguna; los errores semánticos previenen la ejecución.

**Ejemplo:**
```
[M01] Error semántico en línea 15: Variable 'personaje_no_existe' no declarada
```

### Errores en Tiempo de Ejecución

Ocurren durante la ejecución del programa (por ejemplo, división por cero, acceso a atributo indefinido).

**Ejemplo:**
```
[ERROR DE EJECUCIÓN] línea 20: Variable 'x' no definida en tiempo de ejecución
```

---

## Herramientas

### main_consola.py

Interfaz de línea de comandos para ejecutar programas de LoreEngine.

**Uso:**
```bash
python main_consola.py                  # Ejecutar ejemplo integrado
python main_consola.py historia.lore    # Ejecutar un archivo específico
```

**Salida:**
- Diagnósticos detallados de compilación
- Conteo de tokens y errores léxicos
- Visualización del árbol de sintaxis
- Contenidos de la tabla de símbolos
- Experiencia narrativa interactiva

### main_gui.py

Interfaz gráfica de usuario para desarrollar y ejecutar programas de LoreEngine.

**Características:**
- Resaltado de sintaxis
- Diagnósticos de errores
- Ejecución de historia interactiva
- Visualización del estado del personaje

**Uso:**
```bash
python main_gui.py
```

---

## Gramática del Lenguaje (Definición Formal)

### Nivel Superior

```
programa        := declaración*

declaración     := decl_personaje | decl_escena | decl_decision

decl_personaje  := 'personaje' rol? IDENTIFICADOR '{' atributo* '}'
rol             := 'principal' | 'enemigo' | 'aliado'
atributo        := IDENTIFICADOR ':' ENTERO

decl_escena     := 'escena' IDENTIFICADOR '{' sentencia* '}'
decl_decision   := 'decision' IDENTIFICADOR '{' opción+ '}'

opción          := 'opción' CADENA '->' IDENTIFICADOR
```

### Sentencias

```
sentencia       := sent_mostrar | sent_asignación | sent_decision 
                 | sent_si | sent_dado

sent_mostrar    := 'mostrar' expresión
sent_asignación := IDENTIFICADOR ('.' IDENTIFICADOR)? '=' expresión

sent_decision   := IDENTIFICADOR
sent_si         := 'si' expresión '{' sentencia* ('}' 'sino' '{' sentencia* '}')?
sent_dado       := 'dado' '{' (sent_si)+ ('sino' '{' sentencia* '}')? '}'
```

### Expresiones

```
expresión       := término (('+' | '-') término)*
término         := factor (('*' | '/') factor)*
factor          := ENTERO | CADENA | IDENTIFICADOR ('.' IDENTIFICADOR)?
                 | 'dado' '(' ENTERO ')' | '(' expresión ')'
                 | IDENTIFICADOR '{' opción+ '}'

condición       := expresión ('==' | '!=' | '<' | '>' | '<=' | '>=') expresión
                 | expresión
```

---

## Contribuciones y Licencia

LoreEngine fue desarrollado como un proyecto educativo. Se anima a los estudiantes a extender el lenguaje con nuevas características y capacidades.

Mejoras sugeridas:

- Tipos de datos adicionales (flotantes, listas, mapas)
- Definiciones y llamadas de funciones
- Estructuras de bucle (while, for)
- Coincidencia de patrones avanzada
- Gestión de activos (imágenes, sonido)
- Red para narrativas multijugador

---

## Créditos

**Curso:** Diseño de Compiladores (IS-913)  
**Institución:** Universidad Nacional Autónoma de Honduras (UNAH-COMAYAGUA)

**Componentes:**
- Analizador Léxico: `lexer_loreengine.py`
- Parser Sintáctico: `parser_loreengine.py`
- Analizador Semántico: `semantico_loreengine.py`
- Intérprete en Tiempo de Ejecución: `interprete_loreengine.py`
- Tabla de Símbolos: `symbol_table.py`
- Nodos del AST: `ast_nodes.py`

---

## Soporte y Documentación

Para salida de diagnóstico detallada durante el desarrollo:

```bash
python main_consola.py -d historia.lore   # Modo depuración (si está implementado)
```

Revisa la salida de diagnóstico después de cada fase de compilación para entender cualquier error detectado.

---

**Referencia del Lenguaje LoreEngine - versión 1.0**
