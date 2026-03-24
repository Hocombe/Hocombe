#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENEA IA - Asistente Inteligente de Gestión Procesal (Demo)
Servidor Flask con detección de intenciones, cadena LLM y fallback offline.
"""

import json
import os
import re
import urllib.request
import urllib.error
import ssl
import threading
import webbrowser
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def cargar_config():
    ruta = os.path.join(BASE_DIR, 'config.json')
    if not os.path.exists(ruta):
        ruta = os.path.join(BASE_DIR, 'config.ejemplo.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = cargar_config()

# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------
def cargar_json(nombre):
    ruta = os.path.join(BASE_DIR, 'conocimiento', nombre)
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    logging.warning(f'Fichero no encontrado: {ruta}')
    return {}

TRAMITACION = cargar_json('tramitacion.json')
RESOLUCIONES = cargar_json('resoluciones.json')
GUIA = cargar_json('guia_atenea.json')
GLOSARIO = cargar_json('glosario.json')
DATOS_DEMO = cargar_json('datos_demo.json')
FALLBACK = cargar_json('fallback.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

# ---------------------------------------------------------------------------
# Tipos de procedimiento por jurisdicción (para clasificación)
# ---------------------------------------------------------------------------
TIPOS_PENAL = {'DUD', 'DPA', 'LEV', 'LEI', 'POP', 'SU', 'JRD'}
TIPOS_EJ_CIVIL = {'ETJ', 'ENJ', 'EJH', 'POJ', 'POH', 'POI'}
TIPOS_EJ_PENAL = {'EJ', 'EFM', 'COG'}

# ---------------------------------------------------------------------------
# Intent Detection (regex)
# ---------------------------------------------------------------------------
PATRONES_INTENCION = [
    ('tramite_siguiente', [
        r'(?:qué|que)\s+(?:trámite|tramite|toca|sigue|paso)',
        r'siguiente\s+(?:trámite|tramite|paso|fase)',
        r'(?:después|despues)\s+de\s+(?:la\s+)?(?:contestación|contestacion|admisión|admision|vista|demanda)',
        r'(?:qué|que)\s+hago\s+(?:ahora|después|despues)',
    ]),
    ('fase_procesal', [
        r'(?:en\s+qué|en\s+que)\s+fase',
        r'fase\s+(?:procesal|actual|del)',
        r'estado\s+(?:procesal|del\s+procedimiento)',
    ]),
    ('generar_resolucion', [
        r'(?:redacta|genera|elabora|escribe|haz|dame)\s+(?:una?\s+)?(?:providencia|auto|decreto|diligencia|sentencia|oficio)',
        r'(?:borrador|modelo|plantilla)\s+de\s+(?:providencia|auto|decreto|diligencia|sentencia|oficio)',
        r'(?:providencia|auto|decreto|diligencia|sentencia|oficio)\s+(?:de|para|que)',
    ]),
    ('guia_atenea', [
        r'(?:cómo|como)\s+(?:se\s+)?(?:hace|hago|registro|tramito|notifico|envío|envio)',
        r'(?:en\s+)?atenea\s+(?:cómo|como|dónde|donde)',
        r'paso\s+a\s+paso',
        r'(?:dónde|donde)\s+(?:está|esta|encuentro)',
        r'(?:cómo|como)\s+(?:uso|utilizo|accedo)',
    ]),
    ('problema_atenea', [
        r'no\s+(?:me\s+)?(?:deja|permite|puedo|funciona)',
        r'(?:error|fallo|problema|bug)\s+(?:en\s+)?atenea',
        r'no\s+(?:aparece|sale|muestra)',
        r'(?:no\s+)?funciona',
    ]),
    ('consulta_datos', [
        r'(?:cuántos|cuantos|cuáles|cuales|qué|que)\s+(?:procedimientos|asuntos|casos)',
        r'(?:busca|buscar|lista|listar|muestra|mostrar)\s+(?:procedimientos|asuntos)',
        r'procedimientos?\s+(?:de\s+tipo|civiles?|penales?|de\s+ejecución|de\s+ejecucion)',
        r'(?:dame|muéstrame|muestrame)\s+(?:los\s+)?(?:procedimientos|asuntos|casos)',
    ]),
    ('plazos', [
        r'(?:qué|que)\s+(?:plazos?|vence|vencimientos?)',
        r'plazos?\s+(?:esta\s+semana|pendientes?|próximos?|proximos?)',
        r'vencimientos?\s+(?:esta\s+semana|pendientes?)',
        r'(?:qué|que)\s+(?:hay|tenemos)\s+(?:esta\s+semana|pendiente)',
    ]),
    ('estadisticas', [
        r'estad[ií]sticas?',
        r'(?:resumen|informe|datos)\s+(?:del\s+)?(?:juzgado|tribunal|órgano|organo)',
        r'(?:cuántos|cuantos)\s+(?:asuntos|procedimientos)\s+(?:hay|tenemos)',
        r'(?:dame|muéstrame|muestrame)\s+(?:las\s+)?estad[ií]sticas',
    ]),
    ('glosario', [
        r'(?:qué|que)\s+(?:es|significa)\s+(?:un[ao]?\s+)?',
        r'(?:definición|definicion|significado)\s+de',
        r'(?:qué|que)\s+(?:quiere\s+decir|son)\s+',
    ]),
]


def detectar_intencion(mensaje):
    """Detecta la intención del usuario mediante patrones regex."""
    texto = mensaje.lower().strip()
    for intencion, patrones in PATRONES_INTENCION:
        for patron in patrones:
            if re.search(patron, texto):
                return intencion
    return 'general'


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Eres un Letrado de la Administración de Justicia experto en el sistema judicial español y en el Sistema de Gestión Procesal ATENEA.

Tu rol es asistir a los funcionarios judiciales (gestores, tramitadores, auxilio judicial, LAJ, jueces y magistrados) en:
- Tramitación procesal: fases, trámites, plazos y resoluciones
- Uso del sistema ATENEA: guía paso a paso de funcionalidades
- Generación de borradores de resoluciones judiciales
- Consultas sobre procedimientos y estadísticas

Legislación de referencia: LEC, LECrim, LOPJ, CC, CP, LO 1/2025 (MASC).
Cita artículos cuando proceda. Respuestas concisas, estructuradas y profesionales.
Usa viñetas y negritas para conceptos clave.
Si proporcionan datos de contexto de la base de conocimiento, úsalos para respuestas precisas.
Responde SIEMPRE en español."""

