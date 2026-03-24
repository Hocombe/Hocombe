# ATENEA IA Demo — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Flask demo app that showcases AI-assisted judicial case management for the ATENEA system, targeting CGPJ/Ministry executives.

**Architecture:** Single Flask server (`app.py`) serves one HTML dashboard (`index.html`) with 4 tab panels. Backend handles intent detection (regex), LLM calls (urllib to Claude/Groq/Gemini with fallback to pre-generated JSON responses), and serves JSON knowledge base files. All data is fictitious.

**Tech Stack:** Python 3.8+ (stdlib + Flask), HTML/CSS/JS (inline, no frameworks), JSON data files.

**Spec:** `docs/superpowers/specs/2026-03-24-atenea-ia-demo-design.md`

**Target directory:** `D:/PROYECTOS CLAUDE/ATENEA-IA-Demo/`

---

## File Map

| File | Responsibility |
|---|---|
| `ATENEA-IA-Demo/app.py` | Flask server: routes, intent detection, LLM calls, knowledge base loading |
| `ATENEA-IA-Demo/index.html` | Single-page dashboard: 4 tab panels, chat UI, forms, stats display |
| `ATENEA-IA-Demo/config.json` | LLM API keys and settings (gitignored) |
| `ATENEA-IA-Demo/config.ejemplo.json` | Template config without real keys (committed) |
| `ATENEA-IA-Demo/iniciar.bat` | Windows launcher: pip install flask + start server |
| `ATENEA-IA-Demo/conocimiento/tramitacion.json` | Procedure phases per type (30 types × 4-8 phases each) |
| `ATENEA-IA-Demo/conocimiento/resoluciones.json` | Resolution templates by category |
| `ATENEA-IA-Demo/conocimiento/guia_atenea.json` | ATENEA manual indexed by functionality |
| `ATENEA-IA-Demo/conocimiento/glosario.json` | Judicial terminology dictionary |
| `ATENEA-IA-Demo/conocimiento/datos_demo.json` | ~130 fictitious procedures with parties, dates, phases |
| `ATENEA-IA-Demo/conocimiento/fallback.json` | Pre-generated responses for offline mode |

---

## Chunk 1: Foundation (Tasks 1-3)

### Task 1: Project scaffold, config, and launcher

**Files:**
- Create: `ATENEA-IA-Demo/config.json`
- Create: `ATENEA-IA-Demo/config.ejemplo.json`
- Create: `ATENEA-IA-Demo/iniciar.bat`
- Create: `ATENEA-IA-Demo/.gitignore`

- [ ] **Step 1: Create target directory**

```bash
mkdir -p "D:/PROYECTOS CLAUDE/ATENEA-IA-Demo/conocimiento"
mkdir -p "D:/PROYECTOS CLAUDE/ATENEA-IA-Demo/assets/capturas_atenea"
```

- [ ] **Step 2: Create config.ejemplo.json**

Create `ATENEA-IA-Demo/config.ejemplo.json` with the schema from the spec. All `api_key` fields empty strings. This file gets committed.

```json
{
  "puerto": 5050,
  "proveedor_activo": "claude",
  "proveedores": {
    "claude": {
      "api_key": "",
      "modelo": "claude-sonnet-4-6",
      "url": "https://api.anthropic.com/v1/messages"
    },
    "groq": {
      "api_key": "",
      "modelo": "llama-3.1-8b-instant",
      "url": "https://api.groq.com/openai/v1/chat/completions"
    },
    "gemini": {
      "api_key": "",
      "modelo": "gemini-2.0-flash",
      "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    }
  },
  "timeout_llm": 8,
  "max_tokens": 1024,
  "temperatura": 0.3
}
```

- [ ] **Step 3: Copy to config.json**

Copy `config.ejemplo.json` to `config.json`. This file is gitignored — the user fills in their real API keys here.

- [ ] **Step 4: Create iniciar.bat**

```bat
@echo off
pip install flask >nul 2>&1
echo Iniciando ATENEA IA en http://localhost:5050 ...
python app.py
```

- [ ] **Step 5: Create .gitignore**

```
config.json
__pycache__/
*.pyc
```

- [ ] **Step 6: Commit scaffold**

```bash
git add ATENEA-IA-Demo/
git commit -m "feat(atenea-demo): project scaffold with config and launcher"
```

---

### Task 2: Knowledge base JSON files

This is the largest data task. Create all 6 JSON files in `conocimiento/`. All names are completely fictitious.

**Files:**
- Create: `ATENEA-IA-Demo/conocimiento/tramitacion.json`
- Create: `ATENEA-IA-Demo/conocimiento/resoluciones.json`
- Create: `ATENEA-IA-Demo/conocimiento/guia_atenea.json`
- Create: `ATENEA-IA-Demo/conocimiento/glosario.json`
- Create: `ATENEA-IA-Demo/conocimiento/datos_demo.json`
- Create: `ATENEA-IA-Demo/conocimiento/fallback.json`

**Important:** Use @anthropic-skills:iudex-ia for judicial domain accuracy when generating procedure phases, resolution templates, and glossary entries.

- [ ] **Step 1: Create tramitacion.json**

All 30 procedure types with their phases. Structure:

```json
{
  "civil": {
    "JVB": {
      "nombre": "Juicio Verbal",
      "fases": [
        {
          "id": 1,
          "nombre": "Admisión",
          "descripcion": "Examen de la demanda y admisión a trámite",
          "tramites": [
            {"nombre": "Decreto admisión a trámite", "responsable": "LAJ", "plazo_dias": null},
            {"nombre": "Requerimiento subsanación", "responsable": "LAJ", "plazo_dias": 10}
          ],
          "siguiente_fase": 2
        },
        {
          "id": 2,
          "nombre": "Contestación",
          "descripcion": "Traslado de demanda y plazo de contestación",
          "tramites": [
            {"nombre": "Diligencia traslado demanda", "responsable": "LAJ", "plazo_dias": null},
            {"nombre": "Contestación a la demanda", "responsable": "Demandado", "plazo_dias": 10},
            {"nombre": "Declarar rebeldía", "responsable": "LAJ", "plazo_dias": null}
          ],
          "siguiente_fase": 3
        }
      ]
    }
  }
}
```

Include all 30 types grouped by jurisdiction: `civil` (14 types), `penal` (7 types), `ejecucion_civil` (6 types), `ejecucion_penal` (3 types). Each with 4-8 phases per the spec distribution table.

- [ ] **Step 2: Create resoluciones.json**

Resolution templates grouped by type. Structure:

```json
{
  "providencias": [
    {
      "id": "prov_admision_prueba",
      "titulo": "Providencia acordando/denegando prueba",
      "procedimientos_aplicables": ["JVB", "ORD", "OR5", "JVD", "MMC"],
      "fase": "Vista/Audiencia previa",
      "modelo": "En [LOCALIDAD], a [FECHA].\n\nPor presentado el anterior escrito, únanse a los autos de su razón.\n\nVisto el estado de las actuaciones y conforme a lo dispuesto en los artículos 283 y siguientes de la LEC, se acuerda:\n\nADMITIR la prueba propuesta por la parte [DEMANDANTE/DEMANDADA] consistente en:\n- [PRUEBA_1]\n- [PRUEBA_2]\n\nNO ADMITIR la prueba consistente en [PRUEBA_DENEGADA] por [MOTIVO].\n\nNotifíquese a las partes.\n\nAsí lo acuerda y firma S.S.ª [JUEZ]. Doy fe."
    }
  ],
  "autos": [...],
  "decretos": [...],
  "diligencias_ordenacion": [...],
  "sentencias": [...],
  "oficios": [...]
}
```

Include 4+ templates per category as specified in the spec (providencias: admisión prueba, señalamiento, traslado, requerimiento; autos: admisión demanda, sobreseimiento, procesamiento, inhibición, entrada y registro; etc.)

- [ ] **Step 3: Create guia_atenea.json**

Manual indexed by functionality. Structure:

```json
{
  "secciones": [
    {
      "id": "tramitacion",
      "titulo": "Tramitación",
      "subsecciones": [
        {
          "id": "aceptacion_escritos",
          "titulo": "Aceptación de Escritos",
          "contenido": "Para aceptar escritos en ATENEA:\n1. Acceder a la bandeja de aceptación de Escritos...",
          "pasos": [
            "Acceder al menú Tramitación > Aceptación de Escritos",
            "Se muestran todos los Escritos enviados a nuestro Órgano",
            "Filtrar por tipo, fecha o contenido",
            "Seleccionar el escrito y pulsar Aceptar",
            "Categorizar si procede antes de aceptar"
          ],
          "captura": null,
          "palabras_clave": ["escritos", "aceptar", "bandeja", "LexNET", "trámite"]
        }
      ]
    },
    {
      "id": "comunicacion",
      "titulo": "Comunicación",
      "subsecciones": [...]
    }
  ],
  "problemas_conocidos": [
    {
      "id": "firma_laj",
      "problema": "Documentos firmados solo por LAJ no pasan a portafirmas",
      "sintoma": "El documento queda en estado naranja (enviado a firma) pero no aparece en el portafirmas electrónico",
      "workaround": "Recuperar el documento manualmente desde Minerva y reenviarlo al portafirmas",
      "fuente": "CCOO Asturias, abril 2025"
    }
  ]
}
```

Include all 8 sections from spec (Tramitación, Comunicación, Consultas, Utilidades, Configuración, Tareas Pendientes, Guardia, Operaciones Especiales) plus `problemas_conocidos`.

- [ ] **Step 4: Create glosario.json**

```json
{
  "terminos": [
    {
      "termino": "NIG",
      "definicion": "Número de Identificación General. Identificador único de cada procedimiento judicial en España. Formato: 5 dígitos de población + 2 dígitos tipo de órgano + 1 dígito orden jurisdiccional + 4 dígitos año + 7 dígitos número secuencial.",
      "ejemplo": "36057-42-1-2026-0000123",
      "relacionados": ["NUE", "Procedimiento"]
    },
    {
      "termino": "LAJ",
      "definicion": "Letrado de la Administración de Justicia (antiguo Secretario Judicial). Responsable de la fe pública judicial, impulso del proceso y dirección del personal.",
      "relacionados": ["Decreto", "Diligencia de Ordenación"]
    }
  ]
}
```

Include 30-50 key judicial terms relevant to ATENEA usage.

- [ ] **Step 5: Create datos_demo.json**

~130 fictitious procedures. Structure:

```json
{
  "juzgado": "Juzgado de Primera Instancia e Instrucción nº 1 de Demostración",
  "localidad": "Villa de la Justicia",
  "procedimientos": [
    {
      "tipo": "JVB",
      "numero": "45/2026",
      "nig": "99001-42-1-2026-0000045",
      "fase_actual": "Vista",
      "estado": "Pendiente señalamiento",
      "fecha_incoacion": "2026-01-15",
      "partes": {
        "demandante": {"nombre": "Elena Martínez Ruiz", "procurador": "Carlos Vega López", "abogado": "Ana Beltrán Soler"},
        "demandado": {"nombre": "Inmobiliaria Horizonte S.L.", "procurador": "Marta Díaz Cano", "abogado": "Luis Ramos Gil"}
      },
      "cuantia": 8500.00,
      "materia": "Reclamación de cantidad",
      "plazos": [
        {"tipo": "Señalamiento vista", "fecha": "2026-04-22", "estado": "pendiente"}
      ],
      "ultimo_tramite": "Contestación a la demanda presentada el 2026-03-10"
    }
  ]
}
```

