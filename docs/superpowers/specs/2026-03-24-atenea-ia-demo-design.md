# ATENEA IA - Asistente Inteligente de Gestión Procesal (Demo)

## Resumen

Aplicación web standalone (Flask + HTML) que demuestra cómo un agente de IA puede asistir en la gestión procesal judicial integrada con el sistema ATENEA. Dirigida a directivos del CGPJ/Ministerio de Justicia para mostrar el potencial de la IA en la Administración de Justicia.

## Arquitectura

### Stack Tecnológico

- **Backend**: Flask (Python). Única dependencia externa: Flask. LLM via urllib (stdlib)
- **Frontend**: HTML único con CSS/JS inline, dashboard profesional con navegación por pestañas (tabs)
- **LLM**: Híbrido con fallback (Claude → Groq → Gemini → respuestas pre-generadas)
- **Datos**: Ficheros JSON como base de conocimiento
- **Portabilidad**: `iniciar.bat` para doble-click en Windows
- **Puerto**: 5050 (configurable en config.json). Bind a localhost solamente
- **Logging**: Registro de consultas y respuestas en consola para análisis post-demo

### Estructura de Ficheros

```
ATENEA-IA-Demo/
├── app.py                        # Servidor Flask (~1000 líneas)
├── config.json                   # API keys, proveedor LLM activo
├── index.html                    # Dashboard principal
├── conocimiento/
│   ├── tramitacion.json          # Fases procesales por tipo de procedimiento
│   ├── resoluciones.json         # Modelos de resoluciones categorizados
│   ├── guia_atenea.json          # Manual ATENEA indexado por funcionalidad
│   ├── glosario.json             # Terminología procesal
│   ├── datos_demo.json           # ~130 procedimientos ficticios
│   └── fallback.json             # Respuestas pre-generadas para modo offline
├── assets/
│   └── capturas_atenea/          # Screenshots del manual para guía visual
└── iniciar.bat                   # Arranque con doble-click
```

### config.json Schema

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

### iniciar.bat

```bat
@echo off
pip install flask >nul 2>&1
echo Iniciando ATENEA IA en http://localhost:5050 ...
python app.py
```

Comprueba/instala Flask y arranca el servidor. El propio `app.py` abre el navegador tras bindear el puerto (vía `webbrowser.open` en un timer thread de 1.5s).

### API Endpoints

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| GET | `/` | Sirve index.html | - | HTML |
| POST | `/api/asistente` | Chat principal | `{"mensaje": "...", "historial": [...]}` | `{"respuesta": "...", "intencion": "...", "fuente": "claude\|groq\|fallback", "datos": {...}}` |
| POST | `/api/resolucion` | Generar resolución | `{"tipo": "providencia", "procedimiento": "JVB", "numero": "45/2026", "contexto": "..."}` | `{"texto": "...", "fuente": "..."}` |
| GET | `/api/guia` | Buscar en guía ATENEA | `?q=inhibicion` | `{"resultados": [{"titulo": "...", "contenido": "...", "captura": "..."}]}` |
| GET | `/api/procedimientos` | Consultar procedimientos | `?tipo=JVB&fase=vista` | `{"procedimientos": [...], "total": N}` |
| GET | `/api/estadisticas` | Dashboard estadístico | - | `{"por_tipo": {...}, "por_fase": {...}, "plazos_semana": [...]}` |
| GET | `/api/estado` | Estado del LLM | - | `{"proveedor": "claude", "estado": "ok\|fallback\|offline"}` |

## Interfaz: 4 Paneles

**Navegación**: Barra lateral izquierda con 4 pestañas (tabs). Solo un panel visible a la vez. Panel 1 activo por defecto.

### Cabecera
- Logo institucional + "ATENEA IA - Asistente Inteligente de Gestión Procesal"
- Indicador estado LLM: verde (Claude/LLM conectado), amarillo (fallback), rojo (offline)
- Nombre del juzgado demo: "Juzgado de Primera Instancia e Instrucción nº 1 de Demostración"