CADENA_PROVEEDORES = ['claude', 'groq', 'gemini']


# ---------------------------------------------------------------------------
# LLM Calls
# ---------------------------------------------------------------------------
def _llamar_claude(config_prov, mensajes, max_tokens, temperatura):
    """API de Anthropic (Messages API)."""
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
    """APIs compatibles con OpenAI (Groq, Gemini)."""
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
    """Cadena de fallback: proveedor_activo → resto → None."""
    max_tokens = CONFIG.get('max_tokens', 1024)
    temperatura = CONFIG.get('temperatura', 0.3)
    activo = CONFIG.get('proveedor_activo', 'claude')

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
            logging.info(f'LLM: éxito con {proveedor} ({len(texto)} chars)')
            return texto, proveedor
        except Exception as e:
            logging.warning(f'LLM: fallo {proveedor}: {e}')
            continue

    return None, 'ninguno'


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------
def _extraer_tipos_procedimiento(mensaje):
    """Extrae tipos de procedimiento mencionados en el mensaje."""
    tipos_encontrados = []
    msg_upper = mensaje.upper()
    for jurisdiccion_data in TRAMITACION.values():
        if isinstance(jurisdiccion_data, dict):
            for tipo in jurisdiccion_data:
                if tipo in msg_upper:
                    tipos_encontrados.append(tipo)
    return tipos_encontrados