ALL names completely fictitious. Generate 5-8 per procedure type as specified in the distribution table (30 types = ~130-160 total). Vary phases, dates, parties, amounts.

- [ ] **Step 6: Create fallback.json**

Pre-generated responses keyed by `{intention}_{subtype}`. Include:
- 2-3 entries per intention from the spec table
- `general._default` as catch-all
- Responses should be substantive (not just "I don't know"), judicial-quality text

```json
{
  "tramite_siguiente": {
    "JVB_contestacion": "Tras la contestación a la demanda en un Juicio Verbal (JVB), el siguiente trámite es el señalamiento de la vista (art. 440 LEC). El LAJ dictará diligencia de ordenación señalando día y hora para la celebración de la vista, citando a las partes con al menos 10 días de antelación.",
    "MON_requerimiento": "Emitido el requerimiento de pago en un Monitorio, caben dos posibilidades: 1) Si el deudor paga en 20 días, se archivan las actuaciones. 2) Si el deudor se opone, se transforma en JVB (hasta 6.000€) u ORD (más de 6.000€). 3) Si no paga ni se opone, se despacha ejecución directamente (art. 816 LEC).",
    "_default": "Para determinar el siguiente trámite necesito saber el tipo de procedimiento y en qué fase se encuentra. ¿Puedes indicarme estos datos?"
  },
  "fase_procesal": {
    "_default": "Para consultar la fase procesal de un procedimiento, necesito el tipo (JVB, ORD, DPA, etc.) y el estado actual. ¿Puedes proporcionarme estos datos?"
  },
  "generar_resolucion": {
    "_default": "Para generar una resolución necesito: tipo de resolución (providencia, auto, decreto, diligencia, sentencia, oficio), tipo de procedimiento y contexto del caso. ¿Puedes detallarme estos datos?"
  },
  "guia_atenea": {
    "inhibicion": "Para realizar una inhibición en ATENEA:\n1. Acceder a Tramitación > seleccionar el procedimiento\n2. Menú Operaciones Especiales > Inhibición\n3. Indicar el órgano de destino (municipio, tipo de órgano, número)\n4. Se genera automáticamente el auto de inhibición\n5. Aceptar para tramitar la inhibición\n\nNota: El procedimiento quedará en estado 'Inhibido' y no se podrán realizar más trámites.",
    "firma_laj": "Para firmar un documento solo con LAJ en ATENEA:\n1. Desde el compositor de documentos, al finalizar pulsar 'Firma local'\n2. Si el documento no requiere firma judicial, seleccionar 'No requiere firma'\n3. El documento pasará directamente a estado 'Definitivo'\n\nProblema conocido: En algunas versiones los documentos quedan en naranja. Workaround: recuperar desde Minerva y reenviar.",
    "registro_auxilio": "Para registrar un Auxilio Judicial en ATENEA:\n1. Menú Registro > Registro de Asuntos\n2. Seleccionar tipo 'Auxilio Judicial'\n3. Rellenar datos del órgano requirente\n4. Introducir el NIG de origen (o dejar que el sistema genere uno propio)\n5. Registrar intervinientes y documentos\n6. Pulsar 'Registrar'",
    "_default": "Para buscar una funcionalidad en ATENEA, indícame qué operación necesitas realizar y te guiaré paso a paso."
  },
  "problema_atenea": {
    "_default": "Describe el problema que encuentras en ATENEA y te indicaré si hay un workaround conocido."
  },
  "consulta_datos": {
    "_default": "Puedo consultar los procedimientos de demo por tipo, fase, estado o plazos. ¿Qué datos necesitas?"
  },
  "plazos": {
    "_default": "Consultando los plazos de los procedimientos activos en el juzgado de demostración..."
  },
  "estadisticas": {
    "_default": "Generando estadísticas del juzgado de demostración..."
  },
  "glosario": {
    "NIG": "NIG (Número de Identificación General): Identificador único de cada procedimiento judicial en España. Formato: 5 dígitos de población + 2 dígitos tipo de órgano + 1 dígito orden jurisdiccional + 4 dígitos año + 7 dígitos número secuencial. Ejemplo: 36057-42-1-2026-0000123.",
    "LAJ": "LAJ (Letrado de la Administración de Justicia): Antiguo Secretario Judicial. Responsable de la fe pública judicial, impulso procesal, y dirección del personal de la oficina judicial. Dicta Decretos y Diligencias de Ordenación.",
    "LexNET": "LexNET: Sistema de comunicaciones telemáticas de la Administración de Justicia. Permite la presentación de escritos, recepción de notificaciones y consulta de expedientes por vía electrónica.",
    "_default": "No tengo ese término en el glosario. ¿Puedes indicarme la palabra exacta?"
  },
  "general": {
    "_default": "Soy el asistente ATENEA IA. Puedo ayudarte con:\n\n• **Tramitación**: consultar fases procesales y siguiente trámite\n• **Resoluciones**: generar borradores de providencias, autos, decretos...\n• **Guía ATENEA**: cómo usar el sistema paso a paso\n• **Consultas**: buscar procedimientos, plazos y estadísticas\n\n¿Qué necesitas?"
  }
}
```

- [ ] **Step 7: Commit knowledge base**

```bash
git add ATENEA-IA-Demo/conocimiento/
git commit -m "feat(atenea-demo): knowledge base JSON files (tramitación, resoluciones, guía, glosario, datos demo, fallback)"
```