### Panel 1: Asistente de Tramitación (pantalla principal)
- Chat conversacional con el agente IA judicial
- Detección de intenciones por regex + enriquecimiento con LLM
- Botones rápidos de consulta frecuente: "Señalamiento", "Admisión demanda", "Vista oral", "Ejecución", "Recurso", "Instrucción penal"
- Indicador visual de fase procesal cuando se consulta un procedimiento concreto
- Historial de conversación en la sesión

### Panel 2: Generador de Resoluciones
- Selector tipo resolución: Providencia, Auto, Decreto, Diligencia de Ordenación, Sentencia, Oficio
- Selector tipo procedimiento: todos los tipos soportados
- Campos contextuales: número procedimiento, partes, hechos clave, petición
- Botón "Generar" → borrador con formato judicial profesional
- Botón "Copiar al portapapeles"
- El LLM usa modelos base como referencia para generar resoluciones procesalmente correctas

### Panel 3: Guía ATENEA
- Buscador por funcionalidad: "¿Cómo hago una inhibición?"
- Árbol de navegación por secciones del manual (Tramitación, Comunicación, Consultas, Utilidades, Configuración, Tareas Pendientes, Guardia, Operaciones Especiales)
- Capturas de pantalla del manual cuando están disponibles
- Sección "Problemas conocidos y soluciones" con workarounds

### Panel 4: Consulta Inteligente de Procedimientos
- Consulta en lenguaje natural sobre los ~130 procedimientos de demo
- Dashboard estadístico: asuntos por tipo, por fase, pendientes
- Vista de plazos/vencimientos por semana
- Tabla filtrable de procedimientos

## Backend: Sistema de IA

### Intenciones

| Intención | Ejemplo | Fuente |
|---|---|---|
| tramite_siguiente | "Tengo un JVB con contestación, ¿qué toca?" | tramitacion.json |
| fase_procesal | "¿En qué fase está un MON tras requerimiento?" | tramitacion.json |
| generar_resolucion | "Redacta providencia admisión prueba JVB" | resoluciones.json + LLM |
| guia_atenea | "¿Cómo registro un auxilio judicial?" | guia_atenea.json |
| problema_atenea | "No me deja firmar solo con LAJ" | guia_atenea.json |
| consulta_datos | "¿Cuántos asuntos penales hay en instrucción?" | datos_demo.json |
| plazos | "¿Qué vence esta semana?" | datos_demo.json |
| estadisticas | "Dame estadísticas de asuntos por tipo" | datos_demo.json |
| glosario | "¿Qué es un NIG?" | glosario.json |

### Flujo Híbrido LLM/Fallback

```
Pregunta usuario
  → Detectar intención (regex sobre patrones procesales)
  → Si no match regex → intención "general" (pasa todo al LLM con contexto amplio)
  → Cargar contexto del JSON correspondiente a la intención
  → Construir prompt: system_prompt + contexto_json + pregunta_usuario
  → Intentar proveedor_activo (config.json, por defecto Claude)
    → Timeout: 8 segundos por proveedor (máx ~16s con 2 fallos antes de fallback)
    → Éxito: respuesta enriquecida con IA + contexto procesal
    → Fallo (timeout/error/rate-limit): intentar siguiente proveedor en cadena
      → Claude → Groq → Gemini → fallback.json
  → Devolver: respuesta + metadatos (intención, fuente, confianza)
```

El LLM recibe el modelo de resolución completo en el prompt cuando la intención es `generar_resolucion`. Para otras intenciones recibe un resumen estructurado del contexto relevante.

### fallback.json Schema

```json
{
  "tramite_siguiente": {
    "JVB_contestacion": "Tras la contestación a la demanda, el siguiente trámite es...",
    "MON_requerimiento": "Emitido el requerimiento de pago, caben dos posibilidades..."
  },
  "guia_atenea": {
    "inhibicion": "Para realizar una inhibición en ATENEA: 1) Acceder a Operaciones Especiales...",
    "firma_laj": "Para firmar un documento solo con LAJ..."
  },
  "glosario": {
    "NIG": "Número de Identificación General. Formato: 5 dígitos población + 2 tipo órgano..."
  }
}
```