def construir_contexto(intencion, mensaje):
    """Construye el contexto JSON relevante para la intención detectada."""
    if intencion in ('tramite_siguiente', 'fase_procesal'):
        tipos = _extraer_tipos_procedimiento(mensaje)
        if tipos:
            contexto = {}
            for jur_data in TRAMITACION.values():
                if isinstance(jur_data, dict):
                    for tipo in tipos:
                        if tipo in jur_data:
                            contexto[tipo] = jur_data[tipo]
            return json.dumps(contexto, ensure_ascii=False, indent=2)
        todos_tipos = [t for j in TRAMITACION.values() if isinstance(j, dict) for t in j]
        return json.dumps({
            "nota": "No se identificó tipo de procedimiento en la consulta.",
            "tipos_disponibles": todos_tipos
        }, ensure_ascii=False)

    elif intencion == 'generar_resolucion':
        return json.dumps(RESOLUCIONES, ensure_ascii=False, indent=2)[:8000]

    elif intencion in ('guia_atenea', 'problema_atenea'):
        return json.dumps(GUIA, ensure_ascii=False, indent=2)[:6000]

    elif intencion == 'glosario':
        return json.dumps(GLOSARIO, ensure_ascii=False, indent=2)[:4000]

    elif intencion in ('consulta_datos', 'plazos', 'estadisticas'):
        return _generar_resumen_datos()

    return ''


def _generar_resumen_datos():
    """Genera resumen estadístico de los datos de demo."""
    procs = DATOS_DEMO.get('procedimientos', [])
    hoy = datetime.now()
    semana = hoy + timedelta(days=7)

    resumen = {
        'total': len(procs),
        'por_tipo': {},
        'por_fase': {},
        'plazos_proximos': []
    }

    for p in procs:
        t = p.get('tipo', '?')
        resumen['por_tipo'][t] = resumen['por_tipo'].get(t, 0) + 1
        f = p.get('fase_actual', 'Sin fase')
        resumen['por_fase'][f] = resumen['por_fase'].get(f, 0) + 1
        for plazo in p.get('plazos', []):
            if plazo.get('estado') == 'pendiente':
                try:
                    fecha_p = datetime.strptime(plazo['fecha'], '%Y-%m-%d')
                    if hoy <= fecha_p <= semana:
                        resumen['plazos_proximos'].append({
                            'proc': f"{t} {p.get('numero', '?')}",
                            'plazo': plazo.get('tipo', ''),
                            'fecha': plazo['fecha']
                        })
                except (ValueError, KeyError):
                    pass

    resumen['plazos_proximos'].sort(key=lambda x: x.get('fecha', ''))
    return json.dumps(resumen, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Fallback Resolver
# ---------------------------------------------------------------------------
def buscar_fallback(intencion, mensaje):
    """Busca la respuesta pre-generada más relevante."""
    bloque = FALLBACK.get(intencion, {})
    if not bloque:
        bloque = FALLBACK.get('general', {})

    texto_lower = mensaje.lower()
    mejor = None
    mejor_score = 0
    for clave, respuesta in bloque.items():
        if clave.startswith('_'):
            continue
        palabras_clave = clave.lower().replace('_', ' ').split()
        score = sum(1 for p in palabras_clave if p in texto_lower)
        if score > mejor_score:
            mejor_score = score
            mejor = respuesta

    if mejor:
        return mejor
    return bloque.get('_default',
        FALLBACK.get('general', {}).get('_default',
            'Soy el asistente ATENEA IA. Puedo ayudarte con tramitación procesal, '
            'resoluciones judiciales, uso de ATENEA y consultas de procedimientos.'))


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))


@app.route('/assets/<path:filename>')
def serve_asset(filename):
    ruta = os.path.join(BASE_DIR, 'assets', filename)
    if os.path.exists(ruta):
        return send_file(ruta)
    return '', 404


@app.route('/api/estado')
def api_estado():
    """Estado del proveedor LLM activo."""
    activo = CONFIG.get('proveedor_activo', 'claude')
    config_prov = CONFIG.get('proveedores', {}).get(activo, {})
    tiene_key = bool(config_prov.get('api_key'))
    return jsonify({
        'proveedor': activo,
        'modelo': config_prov.get('modelo', ''),
        'estado': 'ok' if tiene_key else 'fallback'
    })