---

### Task 3: Flask backend (app.py)

**Files:**
- Create: `ATENEA-IA-Demo/app.py`

The backend handles: config loading, knowledge base loading, intent detection, LLM calls with fallback chain, and all API endpoints.

- [ ] **Step 1: Write app.py — imports, config loading, knowledge base**

```python
import json, os, re, urllib.request, urllib.error, threading, webbrowser, logging, ssl
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Config ---
def cargar_config():
    ruta = os.path.join(BASE_DIR, 'config.json')
    if not os.path.exists(ruta):
        ruta = os.path.join(BASE_DIR, 'config.ejemplo.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = cargar_config()

# --- Knowledge Base ---
def cargar_json(nombre):
    ruta = os.path.join(BASE_DIR, 'conocimiento', nombre)
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

TRAMITACION = cargar_json('tramitacion.json')
RESOLUCIONES = cargar_json('resoluciones.json')
GUIA = cargar_json('guia_atenea.json')
GLOSARIO = cargar_json('glosario.json')
DATOS_DEMO = cargar_json('datos_demo.json')
FALLBACK = cargar_json('fallback.json')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
```

- [ ] **Step 2: Write intent detection system**

```python
# --- Intent Detection (regex) ---
PATRONES_INTENCION = [
    ('tramite_siguiente', [
        r'(?:qué|que)\s+(?:trámite|tramite|toca|sigue|paso)',
        r'siguiente\s+(?:trámite|tramite|paso|fase)',
        r'(?:después|despues)\s+de\s+(?:la\s+)?(?:contestación|contestacion|admisión|admision|vista)',
    ]),
    ('fase_procesal', [
        r'(?:en\s+qué|en\s+que)\s+fase',
        r'fase\s+(?:procesal|actual|del)',
        r'estado\s+(?:procesal|del\s+procedimiento)',
    ]),
    ('generar_resolucion', [
        r'(?:redacta|genera|elabora|escribe|haz)\s+(?:una?\s+)?(?:providencia|auto|decreto|diligencia|sentencia|oficio)',
        r'(?:borrador|modelo)\s+de\s+(?:providencia|auto|decreto|diligencia|sentencia|oficio)',
    ]),
    ('guia_atenea', [
        r'(?:cómo|como)\s+(?:se\s+)?(?:hace|hago|registro|tramito|notifico)',
        r'(?:en\s+)?atenea\s+(?:cómo|como|dónde|donde)',
        r'paso\s+a\s+paso',
    ]),
    ('problema_atenea', [
        r'no\s+(?:me\s+)?(?:deja|permite|puedo|funciona)',
        r'(?:error|fallo|problema|bug)\s+(?:en\s+)?atenea',
        r'no\s+(?:aparece|sale|muestra)',
    ]),
    ('consulta_datos', [
        r'(?:cuántos|cuantos|cuáles|cuales|qué|que)\s+(?:procedimientos|asuntos|casos)',
        r'(?:busca|buscar|lista|listar)\s+(?:procedimientos|asuntos)',
        r'procedimientos?\s+(?:de\s+tipo|civiles?|penales?|de\s+ejecución)',
    ]),
    ('plazos', [
        r'(?:qué|que)\s+(?:plazos?|vence|vencimientos?)',
        r'plazos?\s+(?:esta\s+semana|pendientes?|próximos?)',
        r'vencimientos?\s+(?:esta\s+semana|pendientes?)',
    ]),
    ('estadisticas', [
        r'estad[ií]sticas?',
        r'(?:resumen|informe|datos)\s+(?:del\s+)?(?:juzgado|tribunal)',
        r'(?:cuántos|cuantos)\s+(?:asuntos|procedimientos)\s+(?:hay|tenemos)',
    ]),
    ('glosario', [
        r'(?:qué|que)\s+(?:es|significa)\s+(?:un[ao]?\s+)?(?:\w+)',
        r'(?:definición|definicion|significado)\s+de',
    ]),
]

def detectar_intencion(mensaje):
    texto = mensaje.lower().strip()
    for intencion, patrones in PATRONES_INTENCION:
        for patron in patrones:
            if re.search(patron, texto):
                return intencion
    return 'general'
```

- [ ] **Step 3: Write LLM call system with fallback chain**