Claves: `{intencion}_{subtipo}`. El sistema busca la clave más específica y cae a la genérica si no encuentra match.

Para la intención `general` (sin match de regex), fallback.json incluye una entrada genérica:
```json
"general": {
  "_default": "Puedo ayudarte con tramitación procesal, generar resoluciones, consultar procedimientos o guiarte por ATENEA. ¿Qué necesitas?"
}
```

### Proveedores LLM

| Prioridad | Proveedor | Modelo | Coste |
|---|---|---|---|
| 1 | Anthropic (Claude) | claude-sonnet-4-6 / claude-haiku-4-5 | API key de pago |
| 2 | Groq | llama-3.1-8b-instant | Gratis |
| 3 | Google | gemini-2.0-flash | Gratis |
| 4 | Fallback | respuestas pre-generadas | Offline |

### System Prompt

Prompt especializado en derecho procesal español usando conocimiento del skill iudex-ia:
- Rol: Letrado de la Administración de Justicia experto
- Contexto: LEC, LECrim, LOPJ, CC, CP
- Instrucciones: respuestas procesalmente precisas, citar artículos cuando proceda
- Formato: respuestas concisas, estructuradas, con pasos claros

## Base de Conocimiento

### Tipos de Procedimiento

**Civil:**
JVB (Verbal), ORD (Ordinario), OR5 (Ordinario especial), JVD (Verbal desahucio), JVU (Verbal urgente), MON (Monitorio), VRB (Verbal arrendaticio), DCT (Divorcio contencioso), DMA (Divorcio mutuo acuerdo), MMC (Modificación medidas contenciosa), F02 (Familia genérico), ITR (Internamiento), X58 (Jurisdicción voluntaria), X53 (Conciliación)

**Penal:**
DUD (Diligencias urgentes), DPA (Diligencias previas), LEV (Juicio leve), LEI (Leve investigado), POP (Procedimiento ordinario penal), SU (Sumario), JRD (Juicio rápido)

**Ejecución Civil:**
ETJ (Títulos judiciales), ENJ (Títulos no judiciales), EJH (Hipotecaria), POJ (Posesoria judicial), POH (Posesoria hipotecaria), POI (Posesoria inscrita)

**Ejecución Penal:**
EJ (Ejecutoria penal), EFM (Ejecutoria faltas/multas), COG (Costas generales)

### Datos de Demo: ~130 Procedimientos Ficticios

5+ procedimientos de cada tipo, en distintas fases, con:
- NIG ficticio (formato real: 5 dígitos población + 2 tipo órgano + 1 orden + 4 año + 7 número)
- Partes con nombres completamente inventados (nunca datos reales)
- Abogados y procuradores ficticios
- Fechas coherentes con 2025-2026
- Plazos y vencimientos realistas
- Estados procesales variados por tipo

Distribución por tipo (5-8 de cada uno en distintas fases):