@app.route('/api/asistente', methods=['POST'])
def api_asistente():
    """Chat principal con el asistente IA."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'respuesta': 'Error al procesar la solicitud.', 'intencion': 'error', 'fuente': 'sistema'})

    mensaje = data.get('mensaje', '').strip()
    historial = data.get('historial', [])

    if not mensaje:
        return jsonify({
            'respuesta': 'Por favor, escribe tu consulta.',
            'intencion': 'error',
            'fuente': 'sistema'
        })

    intencion = detectar_intencion(mensaje)
    contexto = construir_contexto(intencion, mensaje)
    logging.info(f'Consulta: "{mensaje}" → intención: {intencion}')

    mensajes_llm = [
        {'role': 'system', 'content': SYSTEM_PROMPT + '\n\nCONTEXTO DE LA BASE DE CONOCIMIENTO:\n' + contexto}
    ]
    for h in historial[-6:]:
        mensajes_llm.append(h)
    mensajes_llm.append({'role': 'user', 'content': mensaje})

    respuesta, fuente = llamar_llm(mensajes_llm)

    if respuesta is None:
        respuesta = buscar_fallback(intencion, mensaje)
        fuente = 'fallback'

    datos_extra = None
    if intencion in ('consulta_datos', 'plazos', 'estadisticas'):
        try:
            datos_extra = json.loads(contexto)
        except (json.JSONDecodeError, TypeError):
            pass

    logging.info(f'Respuesta ({fuente}): {respuesta[:80]}...')
    return jsonify({
        'respuesta': respuesta,
        'intencion': intencion,
        'fuente': fuente,
        'datos': datos_extra
    })


@app.route('/api/resolucion', methods=['POST'])
def api_resolucion():
    """Generar borrador de resolución judicial."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'texto': 'Error al procesar la solicitud.', 'fuente': 'error'})

    tipo_res = data.get('tipo', '').lower()
    tipo_proc = data.get('procedimiento', '').upper()
    numero = data.get('numero', '')
    contexto_usuario = data.get('contexto', '')

    # Buscar plantilla en la categoría correspondiente
    # Las claves en resoluciones.json son plurales: providencias, autos, decretos...
    categorias_buscar = [
        tipo_res + 's',
        tipo_res + 'es',
        tipo_res,
        'diligencias_ordenacion' if 'diligencia' in tipo_res else ''
    ]

    modelo_base = ''
    for cat_key in categorias_buscar:
        categoria = RESOLUCIONES.get(cat_key, [])
        if isinstance(categoria, list):
            for modelo in categoria:
                aplicables = modelo.get('procedimientos_aplicables', [])
                if not aplicables or tipo_proc in aplicables:
                    modelo_base = modelo.get('modelo', '')
                    break
        if modelo_base:
            break

    # Si no encontró modelo específico, usar el primero de la categoría
    if not modelo_base:
        for cat_key in categorias_buscar:
            categoria = RESOLUCIONES.get(cat_key, [])
            if isinstance(categoria, list) and categoria:
                modelo_base = categoria[0].get('modelo', '')
                break

    prompt = (
        f"Genera una resolución judicial de tipo **{tipo_res}** para un procedimiento "
        f"**{tipo_proc} {numero}**.\n\n"
        f"Contexto del caso: {contexto_usuario}\n\n"
    )
    if modelo_base:
        prompt += (
            f"Usa este modelo como base y adáptalo al contexto proporcionado. "
            f"Rellena los campos entre corchetes con datos coherentes:\n\n{modelo_base}"
        )
    else:
        prompt += (
            f"Genera el texto completo de la resolución con formato judicial profesional. "
            f"Incluye encabezamiento con localidad y fecha, cuerpo con fundamentos, "
            f"y parte dispositiva."
        )

    mensajes = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt}
    ]

    respuesta, fuente = llamar_llm(mensajes)
    if respuesta is None:
        if modelo_base:
            respuesta = modelo_base
            fuente = 'modelo_base'
        else:
            respuesta = f'No se pudo generar la resolución. No hay modelo disponible para {tipo_res} en {tipo_proc} y no hay conexión con el LLM.'
            fuente = 'error'

    return jsonify({'texto': respuesta, 'fuente': fuente})