```python
# --- System Prompt ---
SYSTEM_PROMPT = """Eres un Letrado de la Administración de Justicia experto en el sistema judicial español.
Respondes consultas sobre tramitación procesal (civil, penal, ejecución, familia).
Conoces la LEC, LECrim, LOPJ, CC y CP.
Citas artículos cuando procede. Respuestas concisas, estructuradas, con pasos claros.
Si te proporcionan contexto de la base de conocimiento, úsalo para dar respuestas precisas.
Formato: usa viñetas, negritas para conceptos clave, y estructura la respuesta en secciones si es larga."""

CADENA_PROVEEDORES = ['claude', 'groq', 'gemini']

def _llamar_claude(config_prov, mensajes, max_tokens, temperatura):
    """Llama a la API de Anthropic (formato Messages API)."""
    system_msg = ''
    user_msgs = []
    for m in mensajes:
        if m['role'] == 'system':
            system_msg = m['content']
        else:
            user_msgs.append(m)
    body = json.dumps({
        'model': config_prov['modelo'],
        'max_tokens': max_tokens,
        'temperature': temperatura,
        'system': system_msg,
        'messages': user_msgs
    }).encode('utf-8')
    req = urllib.request.Request(config_prov['url'], data=body, headers={
        'Content-Type': 'application/json',
        'x-api-key': config_prov['api_key'],
        'anthropic-version': '2023-06-01'
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=CONFIG['timeout_llm'], context=ctx) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    return data['content'][0]['text']

def _llamar_openai_compatible(config_prov, mensajes, max_tokens, temperatura):
    """Llama a APIs compatibles con OpenAI (Groq, Gemini)."""
    body = json.dumps({
        'model': config_prov['modelo'],
        'messages': mensajes,
        'max_tokens': max_tokens,
        'temperature': temperatura
    }).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {config_prov['api_key']}"
    }
    req = urllib.request.Request(config_prov['url'], data=body, headers=headers)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=CONFIG['timeout_llm'], context=ctx) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    return data['choices'][0]['message']['content']

def llamar_llm(mensajes):
    """Intenta la cadena de proveedores LLM. Devuelve (respuesta, proveedor_usado)."""
    max_tokens = CONFIG.get('max_tokens', 1024)
    temperatura = CONFIG.get('temperatura', 0.3)
    activo = CONFIG.get('proveedor_activo', 'claude')

    # Reorder chain: active provider first, then the rest
    cadena = [activo] + [p for p in CADENA_PROVEEDORES if p != activo]

    for proveedor in cadena:
        config_prov = CONFIG.get('proveedores', {}).get(proveedor, {})
        if not config_prov.get('api_key'):
            continue
        try:
            logging.info(f'LLM: intentando {proveedor}...')
            if proveedor == 'claude':
                texto = _llamar_claude(config_prov, mensajes, max_tokens, temperatura)
            else:
                texto = _llamar_openai_compatible(config_prov, mensajes, max_tokens, temperatura)
            logging.info(f'LLM: éxito con {proveedor}')
            return texto, proveedor
        except Exception as e:
            logging.warning(f'LLM: fallo {proveedor}: {e}')
            continue

    return None, 'ninguno'
```

- [ ] **Step 4: Write context builder and fallback resolver**

```python
# --- Context Builder ---
def construir_contexto(intencion, mensaje):
    """Construye el contexto JSON relevante para la intención detectada."""
    if intencion == 'tramite_siguiente' or intencion == 'fase_procesal':
        # Extract procedure type from message
        tipos = []
        for jurisdiccion in TRAMITACION.values():
            for tipo in jurisdiccion:
                if tipo.lower() in mensaje.lower() or tipo in mensaje.upper():
                    tipos.append(tipo)
        if tipos:
            contexto_procs = {}
            for jurisdiccion in TRAMITACION.values():
                for tipo in tipos:
                    if tipo in jurisdiccion:
                        contexto_procs[tipo] = jurisdiccion[tipo]
            return json.dumps(contexto_procs, ensure_ascii=False, indent=2)
        return json.dumps({"nota": "No se identificó tipo de procedimiento. Tipos disponibles: " +
            ", ".join(t for j in TRAMITACION.values() for t in j)}, ensure_ascii=False)

    elif intencion == 'generar_resolucion':
        return json.dumps(RESOLUCIONES, ensure_ascii=False, indent=2)

    elif intencion in ('guia_atenea', 'problema_atenea'):
        return json.dumps(GUIA, ensure_ascii=False, indent=2)[:4000]  # Truncate for context window

    elif intencion == 'glosario':
        return json.dumps(GLOSARIO, ensure_ascii=False, indent=2)

    elif intencion in ('consulta_datos', 'plazos', 'estadisticas'):
        procs = DATOS_DEMO.get('procedimientos', [])
        resumen = {
            'total': len(procs),
            'por_tipo': {},
            'por_fase': {},
            'plazos_proximos': []
        }
        hoy = datetime.now().strftime('%Y-%m-%d')
        semana = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        for p in procs:
            resumen['por_tipo'][p['tipo']] = resumen['por_tipo'].get(p['tipo'], 0) + 1
            resumen['por_fase'][p['fase_actual']] = resumen['por_fase'].get(p['fase_actual'], 0) + 1
            for plazo in p.get('plazos', []):
                if plazo.get('estado') == 'pendiente' and plazo.get('fecha', '') <= semana:
                    resumen['plazos_proximos'].append({
                        'proc': f"{p['tipo']} {p['numero']}",
                        'plazo': plazo['tipo'],
                        'fecha': plazo['fecha']
                    })
        return json.dumps(resumen, ensure_ascii=False, indent=2)

    return ''

def buscar_fallback(intencion, mensaje):
    """Busca la respuesta pre-generada más relevante."""
    bloque = FALLBACK.get(intencion, {})
    if not bloque:
        bloque = FALLBACK.get('general', {})

    # Try to find specific key match
    texto_lower = mensaje.lower()
    mejor = None
    mejor_score = 0
    for clave, respuesta in bloque.items():
        if clave == '_default':
            continue
        palabras_clave = clave.lower().replace('_', ' ').split()
        score = sum(1 for p in palabras_clave if p in texto_lower)
        if score > mejor_score:
            mejor_score = score
            mejor = respuesta

    if mejor:
        return mejor
    return bloque.get('_default', FALLBACK.get('general', {}).get('_default', 'No tengo información sobre esa consulta.'))
```

- [ ] **Step 5: Write API endpoints**

