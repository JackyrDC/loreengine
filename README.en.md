<div align="center">
  <img src="assets/img/logo.svg" alt="LoreEngine Logo" width="300" height="300">
</div>

# LoreEngine

**[Español](README.es.md) • [English](README.en.md)**

---

---

## Table of Contents

1. [Introduction](#introduction)
2. [Language Overview](#language-overview)
3. [Installation and Setup](#installation-and-setup)
4. [Getting Started](#getting-started)
5. [Language Concepts](#language-concepts)
6. [Syntax Reference](#syntax-reference)
7. [Type System](#type-system)
8. [Standard Functions](#standard-functions)
9. [Examples](#examples)
10. [Compilation Pipeline](#compilation-pipeline)
11. [Error Handling](#error-handling)
12. [Tools](#tools)

---

## Introduction

LoreEngine is a domain-specific language (DSL) designed for creating interactive narrative experiences. It enables developers to define characters, scenes, and branching storylines through an intuitive, declarative syntax. The language combines storytelling abstractions with procedural logic, allowing for dynamic character interactions and player-driven narratives.

LoreEngine was developed as part of the course **Compiler Design (IS-913)** at Universidad Nacional Autónoma de Honduras (UNAH-COMAYAGUA).

---

## Language Overview

### Design Philosophy

LoreEngine is built on the following principles:

- **Narrative-first**: Syntax prioritizes story structure over technical implementation
- **Declarative**: Characters and scenes are declared once and referenced throughout the program
- **Interactive**: Built-in support for player choices and branching narratives
- **Strongly typed**: Limited but well-defined type system (integers, strings, attributes)
- **Deterministic execution**: Programs compile through four distinct phases before execution

### Core Concepts

The language organizes narratives around three fundamental concepts:

- **Characters (Personajes)**: Named entities with attributes that evolve during gameplay
- **Scenes (Escenas)**: Narrative contexts where dialogue and logic execute
- **Decisions (Decisiones)**: Player choices that determine narrative flow

---

## Installation and Setup

### Requirements

- Python 3.7 or higher
- Windows, macOS, or Linux

### Setup Instructions

1. Navigate to the LoreEngine directory:
   ```bash
   cd loreengine
   ```

2. No external dependencies are required. All modules are implemented using Python's standard library.

3. Verify the installation by checking for the presence of these core files:
   - `lexer_loreengine.py`
   - `parser_loreengine.py`
   - `semantico_loreengine.py`
   - `interprete_loreengine.py`

---

## Getting Started

### Running Your First Program

#### Console Mode

Execute a LoreEngine program in the console:

```bash
python main_consola.py historia.lore
```

Or run the integrated example:

```bash
python main_consola.py
```

#### GUI Mode

For a graphical interface:

```bash
python main_gui.py
```

### Minimal Example

Create a file named `historia.lore` with the following content:

```lore
personaje Protagonista {
  energía: 100
}

escena Inicio {
  mostrar "Welcome to the adventure."
  mostrar "Your energy: " + Protagonista.energía
}
```

Run it:

```bash
python main_consola.py historia.lore
```

---

## Language Concepts

### Characters (Personajes)

Characters are the foundation of any LoreEngine narrative. Each character has a unique name and a set of attributes that define their state.

#### Character Declaration

```lore
personaje NombreDelPersonaje {
  atributo1: valor_inicial
  atributo2: valor_inicial
  ...
}
```

#### Character Roles

Characters may have role modifiers:

- `principal`: The protagonist or main agent (only one per program)
- `enemigo`: A hostile NPC or adversary character
- `aliado`: An ally character

#### Attribute Access

Attributes are accessed using dot notation:

```lore
Personaje.atributo
```

### Scenes (Escenas)

Scenes define narrative contexts where the story unfolds. Each scene contains a sequence of statements that execute in order.

#### Scene Declaration

```lore
escena NombreDeLaEscena {
  statement_1
  statement_2
  ...
}
```

#### Scene Execution

Scenes execute sequentially unless interrupted by a decision that branches to another scene.

### Decisions and Options

Decisions present players with choices that determine narrative flow. Each decision branches to exactly one next scene based on the player's selection.

#### Decision Syntax

```lore
decision NombreDeLaDecision {
  opción "Choice text 1" -> EscenaSiguiente1
  opción "Choice text 2" -> EscenaSiguiente2
  opción "Choice text 3" -> EscenaSiguiente3
}
```

When a decision is executed, the player selects an option and the program branches to the corresponding scene. The remaining scene statements are skipped.

---

## Syntax Reference

### Statements

#### Print Statement (mostrar)

Displays text to the player. Accepts expressions that evaluate to strings or numbers.

```lore
mostrar "Fixed text"
mostrar variable
mostrar "Computed: " + valor
mostrar personaje.atributo
```

#### Assignment

Assigns a value to a variable or character attribute.

```lore
variable = expresión
personaje.atributo = expresión
```

#### Conditional Statement (si)

Executes statements conditionally based on a boolean expression.

```lore
si condición {
  statement_1
  statement_2
}

si condición {
  statement_1
}
sino {
  statement_2
}
```

#### Case Statement (dado)

Executes different statement blocks based on which condition is true. If no condition matches and a default (`sino`) block exists, it executes; otherwise, nothing happens.

```lore
dado {
  si condición1 {
    statement_block_1
  }
  si condición2 {
    statement_block_2
  }
  sino {
    default_block
  }
}
```

### Expressions

#### Literals

- **Integer**: `42`, `-15`, `0`
- **String**: `"Quoted text"`

#### Operators

##### Arithmetic Operators

| Operator | Operation | Example |
|----------|-----------|---------|
| `+` | Addition or String Concatenation | `5 + 3` = `8` |
| `-` | Subtraction | `10 - 4` = `6` |
| `*` | Multiplication | `3 * 7` = `21` |
| `/` | Integer Division | `15 / 3` = `5` |

##### Relational Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `==` | Equal | `x == 5` |
| `!=` | Not equal | `x != 0` |
| `<` | Less than | `x < 10` |
| `>` | Greater than | `x > 0` |
| `<=` | Less than or equal | `x <= 100` |
| `>=` | Greater than or equal | `x >= 50` |

#### Operator Precedence

Operations follow standard mathematical precedence, highest to lowest:

1. Parentheses `( )`
2. Multiplication `*`, Division `/`
3. Addition `+`, Subtraction `-`

```lore
mostrar 2 + 3 * 4      // prints 14, not 20
mostrar (2 + 3) * 4    // prints 20
```

#### String Concatenation

Strings are concatenated using the `+` operator:

```lore
mostrar "The player has " + puntos + " points"
```

---

## Type System

LoreEngine implements a simple but explicit type system:

### Integer Type

All numeric values are integers (32-bit signed).

```lore
edad: 25
salud: 100
```

### String Type

Strings are sequences of characters enclosed in double quotes.

```lore
nombre: "Aragorn"
mostrar "Hello, world"
```

### Attributes

Character attributes are typed at declaration and retain their type throughout execution.

```lore
personaje Mago {
  inteligencia: 18
  mana: 50
}
```

### Type Safety

The semantic analyzer validates:

- All variable references refer to declared variables
- Character attribute accesses are valid
- Expressions in conditions are properly typed
- No attribute name conflicts within a character

---

## Standard Functions

### Random Number Generation

The `dado(n)` function returns a random integer from 1 to n (inclusive).

#### Syntax

```lore
dado(max_value)
```

#### Example

```lore
mostrar "Rolling a d20: " + dado(20)
```

#### Behavior

- `dado(6)` returns a random integer between 1 and 6
- `dado(100)` returns a random integer between 1 and 100
- Only positive integers are supported

---

## Examples

### Example 1: Simple Story

```lore
personaje Aventurero {
  salud: 100
  mana: 50
}

escena Inicio {
  mostrar "You are an adventurer in a dangerous world."
  mostrar "Your health: " + Aventurero.salud
  mostrar "Your mana: " + Aventurero.mana
}
```

### Example 2: Interactive Story with Decisions

```lore
personaje principal Heroe {
  coraje: 50
  inteligencia: 60
}

escena Bosque {
  mostrar "You find yourself in a dark forest."
  mostrar "You hear a roar."
}

escena Lucha {
  mostrar "You attack the monster bravely!"
  Heroe.coraje = Heroe.coraje + 10
  mostrar "Your courage increased to " + Heroe.coraje
}

escena Huida {
  mostrar "You run as fast as you can."
  Heroe.coraje = Heroe.coraje - 5
  mostrar "Your courage decreased to " + Heroe.coraje
}

decision Encuentro {
  opción "Fight" -> Lucha
  opción "Run" -> Huida
}
```

### Example 3: Conditional Logic

```lore
personaje Comerciante {
  oro: 100
}

escena Mercado {
  Comerciante.oro = Comerciante.oro + 50
  
  si Comerciante.oro > 150 {
    mostrar "You have enough money to buy a weapon."
  }
  sino {
    mostrar "You need more money."
  }
}
```

### Example 4: Combat System with Random Outcomes

```lore
personaje Guerrero {
  fuerza: 15
  vida: 80
}

escena Batalla {
  mostrar "Combat begins..."
  mostrar "Your strength is: " + Guerrero.fuerza
  
  dado {
    si dado(100) < 50 {
      mostrar "Critical hit!"
      Guerrero.fuerza = Guerrero.fuerza + 5
    }
    sino {
      mostrar "Normal attack."
    }
  }
  
  mostrar "Your strength is now: " + Guerrero.fuerza
}
```

---

## Compilation Pipeline

LoreEngine programs are compiled through four distinct phases before execution. Each phase builds upon the previous one.

### Phase 1: Lexical Analysis (Léxico)

The lexer tokenizes the source code into recognizable units.

**Responsibilities:**
- Scans the input character by character
- Recognizes keywords, identifiers, literals, and operators
- Reports lexical errors with precise line and column information
- Tracks line and column numbers for error reporting

**Lexical Errors:**
- `L01`: Unclosed string literal
- `L02`: Number followed by letters (malformed number)
- `L03`: Decimal numbers (not supported)
- `L04`: Character with spelling suggestions
- `L05`: Unknown character
- `L06`: Unclosed block comment

**Output:**
- Token stream
- Count of tokens processed
- List of lexical errors

### Phase 2: Syntax Analysis (Sintáctico)

The parser builds an Abstract Syntax Tree (AST) from the token stream.

**Responsibilities:**
- Validates token sequence against grammar rules
- Builds a hierarchical representation of the program
- Implements error recovery to diagnose multiple errors
- Distinguishes fatal errors (program cannot be used) from recoverable warnings

**Syntax Errors:**
- `S01`: Expected token missing
- `S02`: Unexpected token
- `S03`: Missing statement block
- `S04`: Invalid decision option
- `S05`: Invalid expression

**Error Recovery Strategies:**
1. Block synchronization: Skip to the next matching brace or global anchor
2. Implicit insertion: Assume missing tokens when consistent
3. Token deletion: Skip unexpected tokens when the next one is valid

**Output:**
- Abstract Syntax Tree (AST)
- Syntax errors and warnings
- Parser diagnostics

### Phase 3: Semantic Analysis (Semántico)

The semantic analyzer validates program logic and builds a symbol table.

**Two-Pass Approach:**

Pass 1 (Declarations):
- Registers all character and scene declarations
- Enables forward references (scenes can be referenced before definition)
- Detects duplicate declarations

Pass 2 (Verification):
- Validates variable and attribute references
- Checks type consistency
- Ensures all referenced scenes exist

**Semantic Errors:**
- `M01`: Variable or identifier not declared
- `M02`: Symbol redeclared
- `M03`: Referenced scene does not exist
- `M04`: Invalid type in expression
- `M05`: Character with no attributes
- `M06`: Empty scene (no statements)
- `M07`: Multiple principal characters

**Output:**
- Symbol table
- Semantic errors
- Program validation status

### Phase 4: Execution (Ejecución)

The interpreter executes the AST in the runtime environment.

**Responsibilities:**
- Maintains variable state and character attributes
- Executes statements in order
- Manages control flow (scene transitions, decisions)
- Provides user interaction (input/output)

**Runtime Errors:**
- Variable access violations
- Undefined attributes
- Invalid operations

**Output:**
- Interactive narrative experience
- Runtime error reports if encountered

### Pipeline Flow

```text
Source Code
    |
    v
[Phase 1: Lexer] ---> Tokens (+ lexical errors)
    |
    v
[Phase 2: Parser] ---> AST (+ syntax errors)
    |
    v (if no fatal syntax errors)
[Phase 3: Semantic Analyzer] ---> Symbol Table (+ semantic errors)
    |
    v (if no semantic errors)
[Phase 4: Interpreter] ---> Narrative Output
```

**Important:** If Phase 2 produces fatal syntax errors OR Phase 3 produces any semantic errors, execution is halted and the program does not run.

---

## Error Handling

### Lexical Errors

Occur when the source code contains invalid characters or malformed tokens.

**Recovery:** Panic mode recovery discards one character and resumes analysis.

**Example:**
```
[L01] Error léxico en línea 5, columna 12: String not terminated → '"Unterminated'
```

### Syntax Errors

Occur when the token sequence violates the grammar rules.

**Recovery:** Synchronization using block anchors to continue analysis.

**Example:**
```
[S02] Error sintáctico en línea 10, columna 5: Unexpected token 'LLAVE_ABIERTA'
```

### Semantic Errors

Occur when program logic is invalid (undefined variables, type mismatches).

**Recovery:** None; semantic errors prevent execution.

**Example:**
```
[M01] Error semántico en línea 15: Variable 'personaje_no_existe' not declared
```

### Runtime Errors

Occur during program execution (e.g., division by zero, undefined attribute access).

**Example:**
```
[ERROR DE EJECUCIÓN] línea 20: Variable 'x' not defined at runtime
```

---

## Tools

### main_consola.py

Command-line interface for executing LoreEngine programs.

**Usage:**
```bash
python main_consola.py                  # Run integrated example
python main_consola.py historia.lore    # Run a specific file
```

**Output:**
- Detailed compilation diagnostics
- Token count and lexical errors
- Syntax tree visualization
- Symbol table contents
- Interactive narrative experience

### main_gui.py

Graphical user interface for developing and executing LoreEngine programs.

**Features:**
- Syntax highlighting
- Error diagnostics
- Interactive story execution
- Character state visualization

**Usage:**
```bash
python main_gui.py
```

---

## Language Grammar (Formal Definition)

### Top Level

```text
programa        := declaración*

declaración     := decl_personaje | decl_escena | decl_decision

decl_personaje  := 'personaje' rol? IDENTIFICADOR '{' atributo* '}'
rol             := 'principal' | 'enemigo' | 'aliado'
atributo        := IDENTIFICADOR ':' ENTERO

decl_escena     := 'escena' IDENTIFICADOR '{' sentencia* '}'
decl_decision   := 'decision' IDENTIFICADOR '{' opción+ '}'

opción          := 'opción' CADENA '->' IDENTIFICADOR
```

### Statements

```text
sentencia       := sent_mostrar | sent_asignación | sent_decision 
                 | sent_si | sent_dado

sent_mostrar    := 'mostrar' expresión
sent_asignación := IDENTIFICADOR ('.' IDENTIFICADOR)? '=' expresión

sent_decision   := IDENTIFICADOR
sent_si         := 'si' expresión '{' sentencia* ('}' 'sino' '{' sentencia* '}')?
sent_dado       := 'dado' '{' (sent_si)+ ('sino' '{' sentencia* '}')? '}'
```

### Expressions

```text
expresión       := término (('+' | '-') término)*
término         := factor (('*' | '/') factor)*
factor          := ENTERO | CADENA | IDENTIFICADOR ('.' IDENTIFICADOR)?
                 | 'dado' '(' ENTERO ')' | '(' expresión ')'
                 | IDENTIFICADOR '{' opción+ '}'

condición       := expresión ('==' | '!=' | '<' | '>' | '<=' | '>=') expresión
                 | expresión
```

---

## Credits

**Course:** Compiler Design (IS-913)  
**Institution:** Universidad Nacional Autónoma de Honduras (UNAH-COMAYAGUA)

**Components:**
- Lexical Analyzer: `lexer_loreengine.py`
- Syntax Parser: `parser_loreengine.py`
- Semantic Analyzer: `semantico_loreengine.py`
- Runtime Interpreter: `interprete_loreengine.py`
- Symbol Table: `symbol_table.py`
- AST Nodes: `ast_nodes.py`

---

**LoreEngine Language Reference - version 1.0**