| Tipo | Cant. | Fases representadas |
|---|---|---|
| JVB | 8 | Admisión, contestación, vista, sentencia, firmeza, ejecución |
| ORD | 6 | Admisión, contestación, audiencia previa, juicio, sentencia |
| OR5 | 5 | Admisión, contestación, audiencia previa, juicio, sentencia |
| JVD | 5 | Admisión, requerimiento, vista, lanzamiento, archivo |
| JVU | 5 | Admisión, vista, sentencia, firmeza |
| MON | 7 | Requerimiento, oposición→JVB, sin oposición→ejecución, archivo |
| VRB | 5 | Admisión, vista, sentencia |
| DCT | 5 | Admisión, medidas provisionales, prueba, vista, sentencia |
| DMA | 5 | Admisión, traslado fiscal, ratificación, sentencia, firmeza |
| MMC | 5 | Admisión, traslado, prueba, vista, resolución |
| F02 | 5 | Admisión, traslado fiscal, comparecencia, resolución |
| ITR | 5 | Admisión, reconocimiento forense, comparecencia, auto |
| X58 | 5 | Admisión, traslado, comparecencia, auto |
| X53 | 5 | Solicitud, citación, acto conciliación, avenencia/sin avenencia |
| DUD | 6 | Incoación, declaración, transformación DPA, juicio rápido, conformidad |
| DPA | 7 | Incoación, instrucción, auto PA, sobreseimiento, inhibición |
| LEV | 5 | Incoación, señalamiento, juicio, sentencia, firmeza |
| LEI | 5 | Incoación, señalamiento, juicio, sentencia, firmeza |
| POP | 5 | Instrucción, calificación, juicio oral, sentencia |
| SU | 5 | Procesamiento, conclusión sumario, apertura juicio oral |
| JRD | 5 | Instrucción guardia, conformidad, señalamiento, juicio |
| ETJ | 5 | Despacho, requerimiento, embargo, subasta, archivo |
| ENJ | 5 | Despacho, oposición, requerimiento, embargo, archivo |
| EJH | 5 | Despacho, requerimiento, subasta, adjudicación |
| POJ | 5 | Admisión, requerimiento, lanzamiento |
| POH | 5 | Admisión, requerimiento, lanzamiento |
| POI | 5 | Admisión, requerimiento, lanzamiento |
| EJ | 5 | Liquidación condena, cumplimiento, beneficios penitenciarios, libertad |
| EFM | 5 | Liquidación, requerimiento multa, pago, impago→arresto |
| COG | 5 | Tasación, traslado, aprobación/impugnación |

### Modelos de Resoluciones

Categorías con modelos base para que el LLM genere variaciones:
- **Providencias**: admisión prueba, señalamiento, traslado, requerimiento
- **Autos**: admisión demanda, sobreseimiento, procesamiento, inhibición, entrada y registro
- **Decretos**: admisión demanda, archivo, despacho ejecución
- **Diligencias de Ordenación**: firmeza, traslado, señalamiento, suspensión
- **Sentencias**: conformidad penal (estructura)
- **Oficios**: policía, registro civil, forense, centro penitenciario

### Guía ATENEA Indexada

Secciones del manual organizadas por funcionalidad:
- Tramitación: aceptación escritos, tramitación guiada, compositor documentos, firma
- Comunicación: itineraciones, notificaciones, LexNET
- Consultas: múltiple, por escritos, profesional, agenda plazos, agenda presos
- Utilidades: devolución escritos, anulación
- Configuración: parámetros sistema
- Tareas Pendientes: bandeja firma, revisión
- Guardia: registro, reparto
- Operaciones Especiales: transformación, acumulación, inhibición, archivo, requisitorias

Problemas conocidos con workarounds (fuente: CCOO Asturias 2025).

## Criterios de Éxito

1. La demo arranca con doble-click en `iniciar.bat`
2. Los 4 paneles funcionan. Consultas locales (JSON) responden en <1s. Consultas LLM en <15s (incluyendo posible fallback entre proveedores)
3. El asistente responde preguntas procesales con precisión jurídica
4. El generador produce resoluciones con formato judicial correcto
5. La guía ATENEA muestra pasos claros para cada funcionalidad
6. La consulta de procedimientos devuelve datos coherentes
7. Si no hay conexión a internet, el modo fallback funciona sin errores
8. La interfaz tiene aspecto institucional profesional

## Restricciones

- Única dependencia externa: Flask (se instala automáticamente vía `iniciar.bat`)
- LLM via urllib (stdlib), sin requests ni otras librerías HTTP
- Todos los nombres de personas son completamente ficticios (inventados, nunca datos reales)
- No se usan datos de conversaciones ni documentos reales del usuario
- Portable: toda la aplicación en una carpeta
- Compatible con Windows 10/11
- `config.json` contiene API keys: no incluir en repositorios públicos. Se provee `config.ejemplo.json` sin keys
- Servidor Flask bindeado a `127.0.0.1` (localhost), no accesible desde red
- Validación básica en Panel 2: no permite combinaciones sin sentido (ej. Sentencia para X53 Conciliación)