```python
# --- Routes ---
@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))

@app.route('/api/estado')
def api_estado():
    """Check LLM provider status."""
    activo = CONFIG.get('proveedor_activo', 'claude')
    config_prov = CONFIG.get('proveedores', {}).get(activo, {})
    tiene_key = bool(config_prov.get('api_key'))
    return jsonify({'proveedor': activo, 'estado': 'ok' if tiene_key else 'fallback'})

@app.route('/api/asistente', methods=['POST'])
def api_asistente():
    """Main chat endpoint."""
    data = request.get_json(force=True)
    mensaje = data.get('mensaje', '').strip()
    historial = data.get('historial', [])
    if not mensaje:
        return jsonify({'respuesta': 'Por favor, escribe tu consulta.', 'intencion': 'error', 'fuente': 'sistema'})

    intencion = detectar_intencion(mensaje)
    contexto = construir_contexto(intencion, mensaje)
    logging.info(f'Consulta: "{mensaje}" -> intención: {intencion}')

    # Build LLM messages
    mensajes_llm = [{'role': 'system', 'content': SYSTEM_PROMPT + '\n\nCONTEXTO:\n' + contexto}]
    for h in historial[-6:]:  # Last 3 exchanges
        mensajes_llm.append(h)
    mensajes_llm.append({'role': 'user', 'content': mensaje})

    respuesta, fuente = llamar_llm(mensajes_llm)

    if respuesta is None:
        respuesta = buscar_fallback(intencion, mensaje)
        fuente = 'fallback'

    # For data queries, attach structured data
    datos_extra = None
    if intencion in ('consulta_datos', 'plazos', 'estadisticas'):
        datos_extra = json.loads(contexto)

    logging.info(f'Respuesta ({fuente}): {respuesta[:100]}...')
    return jsonify({
        'respuesta': respuesta,
        'intencion': intencion,
        'fuente': fuente,
        'datos': datos_extra
    })

@app.route('/api/resolucion', methods=['POST'])
def api_resolucion():
    """Generate a judicial resolution."""
    data = request.get_json(force=True)
    tipo_res = data.get('tipo', '')
    tipo_proc = data.get('procedimiento', '')
    numero = data.get('numero', '')
    contexto_usuario = data.get('contexto', '')

    # Find matching template
    categoria = RESOLUCIONES.get(tipo_res + 's', RESOLUCIONES.get(tipo_res, []))
    if isinstance(categoria, dict):
        categoria = list(categoria.values())
    modelo_base = ''
    for modelo in (categoria if isinstance(categoria, list) else []):
        if tipo_proc in modelo.get('procedimientos_aplicables', []) or not modelo.get('procedimientos_aplicables'):
            modelo_base = modelo.get('modelo', '')
            break
    if not modelo_base and isinstance(categoria, list) and categoria:
        modelo_base = categoria[0].get('modelo', '')

    prompt = f"""Genera una resolución judicial de tipo {tipo_res} para un procedimiento {tipo_proc} {numero}.
Contexto del caso: {contexto_usuario}
Usa este modelo como base y adáptalo al contexto:\n\n{modelo_base}

Genera el texto completo de la resolución, rellenando los campos entre corchetes con datos coherentes."""

    mensajes = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt}
    ]
    respuesta, fuente = llamar_llm(mensajes)
    if respuesta is None:
        respuesta = modelo_base if modelo_base else f'No hay modelo disponible para {tipo_res} en {tipo_proc}.'
        fuente = 'modelo_base'

    return jsonify({'texto': respuesta, 'fuente': fuente})

@app.route('/api/guia')
def api_guia():
    """Search ATENEA guide."""
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify({'resultados': GUIA.get('secciones', [])})

    resultados = []
    palabras = query.split()
    for seccion in GUIA.get('secciones', []):
        for sub in seccion.get('subsecciones', []):
            score = 0
            texto_buscar = (sub.get('titulo', '') + ' ' + sub.get('contenido', '') + ' ' +
                          ' '.join(sub.get('palabras_clave', []))).lower()
            for p in palabras:
                if p in texto_buscar:
                    score += 1
            if score > 0:
                resultados.append({**sub, 'seccion': seccion['titulo'], 'score': score})

    # Also search problemas_conocidos
    for prob in GUIA.get('problemas_conocidos', []):
        texto_buscar = (prob.get('problema', '') + ' ' + prob.get('sintoma', '') + ' ' + prob.get('workaround', '')).lower()
        score = sum(1 for p in palabras if p in texto_buscar)
        if score > 0:
            resultados.append({
                'titulo': '⚠ ' + prob['problema'],
                'contenido': f"Síntoma: {prob.get('sintoma', '')}\n\nSolución: {prob.get('workaround', '')}",
                'seccion': 'Problemas conocidos',
                'score': score + 5  # Boost problems to appear first
            })

    resultados.sort(key=lambda x: x.get('score', 0), reverse=True)
    return jsonify({'resultados': resultados[:10]})

@app.route('/api/procedimientos')
def api_procedimientos():
    """Query demo procedures."""
    tipo = request.args.get('tipo', '').upper()
    fase = request.args.get('fase', '').lower()
    q = request.args.get('q', '').lower()
    procs = DATOS_DEMO.get('procedimientos', [])
    resultados = []
    for p in procs:
        if tipo and p['tipo'] != tipo:
            continue
        if fase and fase not in p.get('fase_actual', '').lower():
            continue
        if q and q not in json.dumps(p, ensure_ascii=False).lower():
            continue
        resultados.append(p)
    return jsonify({'procedimientos': resultados, 'total': len(resultados)})

@app.route('/api/estadisticas')
def api_estadisticas():
    """Dashboard statistics."""
    procs = DATOS_DEMO.get('procedimientos', [])
    por_tipo = {}
    por_fase = {}
    por_jurisdiccion = {'civil': 0, 'penal': 0, 'ejecucion_civil': 0, 'ejecucion_penal': 0}
    plazos_semana = []
    hoy = datetime.now()
    semana = hoy + timedelta(days=7)

    TIPOS_PENAL = {'DUD', 'DPA', 'LEV', 'LEI', 'POP', 'SU', 'JRD'}
    TIPOS_EJ_CIVIL = {'ETJ', 'ENJ', 'EJH', 'POJ', 'POH', 'POI'}
    TIPOS_EJ_PENAL = {'EJ', 'EFM', 'COG'}

    for p in procs:
        t = p['tipo']
        por_tipo[t] = por_tipo.get(t, 0) + 1
        f = p.get('fase_actual', 'Sin fase')
        por_fase[f] = por_fase.get(f, 0) + 1
        if t in TIPOS_PENAL: por_jurisdiccion['penal'] += 1
        elif t in TIPOS_EJ_CIVIL: por_jurisdiccion['ejecucion_civil'] += 1
        elif t in TIPOS_EJ_PENAL: por_jurisdiccion['ejecucion_penal'] += 1
        else: por_jurisdiccion['civil'] += 1
        for plazo in p.get('plazos', []):
            if plazo.get('estado') == 'pendiente':
                try:
                    fecha_p = datetime.strptime(plazo['fecha'], '%Y-%m-%d')
                    if hoy <= fecha_p <= semana:
                        plazos_semana.append({
                            'proc': f"{t} {p['numero']}",
                            'plazo': plazo['tipo'],
                            'fecha': plazo['fecha']
                        })
                except ValueError:
                    pass

    plazos_semana.sort(key=lambda x: x['fecha'])
    return jsonify({
        'total': len(procs),
        'por_tipo': por_tipo,
        'por_fase': por_fase,
        'por_jurisdiccion': por_jurisdiccion,
        'plazos_semana': plazos_semana
    })

# --- Main ---
if __name__ == '__main__':
    puerto = CONFIG.get('puerto', 5050)
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{puerto}')).start()
    logging.info(f'ATENEA IA iniciado en http://localhost:{puerto}')
    app.run(host='127.0.0.1', port=puerto, debug=False)
```