@app.route('/api/guia')
def api_guia():
    """Búsqueda en la guía de ATENEA."""
    query = request.args.get('q', '').lower().strip()

    if not query:
        return jsonify({'resultados': GUIA.get('secciones', [])})

    palabras = query.split()
    resultados = []

    for seccion in GUIA.get('secciones', []):
        for sub in seccion.get('subsecciones', []):
            texto_buscar = ' '.join([
                sub.get('titulo', ''),
                sub.get('contenido', ''),
                ' '.join(sub.get('palabras_clave', []))
            ]).lower()
            score = sum(1 for p in palabras if p in texto_buscar)
            if score > 0:
                resultados.append({
                    'titulo': sub.get('titulo', ''),
                    'contenido': sub.get('contenido', ''),
                    'pasos': sub.get('pasos', []),
                    'captura': sub.get('captura'),
                    'seccion': seccion.get('titulo', ''),
                    'score': score
                })

    for prob in GUIA.get('problemas_conocidos', []):
        texto_buscar = ' '.join([
            prob.get('problema', ''),
            prob.get('sintoma', ''),
            prob.get('workaround', '')
        ]).lower()
        score = sum(1 for p in palabras if p in texto_buscar)
        if score > 0:
            resultados.append({
                'titulo': prob['problema'],
                'contenido': f"**Síntoma:** {prob.get('sintoma', '')}\n\n**Solución:** {prob.get('workaround', '')}",
                'pasos': [],
                'captura': None,
                'seccion': 'Problemas conocidos',
                'fuente': prob.get('fuente', ''),
                'es_problema': True,
                'score': score + 5
            })

    resultados.sort(key=lambda x: x.get('score', 0), reverse=True)
    return jsonify({'resultados': resultados[:10]})


@app.route('/api/procedimientos')
def api_procedimientos():
    """Consulta de procedimientos de demo."""
    tipo = request.args.get('tipo', '').upper()
    fase = request.args.get('fase', '').lower()
    q = request.args.get('q', '').lower()

    procs = DATOS_DEMO.get('procedimientos', [])
    resultados = []

    for p in procs:
        if tipo and p.get('tipo', '') != tipo:
            continue
        if fase and fase not in p.get('fase_actual', '').lower():
            continue
        if q and q not in json.dumps(p, ensure_ascii=False).lower():
            continue
        resultados.append(p)

    return jsonify({'procedimientos': resultados, 'total': len(resultados)})


@app.route('/api/estadisticas')
def api_estadisticas():
    """Dashboard estadístico."""
    procs = DATOS_DEMO.get('procedimientos', [])
    por_tipo = {}
    por_fase = {}
    por_jurisdiccion = {'civil': 0, 'penal': 0, 'ejecucion_civil': 0, 'ejecucion_penal': 0}
    plazos_semana = []
    hoy = datetime.now()
    semana = hoy + timedelta(days=7)

    for p in procs:
        t = p.get('tipo', '?')
        por_tipo[t] = por_tipo.get(t, 0) + 1

        f = p.get('fase_actual', 'Sin fase')
        por_fase[f] = por_fase.get(f, 0) + 1

        if t in TIPOS_PENAL:
            por_jurisdiccion['penal'] += 1
        elif t in TIPOS_EJ_CIVIL:
            por_jurisdiccion['ejecucion_civil'] += 1
        elif t in TIPOS_EJ_PENAL:
            por_jurisdiccion['ejecucion_penal'] += 1
        else:
            por_jurisdiccion['civil'] += 1

        for plazo in p.get('plazos', []):
            if plazo.get('estado') == 'pendiente':
                try:
                    fecha_p = datetime.strptime(plazo['fecha'], '%Y-%m-%d')
                    if hoy <= fecha_p <= semana:
                        plazos_semana.append({
                            'proc': f"{t} {p.get('numero', '?')}",
                            'plazo': plazo.get('tipo', ''),
                            'fecha': plazo['fecha']
                        })
                except (ValueError, KeyError):
                    pass

    plazos_semana.sort(key=lambda x: x.get('fecha', ''))

    return jsonify({
        'total': len(procs),
        'por_tipo': por_tipo,
        'por_fase': por_fase,
        'por_jurisdiccion': por_jurisdiccion,
        'plazos_semana': plazos_semana
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    puerto = CONFIG.get('puerto', 5050)
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{puerto}')).start()
    logging.info(f'ATENEA IA iniciado en http://localhost:{puerto}')
    app.run(host='127.0.0.1', port=puerto, debug=False)