- [ ] **Step 6: Test backend manually**

```bash
cd "D:/PROYECTOS CLAUDE/ATENEA-IA-Demo"
python -c "
from app import detectar_intencion, buscar_fallback
assert detectar_intencion('¿Qué trámite toca en un JVB?') == 'tramite_siguiente'
assert detectar_intencion('¿Cómo hago una inhibición en ATENEA?') == 'guia_atenea'
assert detectar_intencion('Redacta una providencia de admisión') == 'generar_resolucion'
assert detectar_intencion('¿Qué es un NIG?') == 'glosario'
assert detectar_intencion('¿Cuántos asuntos civiles hay?') == 'consulta_datos'
assert detectar_intencion('Hola, buenos días') == 'general'
print('All intent tests passed')
fb = buscar_fallback('glosario', '¿Qué es un NIG?')
assert 'NIG' in fb
print('Fallback test passed')
print('All backend tests OK')
"
```

Expected: All assertions pass, prints "All backend tests OK"

- [ ] **Step 7: Commit backend**

```bash
git add ATENEA-IA-Demo/app.py
git commit -m "feat(atenea-demo): Flask backend with intent detection, LLM fallback chain, and all API endpoints"
```

---

## Chunk 2: Frontend (Task 4)

### Task 4: Dashboard HTML (index.html)

**Files:**
- Create: `ATENEA-IA-Demo/index.html`

Single HTML file with inline CSS and JS. Professional institutional design. 4 tab panels. Uses @frontend-design for design quality.

- [ ] **Step 1: Write index.html — structure, styles, and header**

Create the full HTML document with:
- Professional color scheme: dark blue (#1a365d) header, white content, light gray (#f5f7fa) sidebar
- Institutional fonts: system-ui, Segoe UI
- Responsive layout: sidebar (250px) + main content area
- Header: title "ATENEA IA" + juzgado name + LLM status indicator (colored dot)
- Sidebar: 4 tabs with icons (unicode), active state highlighted
- Tab switching via JS (show/hide panels)

- [ ] **Step 2: Write Panel 1 — Asistente de Tramitación**

Chat interface:
- Message history area (scrollable)
- Input box + send button at bottom
- Quick action buttons row: "Señalamiento", "Admisión demanda", "Vista oral", "Ejecución", "Recurso", "Instrucción penal"
- Messages styled as bubbles (user right, assistant left)
- Loading indicator while waiting for LLM
- Phase indicator bar when a specific procedure is discussed
- JS: `fetch('/api/asistente', {method:'POST', body: JSON.stringify({mensaje, historial})})` on send
- Maintain `historial` array in JS for conversation context

- [ ] **Step 3: Write Panel 2 — Generador de Resoluciones**

Form interface:
- Select: tipo resolución (Providencia, Auto, Decreto, Diligencia de Ordenación, Sentencia, Oficio)
- Select: tipo procedimiento (all 30 types grouped by jurisdiction in optgroups)
- Input: número procedimiento
- Textarea: contexto del caso
- Validation: disable nonsensical combinations using this map in JS:
  ```
  COMBINACIONES_INVALIDAS = {
    'sentencia': ['X53','MON'],  // No hay sentencia en conciliación ni monitorio
    'auto': ['X53'],              // Conciliación no lleva autos
    'oficio': ['X53']             // Conciliación no lleva oficios
  }
  ```
  When tipo_resolucion changes, disable procedure options that are invalid. Show tooltip explaining why.
- Button "Generar Resolución"
- Output area: formatted text with judicial styling (serif font, justified)
- Button "Copiar al portapapeles"
- JS: `fetch('/api/resolucion', {method:'POST', body: JSON.stringify({tipo, procedimiento, numero, contexto})})`

- [ ] **Step 4: Write Panel 3 — Guía ATENEA**

Search + tree interface:
- Search input at top with real-time search
- Results area showing matching sections with highlighted keywords
- Sidebar tree of manual sections (collapsible)
- Section detail view with step-by-step instructions
- Image display: if result has `captura` field and it's non-null, show `<img src="/assets/capturas_atenea/{captura}">`. If null, gracefully omit (no broken image). All `captura` fields will be `null` initially — the directory exists for future population.
- "Problemas conocidos" section with warning styling
- JS: `fetch('/api/guia?q=' + encodeURIComponent(query))`

- [ ] **Step 5: Write Panel 4 — Consulta Inteligente**

Dashboard + table interface:
- Top row: 4 stat cards (Total asuntos, Civil, Penal, Ejecución) with counts
- Chart area: horizontal bar chart of procedures by type (pure CSS, no chart library)
- Plazos section: table of upcoming deadlines this week
- Filterable table of all procedures (filter by tipo, fase, text search)
- Natural language search box that uses `/api/asistente` with `consulta_datos` intent
- JS: `fetch('/api/estadisticas')` on load, `fetch('/api/procedimientos?tipo=X&fase=Y')` on filter

- [ ] **Step 6: Write JS — tab switching, LLM status check, initialization**

```javascript
// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.panel).classList.add('active');
    });
});

// LLM status check on load
fetch('/api/estado').then(r => r.json()).then(data => {
    const dot = document.getElementById('llm-status');
    dot.className = 'status-dot ' + (data.estado === 'ok' ? 'online' : 'fallback');
    dot.title = data.proveedor + ' (' + data.estado + ')';
});

// Load statistics on Panel 4 init
// ... fetch and render stats
```

- [ ] **Step 7: Test frontend visually**

```bash
cd "D:/PROYECTOS CLAUDE/ATENEA-IA-Demo"
python app.py
```

Open http://localhost:5050, verify:
1. Dashboard loads with institutional styling
2. 4 tabs switch correctly
3. Chat sends messages and receives responses (fallback mode if no API keys)
4. Resolution generator form works
5. Guide search returns results
6. Statistics dashboard shows data

- [ ] **Step 8: Commit frontend**

```bash
git add ATENEA-IA-Demo/index.html
git commit -m "feat(atenea-demo): professional dashboard HTML with 4 panels (chat, resolution generator, guide, statistics)"
```

---

## Chunk 3: Polish and Verification (Tasks 5-7)

### Task 5: Integration testing

- [ ] **Step 1: Test all 4 panels end-to-end in fallback mode (no API keys)**

Start server, verify each panel returns meaningful responses from `fallback.json`.

- [ ] **Step 2: Test with real LLM (if API key available)**

Add a Claude/Groq API key to `config.json`, restart server, verify:
- Chat produces LLM-quality responses
- Resolution generator uses templates + LLM
- Status indicator shows green

- [ ] **Step 3: Test intent detection edge cases**

Test these queries in the chat and verify correct intent detection:
- "¿Qué trámite toca después de la contestación en un JVB?" → tramite_siguiente
- "Redacta un auto de sobreseimiento provisional" → generar_resolucion
- "¿Cómo se registra un auxilio judicial en ATENEA?" → guia_atenea
- "No me deja firmar con el portafirmas" → problema_atenea
- "¿Cuántos procedimientos penales hay pendientes?" → consulta_datos
- "¿Qué plazos vencen esta semana?" → plazos
- "Dame las estadísticas del juzgado" → estadisticas
- "¿Qué es el NIG?" → glosario
- "Buenos días" → general

- [ ] **Step 4: Commit any fixes**

```bash
git add -A ATENEA-IA-Demo/
git commit -m "fix(atenea-demo): integration test fixes"
```

---

### Task 6: Visual polish

Use @frontend-design for professional institutional aesthetics.

- [ ] **Step 1: Review and refine colors, spacing, typography**

Ensure the dashboard looks institutional/professional, not generic. Review:
- Header contrast and readability
- Card shadows and border radii
- Button states (hover, active, disabled)
- Chat bubble styling
- Table styling in Panel 4
- Loading states

- [ ] **Step 2: Add responsive touches**

Ensure the demo works well at 1280px+ widths (typical for executive presentations on a projector/large screen).

- [ ] **Step 3: Commit polish**

```bash
git add ATENEA-IA-Demo/index.html
git commit -m "style(atenea-demo): visual polish for institutional presentation quality"
```

---

### Task 7: Final verification and push

Use @superpowers:verification-before-completion before declaring done.

- [ ] **Step 1: Full smoke test**

1. Delete `__pycache__` if exists
2. Run `iniciar.bat` from Windows Explorer (double-click)
3. Verify browser opens automatically
4. Test each panel: chat, generate resolution, search guide, view stats
5. Test offline: remove API keys from config.json, restart, verify fallback works
6. Verify console logging shows queries and responses

- [ ] **Step 2: Create config.ejemplo.json if not already done**

Verify `config.ejemplo.json` exists with empty API keys and `config.json` is in `.gitignore`.

- [ ] **Step 3: Final commit and push**

```bash
cd "D:/PROYECTOS CLAUDE"
git add ATENEA-IA-Demo/
git commit -m "feat(atenea-demo): complete ATENEA IA demo app ready for presentation"
git push origin feature/atenea-ia-demo
```

---

## Execution Notes

- **Task 2 is the largest** (~130 procedures × structured JSON). Use @anthropic-skills:iudex-ia for judicial domain accuracy. Can be parallelized: tramitacion.json + resoluciones.json can be written by one subagent, datos_demo.json by another, guia_atenea.json + glosario.json + fallback.json by a third.
- **Task 3 and Task 4 are independent** and can be worked on in parallel once Task 2 is complete.
- **All person names in datos_demo.json must be completely fictitious.** Never use real names from any source.
- **The HTML (Task 4) will be large** (~1500-2000 lines with inline CSS/JS). This is expected for a single-file dashboard.
