#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portal Judicial Unificado - Servidor Central
Tribunal de Instancia de Vilagarcía de Arousa
-----------------------------------------------
Gestiona todos los módulos:
  - Agenda Judicial
  - Calculadora de Vencimientos
  - Gestión de Vacaciones
  - ClipBox (Modelos de Resoluciones)
  - Alardes Judiciales
  - Peritos Judiciales
  - Boletín Trimestral
-----------------------------------------------
Sin permisos de administrador. Portable.
"""

import os
import sys
import json
import html as _html_mod
import shutil
import socket
import threading
import webbrowser
import zipfile
import tempfile
import time as _time_mod
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path

# Flask
try:
    from flask import Flask, jsonify, request, send_from_directory, send_file, Response
    from flask_cors import CORS
except ImportError:
    print("ERROR: Flask no está instalado.")
    print("Instala con: pip install flask flask-cors")
    input("Pulsa Enter para cerrar...")
    sys.exit(1)

# ─────────────────────────────────────────────
# RUTAS BASE
# ─────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATOS_DIR  = os.environ.get('PORTAL_DATOS_DIR',  os.path.join(BASE_DIR, 'datos'))
BACKUP_DIR = os.environ.get('PORTAL_BACKUP_DIR', os.path.join(BASE_DIR, 'backups'))
CONFIG_DIR = os.environ.get('PORTAL_CONFIG_DIR', os.path.join(BASE_DIR, 'config'))
LOG_DIR    = os.path.join(BASE_DIR, 'logs')

# Ficheros JSON de cada módulo
F_AGENDA      = os.path.join(DATOS_DIR, 'agenda.json')
F_VENCIMIENTOS= os.path.join(DATOS_DIR, 'vencimientos.json')
F_VACACIONES  = os.path.join(DATOS_DIR, 'vacaciones.json')
F_CLIPBOX     = os.path.join(DATOS_DIR, 'clipbox.json')
F_PERITOS     = os.path.join(DATOS_DIR, 'peritos.json')
F_BOLETIN     = os.path.join(DATOS_DIR, 'boletin.json')
F_INSTRUCCION = os.path.join(DATOS_DIR, 'instruccion_penal.json')
F_MINUTAS     = os.path.join(DATOS_DIR, 'minutas.json')
F_CORREOS     = os.path.join(DATOS_DIR, 'correos.json')
F_AUXILIOS    = os.path.join(DATOS_DIR, 'auxilios.json')
F_PRESOS      = os.path.join(DATOS_DIR, 'presos.json')
F_NOTIFICAJUD = os.path.join(DATOS_DIR, 'notificajud.json')
F_CONFIG_LLM  = os.path.join(DATOS_DIR, 'config_llm.json')
F_GLOSARIO_IA = os.path.join(DATOS_DIR, 'glosario_ia.txt')
F_GUARDIAS    = os.path.join(DATOS_DIR, 'guardias.json')
F_AUSENCIAS   = os.path.join(DATOS_DIR, 'ausencias.json')
F_PRESENCIA   = os.path.join(DATOS_DIR, 'presencia.json')
F_PRESENCIA_EDIT = os.path.join(DATOS_DIR, 'presencia_edicion.json')
F_ARCHIVO     = os.path.join(DATOS_DIR, 'archivo.json')
F_DIR3        = os.path.join(DATOS_DIR, 'dir3.json')
F_CHAT        = os.path.join(DATOS_DIR, 'chat.json')
F_TABLON      = os.path.join(DATOS_DIR, 'tablon.json')
F_NOTIFICACIONES = os.path.join(DATOS_DIR, 'notificaciones.json')

# ── Ficheros per-PC (cada PC tiene su propio estado de sesión) ──
_HOSTNAME = socket.gethostname()
F_USUARIO     = os.path.join(CONFIG_DIR, f'_nombre_usuario_{_HOSTNAME}.txt')

# Carpeta de red para backup secundario (opcional — si no existe, se ignora)
RED_BACKUP = os.path.join(BASE_DIR, 'config', 'ruta_red.txt')

# ── Multiusuario ──────────────────────────────────────────
USUARIOS_DIR  = os.path.join(CONFIG_DIR, 'usuarios')       # config/usuarios/{id}.json
DATOS_USR_DIR = os.path.join(DATOS_DIR,  'usuarios')       # datos/usuarios/{id}/modulo.json
F_USUARIOS_LISTA     = os.path.join(CONFIG_DIR, 'usuarios_lista.json')
F_SUPERADMIN         = os.path.join(CONFIG_DIR, 'superadmin.json')
F_SUPERADMIN_RECOVERY = os.path.join(CONFIG_DIR, 'superadmin_recovery.txt')

# Módulos que pueden ser privados por usuario
MODULOS_PRIVADOS = ['agenda', 'vencimientos', 'vacaciones', 'clipbox', 'alardes', 'peritos', 'instruccion_penal', 'minutas', 'correos', 'auxilios', 'boletin', 'presos', 'notificajud', 'ausencias', 'archivo']

# ── Equipos / Grupos de trabajo ───────────────────────────
GRUPOS_DIR = os.path.join(DATOS_DIR, 'grupos')
F_GRUPOS   = os.path.join(CONFIG_DIR, 'grupos.json')

# ── Superadmin ────────────────────────────────────────────
import hashlib, secrets as _secrets

_superadmin_token = None   # token de sesión activo (en memoria)

def _hash_pwd(pwd):
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest()

def cargar_superadmin():
    if os.path.exists(F_SUPERADMIN):
        return cargar_json(F_SUPERADMIN)
    return {}

def _es_superadmin_activo(token):
    return token and token == _superadmin_token

# ── Usuarios ──────────────────────────────────────────────
def _sin_acentos(texto):
    """Elimina acentos/diacríticos de un texto (á→a, ñ→n, etc.)."""
    import unicodedata
    s = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')

def _id_usuario(nombre):
    """Convierte un nombre a un identificador seguro de fichero."""
    s = _sin_acentos(nombre)
    return ''.join(c for c in s.upper() if c.isalnum() or c in '-_').strip('-_') or 'USUARIO'

def cargar_usuarios():
    """Devuelve la lista de usuarios [{id, nombre, avatar, modulos_privados}]."""
    if os.path.exists(F_USUARIOS_LISTA):
        return cargar_json(F_USUARIOS_LISTA).get('usuarios', [])
    return []

def guardar_usuarios(lista):
    guardar_json(F_USUARIOS_LISTA, {'usuarios': lista})

def datos_usuario_dir(uid):
    """Carpeta de datos privados del usuario."""
    d = os.path.join(DATOS_USR_DIR, uid)
    os.makedirs(d, exist_ok=True)
    return d

def f_dato_usuario(uid, modulo):
    """Ruta al fichero JSON privado de un módulo para un usuario."""
    return os.path.join(datos_usuario_dir(uid), f'{modulo}.json')

# ── Grupos / Equipos ──────────────────────────────────────
def cargar_grupos():
    """Devuelve la lista de grupos [{id, nombre, icono, color, modulos, miembros}]."""
    if os.path.exists(F_GRUPOS):
        return cargar_json(F_GRUPOS).get('grupos', [])
    return []

def guardar_grupos(lista):
    guardar_json(F_GRUPOS, {'grupos': lista})

def datos_grupo_dir(gid):
    """Carpeta de datos compartidos del grupo."""
    d = os.path.join(GRUPOS_DIR, gid)
    os.makedirs(d, exist_ok=True)
    return d

def f_dato_grupo(gid, modulo):
    """Ruta al fichero JSON de un módulo para un grupo."""
    return os.path.join(datos_grupo_dir(gid), f'{modulo}.json')

# Configuración de backup automático
F_BACKUP_CONFIG = os.path.join(BASE_DIR, 'config', 'backup_config.json')
DEFAULT_BACKUP_CONFIG = {
    'frecuencia_horas': 0,          # 0 = desactivado
    'hora_inicio': '',              # '' = sin restricción, ej: '08:00'
    'hora_fin': '',                 # '' = sin restricción, ej: '20:00'
    'rutas_externas': [],           # lista de rutas adicionales
    'modulos': ['agenda', 'vencimientos', 'vacaciones', 'clipbox', 'peritos', 'instruccion_penal', 'boletin', 'presos', 'notificajud', 'guardias', 'ausencias', 'archivo'],
    'max_backups_locales': 30,      # días a conservar
    'intervalo_backup_min': 5,      # minutos mínimos entre backups del mismo módulo
    'ultimo_auto': None
}

# Estado del scheduler en memoria
_backup_scheduler_timer = None

# ─────────────────────────────────────────────
# INICIALIZACIÓN
# ─────────────────────────────────────────────
for d in [DATOS_DIR, BACKUP_DIR, CONFIG_DIR, LOG_DIR, USUARIOS_DIR, DATOS_USR_DIR, GRUPOS_DIR]:
    os.makedirs(d, exist_ok=True)

# Datos por defecto para cada módulo
DEFAULTS = {
    F_AGENDA: {
        'senalamientos': [], 'guardias': [], 'tiposProcedimiento': [],
        'plazas': ['Plaza 1 - SOFIA LEONOR', 'Plaza 2 - PATRICIA FERNANDEZ', 'Plaza 3 - PEDRO ADRIAN GÓMEZ'],
        'letrados': ['BENITA GÁNDARA', 'ISABEL RODRÍGUEZ', 'VIOLETA REBOREDO'],
        'instruccionesPorPlaza': {}, 'coloresPersonalizados': {},
        'nombreTribunal': 'Tribunal de Instancia de Vilagarcía de Arousa',
        'intervaloHuecos': 30
    },
    F_VENCIMIENTOS: {
        'avisos': [], 'festivos': [], 'configuracion': {},
        'plazaSeleccionada': 'Vilagarcía de Arousa'
    },
    F_VACACIONES: {
        'funcionarios': [], 'vacaciones': [], 'festivos': [],
        'minimos': {
            'Civil': 2, 'Penal': 3, 'Ejecución': 1,
            'Auxilio Judicial': 2, 'Decanato': 1, 'Registro Civil': 1
        }
    },
    F_CLIPBOX: {'clips': []},
    F_PERITOS: {
        'especialidades': [], 'peritos': [], 'selecciones': [],
        'settings': {'abrirNavegadorAutomaticamente': True, 'idioma': 'es', 'tema': 'light'}
    },
    F_BOLETIN:     {'plazas': {}, 'datos': {}, 'version': '1.0'},
    F_INSTRUCCION: {'procedimientos': []},
    F_MINUTAS:     {'minutas': [], 'plazas_propias': []},
    F_CORREOS:     {'sugerencias': {}, 'borradores': {}, 'sesion': None, 'mapa_localidad_cp': {}, 'config': {'tema': 'oscuro', 'panel_w': 520}},
    F_AUXILIOS:    {'auxilios': []},
    F_NOTIFICAJUD: {
        'notificaciones': [], 'funcionarios': [], 'plazas': [],
        'diligenciasHistorial': [], 'configTurnos': {},
        'turnosAsignaciones': {}, 'serviciosTurnos': []
    },
    F_AUSENCIAS: {
        'plazas': [],
        'ausencias': [],
        'plantillasCargos': [
            {'nombre': 'Magistrado/a', 'colorDefecto': '#3b82f6'},
            {'nombre': 'Letrado/a de la Adm. de Justicia', 'colorDefecto': '#10b981'},
            {'nombre': 'Fiscal', 'colorDefecto': '#f59e0b'},
            {'nombre': 'Forense', 'colorDefecto': '#8b5cf6'}
        ]
    },
    F_PRESOS:   {'presos': []},
    F_GUARDIAS: {'guardias': []},
    F_ARCHIVO: {
        'plazas': [],
        'solicitudes': []
    },
    F_TABLON: {'anuncios': []},
    F_NOTIFICACIONES: {}
}

def inicializar_datos():
    """Crea los ficheros JSON con valores por defecto si no existen."""
    for fichero, defecto in DEFAULTS.items():
        if not os.path.exists(fichero):
            guardar_json(fichero, defecto)
            log(f"Fichero creado: {os.path.basename(fichero)}")

# ─────────────────────────────────────────────
# CACHÉ EN MEMORIA + TRACKING DE SALUD
# ─────────────────────────────────────────────
import collections

_cache = {}            # {ruta: datos} — última lectura exitosa de cada JSON
_salud_eventos = collections.deque(maxlen=200)  # buffer circular de eventos
_salud_contadores = {  # contadores del día actual
    'fecha': None,
    'lecturas_ok': 0,
    'lecturas_error': 0,
    'cache_hits': 0,
    'backups_ok': 0,
    'backups_error': 0,
}
_salud_ultima_lectura_ok = None  # timestamp de la última lectura exitosa

def _salud_resetear_dia():
    """Resetea contadores si cambió el día."""
    hoy = datetime.now().strftime('%Y-%m-%d')
    if _salud_contadores['fecha'] != hoy:
        _salud_contadores['fecha'] = hoy
        _salud_contadores['lecturas_ok'] = 0
        _salud_contadores['lecturas_error'] = 0
        _salud_contadores['cache_hits'] = 0
        _salud_contadores['backups_ok'] = 0
        _salud_contadores['backups_error'] = 0

def _salud_evento(tipo, modulo, mensaje=''):
    """Registra un evento de salud."""
    _salud_resetear_dia()
    _salud_eventos.append({
        'ts': datetime.now().isoformat(),
        'tipo': tipo,
        'modulo': modulo,
        'mensaje': mensaje
    })
    # Actualizar contadores
    if tipo == 'lectura_ok':
        _salud_contadores['lecturas_ok'] += 1
    elif tipo == 'lectura_error':
        _salud_contadores['lecturas_error'] += 1
    elif tipo == 'cache_hit':
        _salud_contadores['cache_hits'] += 1
    elif tipo == 'backup_ok':
        _salud_contadores['backups_ok'] += 1
    elif tipo == 'backup_error':
        _salud_contadores['backups_error'] += 1

# ─────────────────────────────────────────────
# HELPERS JSON
# ─────────────────────────────────────────────
def cargar_json(ruta, _reintentos=4):
    global _salud_ultima_lectura_ok
    _mod = os.path.basename(ruta)
    for intento in range(_reintentos):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            # ✅ Lectura exitosa → actualizar caché
            _cache[ruta] = datos
            _salud_ultima_lectura_ok = datetime.now().isoformat()
            # Solo registrar evento para ficheros de datos principales (no configs)
            if ruta in DEFAULTS:
                _salud_evento('lectura_ok', _mod)
            return datos
        except FileNotFoundError:
            if intento < _reintentos - 1:
                _time_mod.sleep(0.1)
                continue
            log(f"Fichero no encontrado tras {_reintentos} intentos: {ruta}", 'WARN')
        except (json.JSONDecodeError, PermissionError) as e:
            if intento < _reintentos - 1:
                _time_mod.sleep(0.15)
                continue
            log(f"Error cargando {ruta} tras {_reintentos} intentos: {e}", 'ERROR')
        except Exception as e:
            if intento < _reintentos - 1:
                _time_mod.sleep(0.15)
                continue
            log(f"Error cargando {ruta} tras {_reintentos} intentos: {e}", 'ERROR')
    # ✅ Todos los reintentos fallaron → usar caché si disponible
    if ruta in _cache:
        _salud_evento('cache_hit', _mod, f'Sirviendo datos cacheados tras {_reintentos} intentos fallidos')
        log(f"[CACHÉ] Sirviendo datos cacheados para {_mod}", 'WARN')
        return _cache[ruta]
    _salud_evento('lectura_error', _mod, f'Sin caché disponible tras {_reintentos} intentos')
    return DEFAULTS.get(ruta, {})

# ── File locking robusto para entorno multi-servidor en red ────────────

class LockError(Exception):
    """No se pudo adquirir el lock de fichero."""
    pass

class _NoGuardar(Exception):
    """Señal para salir de editar_json sin guardar (validación fallida bajo lock)."""
    pass

def _adquirir_lock_fichero(ruta, timeout=12.0):
    """Crea un fichero .lock exclusivo para evitar escrituras simultáneas en red.
    NUNCA continúa sin lock — lanza LockError si no se puede adquirir."""
    lock = ruta + '.lock'
    inicio = _time_mod.time()
    while True:
        try:
            # O_CREAT|O_EXCL es atómico en SMB v2/v3 → operación segura en red
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f'{_HOSTNAME}:{os.getpid()}'.encode())
            os.close(fd)
            return lock
        except FileExistsError:
            # Si el lock lleva más de 15s → proceso cayó sin liberar
            try:
                edad = _time_mod.time() - os.path.getmtime(lock)
                if edad > 15:
                    # Verificar que el lock es realmente stale leyendo su contenido
                    try:
                        with open(lock, 'r') as lf:
                            contenido = lf.read().strip()
                        log(f"Lock stale ({edad:.0f}s) de {contenido}, liberando: {lock}", 'WARN')
                    except Exception:
                        pass
                    try:
                        os.remove(lock)
                    except FileNotFoundError:
                        pass  # Otro servidor ya lo eliminó
                    except PermissionError:
                        _time_mod.sleep(0.1)
                    continue
            except (OSError, FileNotFoundError):
                pass  # El lock desapareció entre la comprobación
            if _time_mod.time() - inicio > timeout:
                log(f"TIMEOUT adquiriendo lock ({timeout}s): {lock}", 'ERROR')
                raise LockError(f"No se pudo adquirir lock: {lock}")
            _time_mod.sleep(0.05 + 0.02 * ((_time_mod.time() - inicio) / timeout))

def _liberar_lock_fichero(lock):
    try: os.remove(lock)
    except Exception: pass

def _tmp_unico(ruta):
    """Genera nombre de fichero temporal único por hostname+PID."""
    return f'{ruta}.tmp.{_HOSTNAME}.{os.getpid()}'

def guardar_json(ruta, datos):
    lock = _adquirir_lock_fichero(ruta)
    try:
        tmp = _tmp_unico(ruta)
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
        # ✅ Escritura exitosa → actualizar caché
        _cache[ruta] = datos
        return True
    except LockError:
        raise
    except Exception as e:
        log(f"Error guardando {ruta}: {e}", 'ERROR')
        return False
    finally:
        _liberar_lock_fichero(lock)

# ── Context manager para read-modify-write atómico ────────────────────
from contextlib import contextmanager

@contextmanager
def editar_json(ruta):
    """Lee un JSON bajo lock, permite modificarlo y lo escribe atómicamente.
    El lock se mantiene durante TODO el ciclo lectura-modificación-escritura.
    Uso:
        with editar_json(ruta) as datos:
            datos['clave'] = valor
    Al salir del with, se guarda automáticamente."""
    lock = _adquirir_lock_fichero(ruta)
    try:
        # Lectura interna sin lock (ya lo tenemos)
        datos = {}
        if os.path.exists(ruta):
            for _intento in range(3):
                try:
                    with open(ruta, 'r', encoding='utf-8') as f:
                        datos = json.load(f)
                    break
                except (json.JSONDecodeError, PermissionError, FileNotFoundError):
                    _time_mod.sleep(0.1)
                except Exception as e:
                    log(f"Error leyendo {ruta} bajo lock: {e}", 'ERROR')
                    break
        if not datos:
            datos = DEFAULTS.get(ruta, {})
            if callable(getattr(datos, 'copy', None)):
                datos = datos.copy()

        yield datos

        # Escritura atómica
        tmp = _tmp_unico(ruta)
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
    except _NoGuardar:
        pass  # Abortar sin guardar (validación fallida) — no logear error
    except LockError:
        raise
    except Exception as e:
        log(f"Error en editar_json({ruta}): {e}", 'ERROR')
        raise
    finally:
        _liberar_lock_fichero(lock)

# ─────────────────────────────────────────────
# BACKUP
# ─────────────────────────────────────────────
def cargar_backup_config():
    """Carga la configuración de backup, con valores por defecto."""
    if os.path.exists(F_BACKUP_CONFIG):
        cfg = cargar_json(F_BACKUP_CONFIG)
        # Asegurar claves por defecto
        for k, v in DEFAULT_BACKUP_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    return dict(DEFAULT_BACKUP_CONFIG)

# Timestamp del último backup por módulo (throttle configurable desde panel de backup)
_ultimo_backup_ts: dict = {}

def hacer_backup(modulo, datos):
    """Backup puntual de un módulo en carpeta local (llamado al guardar datos).
    Se omite si el mismo módulo fue respaldado hace menos de intervalo_backup_min minutos
    (valor configurable en el panel de backup del portal)."""
    global _ultimo_backup_ts
    ahora = datetime.now()
    ultimo = _ultimo_backup_ts.get(modulo)
    if ultimo:
        cfg = cargar_backup_config()
        intervalo_seg = int(cfg.get('intervalo_backup_min', 5)) * 60
        if (ahora - ultimo).total_seconds() < intervalo_seg:
            return  # demasiado pronto, omitir este backup
    _ultimo_backup_ts[modulo] = ahora
    try:
        hoy = datetime.now().strftime('%Y-%m-%d')
        ts  = datetime.now().strftime('%H%M%S')
        carpeta = os.path.join(BACKUP_DIR, hoy)
        os.makedirs(carpeta, exist_ok=True)
        destino = os.path.join(carpeta, f'{modulo}_{ts}.json')
        with open(destino, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        # Backup a carpeta de red legacy (ruta_red.txt)
        if os.path.exists(RED_BACKUP):
            with open(RED_BACKUP, 'r', encoding='utf-8') as f:
                ruta_red = f.read().strip()
            if ruta_red and os.path.isdir(ruta_red):
                carpeta_red = os.path.join(ruta_red, hoy)
                os.makedirs(carpeta_red, exist_ok=True)
                shutil.copy2(destino, os.path.join(carpeta_red, f'{modulo}_{ts}.json'))
        cfg = cargar_backup_config()
        _limpiar_backups_antiguos(cfg.get('max_backups_locales', 30))
    except Exception as e:
        log(f"Error en backup ({modulo}): {e}", 'WARNING')

def hacer_backup_completo_auto(etiqueta='auto'):
    """Genera un ZIP completo con los módulos configurados y lo copia a rutas externas."""
    global _backup_scheduler_timer
    cfg = cargar_backup_config()
    modulos_mapa = {
        'agenda': F_AGENDA, 'vencimientos': F_VENCIMIENTOS,
        'vacaciones': F_VACACIONES, 'clipbox': F_CLIPBOX,
        'peritos': F_PERITOS, 'boletin': F_BOLETIN,
        'instruccion_penal': F_INSTRUCCION,
        'minutas': F_MINUTAS, 'correos': F_CORREOS,
        'auxilios': F_AUXILIOS, 'presos': F_PRESOS,
        'notificajud': F_NOTIFICAJUD,
        'guardias': F_GUARDIAS,
        'ausencias': F_AUSENCIAS,
        'archivo': F_ARCHIVO
    }
    try:
        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        nombre_base = f'{etiqueta}_{ts}'
        carpeta_tmp = os.path.join(BACKUP_DIR, nombre_base)
        os.makedirs(carpeta_tmp, exist_ok=True)
        modulos_incluidos = cfg.get('modulos', list(modulos_mapa.keys()))
        for nombre, ruta in modulos_mapa.items():
            if nombre in modulos_incluidos and os.path.exists(ruta):
                shutil.copy2(ruta, os.path.join(carpeta_tmp, f'{nombre}.json'))
        zip_ruta = shutil.make_archive(carpeta_tmp, 'zip', carpeta_tmp)
        shutil.rmtree(carpeta_tmp)
        zip_nombre = os.path.basename(zip_ruta)
        log(f"Backup completo generado: {zip_nombre}")
        _salud_evento('backup_ok', 'backup', zip_nombre)
        # Copiar a rutas externas configuradas
        for ruta_ext in cfg.get('rutas_externas', []):
            try:
                if ruta_ext and os.path.isdir(ruta_ext):
                    shutil.copy2(zip_ruta, os.path.join(ruta_ext, zip_nombre))
                    log(f"Backup copiado a ruta externa: {ruta_ext}")
            except Exception as e:
                log(f"Error copiando a ruta externa {ruta_ext}: {e}", 'WARNING')
        # Actualizar timestamp del último backup automático
        with editar_json(F_BACKUP_CONFIG) as cfg_ts:
            cfg_ts['ultimo_auto'] = datetime.now().isoformat()
        _limpiar_backups_antiguos(cfg.get('max_backups_locales', 30))
        return zip_nombre
    except Exception as e:
        log(f"Error en backup completo ({etiqueta}): {e}", 'ERROR')
        _salud_evento('backup_error', 'backup', str(e))
        return None

def _limpiar_backups_antiguos(dias):
    limite = datetime.now() - timedelta(days=dias)
    try:
        for nombre in os.listdir(BACKUP_DIR):
            ruta = os.path.join(BACKUP_DIR, nombre)
            # Borrar carpetas antiguas por fecha
            if os.path.isdir(ruta):
                try:
                    # Soportar formatos: '2026-03-09', 'auto_2026-03-09_140736', 'manual_2026-03-09_140736'
                    _parte = nombre.split('_', 1)[-1] if '_' in nombre else nombre
                    _fecha_str = _parte[:10]  # 'YYYY-MM-DD'
                    fecha = datetime.strptime(_fecha_str, '%Y-%m-%d')
                    if fecha < limite:
                        shutil.rmtree(ruta)
                except (ValueError, OSError) as e:
                    log(f"Error limpiando backup dir {nombre}: {e}")
            # Borrar ZIPs automáticos más antiguos que el límite
            elif ruta.endswith('.zip'):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(ruta))
                    if mtime < limite:
                        os.remove(ruta)
                except (OSError,) as e:
                    log(f"Error limpiando backup zip {nombre}: {e}")
    except (OSError,) as e:
        log(f"Error en limpieza de backups: {e}")

def _arrancar_scheduler_backup():
    """Programa el siguiente backup automático según la configuración."""
    global _backup_scheduler_timer
    if _backup_scheduler_timer:
        _backup_scheduler_timer.cancel()
        _backup_scheduler_timer = None
    cfg = cargar_backup_config()
    horas = cfg.get('frecuencia_horas', 0)
    if not horas or horas <= 0:
        return
    segundos = horas * 3600
    def _ejecutar():
        cfg2   = cargar_backup_config()
        h_ini  = cfg2.get('hora_inicio', '')
        h_fin  = cfg2.get('hora_fin', '')
        ahora  = datetime.now().strftime('%H:%M')
        en_ventana = True
        if h_ini and h_fin:
            en_ventana = h_ini <= ahora <= h_fin
        if en_ventana:
            hacer_backup_completo_auto('auto')
        else:
            log(f'[BACKUP] Fuera de ventana horaria ({h_ini}–{h_fin}), omitido')
        _arrancar_scheduler_backup()  # reprogramar
    _backup_scheduler_timer = threading.Timer(segundos, _ejecutar)
    _backup_scheduler_timer.daemon = True
    _backup_scheduler_timer.start()
    log(f"Backup automático programado en {horas}h")

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
def log(msg, nivel='INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linea = f"[{ts}] [{nivel}] {msg}"
    print(linea)
    try:
        fichero = os.path.join(LOG_DIR, f"portal_{datetime.now().strftime('%Y-%m-%d')}.log")
        with open(fichero, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except (OSError, PermissionError):
        pass  # si falla el log, al menos se imprimió en consola

# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app, origins=['http://localhost:*', 'http://127.0.0.1:*'])

# ── PORTAL HTML ──────────────────────────────
@app.route('/')
def index():
    html = os.path.join(BASE_DIR, 'portal.html')
    if os.path.exists(html):
        with open(html, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>portal.html no encontrado</h1>", 404

# ── HEALTH ───────────────────────────────────
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.0', 'timestamp': datetime.now().isoformat()})

# ══════════════════════════════════════════════
# MÓDULO 1 — AGENDA JUDICIAL
# ══════════════════════════════════════════════
@app.route('/api/agenda', methods=['GET'])
def agenda_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('agenda', F_AGENDA)))

@app.route('/api/agenda', methods=['POST'])
def agenda_post():
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('agenda', F_AGENDA)
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('agenda', actual)
    return jsonify({'success': True})

# ── Timestamp de agenda en fichero (funciona en multi-servidor) ──
F_AGENDA_TS = os.path.join(CONFIG_DIR, 'agenda_timestamp.json')

def _get_agenda_ts():
    if os.path.exists(F_AGENDA_TS):
        try: return cargar_json(F_AGENDA_TS).get('ts', '')
        except Exception: pass
    return ''

def _set_agenda_ts():
    ts = datetime.now().isoformat()
    guardar_json(F_AGENDA_TS, {'ts': ts})
    return ts

# Compatibilidad con la Agenda existente (usa /api/datos)
@app.route('/api/datos', methods=['GET', 'POST'])
def agenda_datos_compat():
    ruta = _resolver_fichero_modulo('agenda', F_AGENDA)
    if request.method == 'GET':
        d = cargar_json(ruta)
        return jsonify({
            'senalamientos':       d.get('senalamientos', []),
            'guardias':            d.get('guardias', []),
            'plazas':              d.get('plazas', []),
            'letrados':            d.get('letrados', []),
            'tiposProcedimiento':  d.get('tiposProcedimiento', []),
            'instruccionesPorPlaza': d.get('instruccionesPorPlaza', {}),
            'coloresPersonalizados': d.get('coloresPersonalizados', {}),
            'nombreTribunal':      d.get('nombreTribunal', ''),
            'intervaloHuecos':     d.get('intervaloHuecos', 30),
            'tiposCategorias':     d.get('tiposCategorias', {'civil':[], 'penal':[], 'ejecucion':[], 'ajn':[]})
        })
    datos = request.get_json(force=True) or {}
    # Los heartbeats de presencia (action='registrarPresencia') no contienen
    # datos de agenda; devolver éxito sin mezclar, guardar ni hacer backup.
    if datos.get('action') == 'registrarPresencia':
        return jsonify({'success': True})
    # ── Protección contra sobreescritura con datos vacíos ──
    with editar_json(ruta) as actual:
        senals_servidor = actual.get('senalamientos', [])
        senals_cliente  = datos.get('senalamientos')
        if senals_cliente is not None and len(senals_cliente) == 0 and len(senals_servidor) > 5:
            log(f"[PROTECCIÓN] Rechazado guardado de agenda: cliente envía 0 señalamientos, "
                f"servidor tiene {len(senals_servidor)}. Posible localStorage vacío.", 'WARN')
            return jsonify({'success': False, 'error': 'proteccion_datos_vacios',
                            'msg': f'El servidor tiene {len(senals_servidor)} señalamientos. '
                                   f'No se permite sobreescribir con datos vacíos.'})
        actual.update(datos)
        hacer_backup('agenda', actual)
    _set_agenda_ts()
    guardar_json(F_PRESENCIA_EDIT, {})
    return jsonify({'success': True})

# ── Acciones directas del asistente IA sobre la agenda ──────────────────────
@app.route('/api/agenda/senalamiento', methods=['POST'])
def agenda_crear_senalamiento():
    """Crea un señalamiento directamente desde el asistente IA."""
    d = request.get_json(force=True) or {}
    fecha       = d.get('fecha', '')
    hora        = d.get('hora', '')
    tipo        = d.get('tipo', '')
    plaza       = d.get('plaza', '')
    expediente  = d.get('expediente', '---')
    letrado     = d.get('letrado', '')
    sala        = d.get('sala', '')
    partes      = d.get('partes', '')
    observaciones = d.get('observaciones', '')

    if not fecha or not hora or not tipo:
        return jsonify({'success': False, 'error': 'Faltan campos obligatorios: fecha, hora, tipo'}), 400
    try:
        date.fromisoformat(fecha)
    except ValueError:
        return jsonify({'success': False, 'error': f'Fecha inválida: {fecha}'}), 400
    if not re.match(r'^\d{2}:\d{2}$', hora):
        return jsonify({'success': False, 'error': f'Hora inválida: {hora}'}), 400

    ruta = _resolver_fichero_modulo('agenda', F_AGENDA)
    with editar_json(ruta) as actual:
        senalamientos = actual.get('senalamientos', [])
        conflicto = next((s for s in senalamientos
                          if s.get('fecha') == fecha and s.get('hora') == hora
                          and s.get('plaza') == plaza and not s.get('anulado')), None)
        nuevo = {
            'id': int(datetime.now().timestamp() * 1000),
            'fecha': fecha, 'hora': hora, 'tipo': tipo, 'plaza': plaza,
            'expediente': expediente, 'letrado': letrado, 'sala': sala,
            'partes': partes, 'observaciones': observaciones,
            'anulado': False, 'celebrado': False, 'suspendido': False
        }
        senalamientos.append(nuevo)
        actual['senalamientos'] = senalamientos
        tipos_existentes = actual.get('tiposProcedimiento', [])
        if tipo and tipo not in tipos_existentes:
            tipos_existentes.append(tipo)
            actual['tiposProcedimiento'] = tipos_existentes
        hacer_backup('agenda', actual)
    _set_agenda_ts()
    return jsonify({
        'success': True, 'senalamiento': nuevo,
        'conflicto': bool(conflicto)
    })

@app.route('/api/agenda/senalamiento/anular', methods=['POST'])
def agenda_anular_senalamiento():
    """Anula, suspende, celebra o borra un señalamiento identificado por ID."""
    d = request.get_json(force=True) or {}
    sen_id      = d.get('id')
    accion_mod  = d.get('accion', 'anular')  # 'anular' | 'suspender' | 'celebrar' | 'borrar'

    if not sen_id:
        return jsonify({'success': False, 'error': 'Se requiere ID del señalamiento'}), 400

    ruta = _resolver_fichero_modulo('agenda', F_AGENDA)
    with editar_json(ruta) as actual:
        senalamientos = actual.get('senalamientos', [])
        matches = [s for s in senalamientos if s.get('id') == sen_id]
        if not matches:
            return jsonify({'success': False, 'error': 'No se encontró el señalamiento'})
        target = matches[0]
        fmt = f"{target.get('tipo','')} {target.get('expediente','')} — {target.get('fecha','')} {target.get('hora','')}"
        if accion_mod == 'borrar':
            actual['senalamientos'] = [s for s in senalamientos if s.get('id') != sen_id]
        elif accion_mod == 'suspender':
            target['suspendido'] = True; target['anulado'] = False; target['celebrado'] = False
        elif accion_mod == 'celebrar':
            target['celebrado'] = True; target['suspendido'] = False; target['anulado'] = False
        else:
            target['anulado'] = True; target['suspendido'] = False; target['celebrado'] = False
        hacer_backup('agenda', actual)
    _set_agenda_ts()
    return jsonify({'success': True, 'senalamiento': fmt.strip(), 'accion': accion_mod})

@app.route('/api/agenda/senalamiento/modificar', methods=['POST'])
def agenda_modificar_senalamiento():
    """Modifica campos de un señalamiento (hora, fecha, plaza, tipo)."""
    d = request.get_json(force=True) or {}
    sen_id  = d.get('id')
    cambios = d.get('cambios', {})

    if not sen_id:
        return jsonify({'success': False, 'error': 'Se requiere ID del señalamiento'}), 400
    if not cambios:
        return jsonify({'success': False, 'error': 'No se indicaron cambios'}), 400

    ruta = _resolver_fichero_modulo('agenda', F_AGENDA)
    with editar_json(ruta) as actual:
        senalamientos = actual.get('senalamientos', [])
        matches = [s for s in senalamientos if s.get('id') == sen_id]
        if not matches:
            return jsonify({'success': False, 'error': 'No se encontró el señalamiento'})
        target = matches[0]
        campos_validos = ('hora', 'fecha', 'plaza', 'tipo', 'expediente', 'sala', 'partes', 'observaciones')
        aplicados = []
        for campo, valor in cambios.items():
            if campo in campos_validos and valor:
                target[campo] = valor
                aplicados.append(campo)
        if not aplicados:
            return jsonify({'success': False, 'error': 'Ningún campo válido para modificar'})
        hacer_backup('agenda', actual)
    _set_agenda_ts()
    fmt = f"{target.get('tipo','')} {target.get('expediente','')} — {target.get('fecha','')} {target.get('hora','')}"
    return jsonify({'success': True, 'senalamiento': fmt.strip(), 'campos': aplicados})

@app.route('/api/datos/timestamp', methods=['GET'])
def agenda_timestamp():
    """Devuelve el timestamp del último guardado de la agenda (desde fichero)"""
    return jsonify({'timestamp': _get_agenda_ts()})

@app.route('/api/presencia', methods=['GET', 'POST', 'DELETE'])
def agenda_presencia():
    """Indicador de presencia: quién está creando un señalamiento ahora.
    Usa fichero separado (presencia_edicion.json) para no colisionar con el chat."""
    if request.method == 'GET':
        presencia = None
        if os.path.exists(F_PRESENCIA_EDIT):
            try:
                d = cargar_json(F_PRESENCIA_EDIT)
                if d and d.get('caduca'):
                    caduca = datetime.fromisoformat(d['caduca'])
                    if datetime.now() <= caduca:
                        presencia = d
                    else:
                        guardar_json(F_PRESENCIA_EDIT, {})  # limpiar caducada
            except Exception:
                pass
        return jsonify({'presencia': presencia})
    elif request.method == 'POST':
        d = request.get_json(force=True) or {}
        usuario = d.get('usuario', 'Alguien')
        presencia = {
            'usuario': usuario,
            'desde': datetime.now().isoformat(),
            'caduca': (datetime.now() + timedelta(minutes=3)).isoformat()
        }
        guardar_json(F_PRESENCIA_EDIT, presencia)
        return jsonify({'success': True})
    elif request.method == 'DELETE':
        guardar_json(F_PRESENCIA_EDIT, {})
        return jsonify({'success': True})

@app.route('/api/nombre-usuario', methods=['GET', 'POST'])
def nombre_usuario():
    if request.method == 'POST':
        nombre = (request.get_json(force=True) or {}).get('nombre', 'USUARIO')
        lock = _adquirir_lock_fichero(F_USUARIO)
        try:
            with open(F_USUARIO, 'w', encoding='utf-8') as f:
                f.write(nombre)
        finally:
            _liberar_lock_fichero(lock)
        return jsonify({'success': True, 'nombre': nombre})
    if os.path.exists(F_USUARIO):
        with open(F_USUARIO, 'r', encoding='utf-8') as f:
            return jsonify({'success': True, 'nombre': f.read().strip()})
    return jsonify({'success': True, 'nombre': None})

# ══════════════════════════════════════════════
# MULTIUSUARIO — Gestión de usuarios
# ══════════════════════════════════════════════

@app.route('/api/usuarios', methods=['GET'])
def usuarios_get():
    """Lista todos los usuarios (sin exponer pin_hash)."""
    usuarios = cargar_usuarios()
    seguros = []
    for u in usuarios:
        uu = {k: v for k, v in u.items() if k != 'pin_hash'}
        uu['tiene_pin'] = bool(u.get('pin_hash'))
        seguros.append(uu)
    return jsonify({'usuarios': seguros})

@app.route('/api/usuarios', methods=['POST'])
def usuario_crear():
    """Crea un nuevo usuario."""
    datos = request.get_json(force=True) or {}
    nombre = (datos.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
    uid = _id_usuario(nombre)
    with editar_json(F_USUARIOS_LISTA) as data:
        lista = data.get('usuarios', [])
        # Verificar que no existe ya
        if any(u['id'] == uid for u in lista):
            return jsonify({'success': False, 'error': 'Ya existe un usuario con ese nombre'}), 409
        nuevo = {
            'id': uid,
            'nombre': nombre,
            'avatar': datos.get('avatar', '👤'),
            'modulos_privados': datos.get('modulos_privados', []),
            'rol': datos.get('rol', 'funcionario'),
            'pestanas_visibles': datos.get('pestanas_visibles', None),  # None = todas
            'permisos': datos.get('permisos', {}),
            'principal': bool(datos.get('principal', False))
        }
        # Solo un usuario puede ser principal
        if nuevo['principal']:
            for u in lista:
                u['principal'] = False
        lista.append(nuevo)
        data['usuarios'] = lista
    # Crear carpeta de datos
    os.makedirs(datos_usuario_dir(uid), exist_ok=True)
    log(f"Usuario creado: {uid} ({nombre})")
    return jsonify({'success': True, 'usuario': nuevo})

@app.route('/api/usuarios/<uid>', methods=['PUT'])
def usuario_editar(uid):
    """Edita un usuario existente."""
    datos = request.get_json(force=True) or {}
    with editar_json(F_USUARIOS_LISTA) as data:
        lista = data.get('usuarios', [])
        for u in lista:
            if u['id'] == uid:
                if 'nombre' in datos:
                    u['nombre'] = datos['nombre'].strip()
                if 'avatar' in datos:
                    u['avatar'] = datos['avatar']
                if 'modulos_privados' in datos:
                    u['modulos_privados'] = datos['modulos_privados']
                if 'permisos' in datos:
                    u['permisos'] = datos['permisos']
                if 'rol' in datos:
                    u['rol'] = datos['rol']
                if 'pestanas_visibles' in datos:
                    u['pestanas_visibles'] = datos['pestanas_visibles']  # None = todas
                if 'principal' in datos:
                    u['principal'] = bool(datos['principal'])
                    # Solo un usuario puede ser principal
                    if u['principal']:
                        for other in lista:
                            if other['id'] != uid:
                                other['principal'] = False
                data['usuarios'] = lista
                return jsonify({'success': True, 'usuario': u})
    return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

@app.route('/api/usuarios/<uid>', methods=['DELETE'])
def usuario_eliminar(uid):
    """Elimina un usuario (sin borrar sus datos)."""
    with editar_json(F_USUARIOS_LISTA) as data:
        lista = data.get('usuarios', [])
        nueva = [u for u in lista if u['id'] != uid]
        if len(nueva) == len(lista):
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        data['usuarios'] = nueva
    log(f"Usuario eliminado: {uid}")
    return jsonify({'success': True})

@app.route('/api/usuarios/<uid>/verify-pin', methods=['POST'])
def usuario_verify_pin(uid):
    """Verifica el PIN de un usuario (endpoint público, no requiere auth)."""
    datos = request.get_json(force=True) or {}
    pin = str(datos.get('pin', '')).strip()
    for u in cargar_usuarios():
        if u['id'] == uid:
            pin_hash = u.get('pin_hash')
            if not pin_hash:
                return jsonify({'ok': True, 'sin_pin': True})
            return jsonify({'ok': _hash_pwd(pin) == pin_hash})
    return jsonify({'ok': False}), 404

@app.route('/api/usuarios/<uid>/pin', methods=['POST'])
def usuario_set_pin(uid):
    """Establece o elimina el PIN de un usuario. Requiere sesión superadmin."""
    token = request.headers.get('X-Superadmin-Token') or ''
    if not _es_superadmin_activo(token):
        return jsonify({'success': False, 'error': 'Requiere sesión superadmin'}), 403
    datos = request.get_json(force=True) or {}
    pin = str(datos.get('pin', '')).strip()
    with editar_json(F_USUARIOS_LISTA) as data:
        lista = data.get('usuarios', [])
        for u in lista:
            if u['id'] == uid:
                if pin:
                    if not pin.isdigit() or len(pin) != 4:
                        return jsonify({'success': False, 'error': 'El PIN debe tener exactamente 4 dígitos numéricos'}), 400
                    u['pin_hash'] = _hash_pwd(pin)
                else:
                    u.pop('pin_hash', None)
                data['usuarios'] = lista
                log(f"PIN {'establecido' if pin else 'eliminado'} para usuario {uid}")
                return jsonify({'success': True, 'tiene_pin': bool(pin)})
    return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

# ── Superadmin endpoints ──────────────────────────────────

@app.route('/api/superadmin/status', methods=['GET'])
def superadmin_status():
    cfg = cargar_superadmin()
    token = request.headers.get('X-Superadmin-Token') or ''
    return jsonify({
        'configurado': bool(cfg.get('password_hash')),
        'activo': _es_superadmin_activo(token)
    })

@app.route('/api/superadmin/setup', methods=['POST'])
def superadmin_setup():
    global _superadmin_token
    datos = request.get_json(force=True) or {}
    pwd   = datos.get('password', '').strip()
    token_actual = request.headers.get('X-Superadmin-Token') or ''

    if len(pwd) < 4:
        return jsonify({'success': False, 'error': 'La contraseña debe tener al menos 4 caracteres'}), 400

    recovery_code = _secrets.token_hex(8).upper()  # 16 chars hex
    with editar_json(F_SUPERADMIN) as cfg:
        # Si ya está configurado, requiere sesión activa o código de recuperación
        if cfg.get('password_hash'):
            recovery = datos.get('recovery_code', '').strip()
            if not _es_superadmin_activo(token_actual) and recovery != cfg.get('recovery_code', ''):
                return jsonify({'success': False, 'error': 'Sesión superadmin o código de recuperación requerido'}), 403
        cfg['password_hash'] = _hash_pwd(pwd)
        cfg['recovery_code'] = recovery_code
    # Fichero de recuperación en texto plano
    try:
        with open(F_SUPERADMIN_RECOVERY, 'w', encoding='utf-8') as f:
            f.write(f"Portal Judicial — Código de recuperación superadmin\n")
            f.write(f"{'='*50}\n")
            f.write(f"Código: {recovery_code}\n\n")
            f.write(f"Guarda este fichero en un lugar seguro.\n")
            f.write(f"Úsalo en el portal para recuperar el acceso si olvidas la contraseña.\n")
    except Exception:
        pass
    # Iniciar sesión automáticamente
    _superadmin_token = _secrets.token_hex(32)
    log("Contraseña superadmin configurada")
    return jsonify({'success': True, 'token': _superadmin_token})

@app.route('/api/superadmin/login', methods=['POST'])
def superadmin_login():
    global _superadmin_token
    datos = request.get_json(force=True) or {}
    cfg   = cargar_superadmin()
    if not cfg.get('password_hash'):
        return jsonify({'success': False, 'error': 'Superadmin no configurado'}), 400

    pwd      = datos.get('password', '').strip()
    recovery = datos.get('recovery_code', '').strip()

    ok = False
    if pwd and _hash_pwd(pwd) == cfg.get('password_hash'):
        ok = True
    elif recovery and recovery.upper() == cfg.get('recovery_code', ''):
        ok = True

    if not ok:
        return jsonify({'success': False, 'error': 'Contraseña o código de recuperación incorrecto'}), 401

    _superadmin_token = _secrets.token_hex(32)
    log("Login superadmin OK")
    return jsonify({'success': True, 'token': _superadmin_token})

@app.route('/api/superadmin/logout', methods=['POST'])
def superadmin_logout():
    global _superadmin_token
    _superadmin_token = None
    return jsonify({'success': True})

@app.route('/api/usuarios/<uid>/permisos', methods=['PUT'])
def usuario_permisos(uid):
    token = request.headers.get('X-Superadmin-Token') or ''
    if not _es_superadmin_activo(token):
        return jsonify({'success': False, 'error': 'Requiere sesión superadmin'}), 403
    datos = request.get_json(force=True) or {}
    with editar_json(F_USUARIOS_LISTA) as data:
        lista = data.get('usuarios', [])
        for u in lista:
            if u['id'] == uid:
                u['permisos'] = datos.get('permisos', {})
                u['rol']      = datos.get('rol', 'usuario')
                data['usuarios'] = lista
                return jsonify({'success': True, 'usuario': u})
    return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

# ── Datos privados por usuario ─────────────────────────────

@app.route('/api/usuario/<uid>/datos/<modulo>', methods=['GET'])
def usuario_datos_get(uid, modulo):
    """Devuelve datos privados de un módulo para un usuario."""
    if modulo not in MODULOS_PRIVADOS:
        return jsonify({'error': 'Módulo no privado'}), 400
    ruta = f_dato_usuario(uid, modulo)
    defaults_map = {
        'clipbox':        {'clips': []},
        'vencimientos':   {'avisos': [], 'festivos': [], 'configuracion': {}},
        'agenda':         {'senalamientos': [], 'guardias': [], 'tiposProcedimiento': [], 'plazas': [], 'letrados': []},
        'vacaciones':     {'funcionarios': [], 'vacaciones': [], 'festivos': []},
        'peritos':        {'especialidades': [], 'peritos': [], 'selecciones': []},
        'instruccion_penal': {'procedimientos': []},
        'minutas':        {'minutas': [], 'plazas_propias': []},
        'correos':        {'sugerencias': {}, 'borradores': {}, 'sesion': None, 'mapa_localidad_cp': {}, 'config': {}},
        'auxilios':       {'auxilios': []},
        'boletin':        {'plazas': {}, 'datos': {}, 'version': '1.0'},
        'alardes':        {},
        'ausencias':      {'plazas': [], 'ausencias': [], 'plantillasCargos': []}
    }
    if os.path.exists(ruta):
        return jsonify(cargar_json(ruta))
    return jsonify(defaults_map.get(modulo, {}))

@app.route('/api/usuario/<uid>/datos/<modulo>', methods=['POST'])
def usuario_datos_post(uid, modulo):
    """Guarda datos privados de un módulo para un usuario."""
    if modulo not in MODULOS_PRIVADOS:
        return jsonify({'error': 'Módulo no privado'}), 400
    datos = request.get_json(force=True)
    if datos is None:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = f_dato_usuario(uid, modulo)
    ok = guardar_json(ruta, datos)
    if ok:
        hacer_backup(f'{uid}_{modulo}', datos)
    return jsonify({'success': ok})

# ── Usuario activo (sesión del servidor) ──────────────────

F_USUARIO_ACTIVO = os.path.join(CONFIG_DIR, f'_usuario_activo_{_HOSTNAME}.json')

@app.route('/api/usuario-activo', methods=['GET'])
def usuario_activo_get():
    if os.path.exists(F_USUARIO_ACTIVO):
        return jsonify(cargar_json(F_USUARIO_ACTIVO))
    return jsonify({'id': None, 'nombre': None})

@app.route('/api/usuario-activo', methods=['POST'])
def usuario_activo_post():
    datos = request.get_json(force=True) or {}
    uid   = datos.get('id')
    nombre = datos.get('nombre', '')
    guardar_json(F_USUARIO_ACTIVO, {'id': uid, 'nombre': nombre})
    return jsonify({'success': True})

# ── Estado del asistente IA (per-PC) ──────────────────────

F_ASISTENTE_ESTADO = os.path.join(CONFIG_DIR, f'_asistente_{_HOSTNAME}.json')

@app.route('/api/asistente-estado', methods=['GET'])
def asistente_estado_get():
    if os.path.exists(F_ASISTENTE_ESTADO):
        return jsonify(cargar_json(F_ASISTENTE_ESTADO))
    return jsonify({})

@app.route('/api/asistente-estado', methods=['POST'])
def asistente_estado_post():
    datos = request.get_json(force=True) or {}
    guardar_json(F_ASISTENTE_ESTADO, datos)
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# FIN MULTIUSUARIO
# ══════════════════════════════════════════════

@app.route('/api/config/<usuario>', methods=['GET', 'POST'])
def config_usuario(usuario):
    usuario_limpio = ''.join(c for c in usuario.upper() if c.isalnum() or c in '-_')
    ruta = os.path.join(CONFIG_DIR, f'{usuario_limpio}.json')
    if request.method == 'POST':
        cfg = request.get_json(force=True) or {}
        guardar_json(ruta, cfg)
        return jsonify({'success': True})
    if os.path.exists(ruta):
        return jsonify({'success': True, 'config': cargar_json(ruta)})
    return jsonify({'success': True, 'config': None})

# ══════════════════════════════════════════════
# GRUPOS / EQUIPOS DE TRABAJO
# ══════════════════════════════════════════════

@app.route('/api/grupos', methods=['GET'])
def grupos_get():
    """Lista todos los grupos (público — el portal lo necesita para renderizar tabs)."""
    return jsonify({'grupos': cargar_grupos()})

@app.route('/api/grupos', methods=['POST'])
def grupo_crear():
    """Crea un nuevo grupo. Requiere sesión superadmin."""
    token = request.headers.get('X-Superadmin-Token') or ''
    if not _es_superadmin_activo(token):
        return jsonify({'success': False, 'error': 'Requiere sesión superadmin'}), 403
    datos  = request.get_json(force=True) or {}
    nombre = (datos.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
    gid   = _id_usuario(nombre)   # reutilizamos el mismo slugificador
    with editar_json(F_GRUPOS) as data:
        lista = data.get('grupos', [])
        if any(g['id'] == gid for g in lista):
            return jsonify({'success': False, 'error': 'Ya existe un grupo con ese nombre'}), 409
        nuevo = {
            'id':      gid,
            'nombre':  nombre,
            'icono':   datos.get('icono',   '👥'),
            'color':   datos.get('color',   '#6366f1'),
            'modulos': datos.get('modulos', []),
            'miembros': datos.get('miembros', [])
        }
        lista.append(nuevo)
        data['grupos'] = lista
    os.makedirs(datos_grupo_dir(gid), exist_ok=True)
    log(f"Grupo creado: {gid} ({nombre})")
    return jsonify({'success': True, 'grupo': nuevo})

@app.route('/api/grupos/<gid>', methods=['PUT'])
def grupo_editar(gid):
    """Edita un grupo existente. Requiere sesión superadmin."""
    token = request.headers.get('X-Superadmin-Token') or ''
    if not _es_superadmin_activo(token):
        return jsonify({'success': False, 'error': 'Requiere sesión superadmin'}), 403
    datos = request.get_json(force=True) or {}
    with editar_json(F_GRUPOS) as data:
        lista = data.get('grupos', [])
        for g in lista:
            if g['id'] == gid:
                if 'nombre'   in datos: g['nombre']   = datos['nombre'].strip()
                if 'icono'    in datos: g['icono']     = datos['icono']
                if 'color'    in datos: g['color']     = datos['color']
                if 'modulos'  in datos: g['modulos']   = datos['modulos']
                if 'miembros' in datos: g['miembros']  = datos['miembros']
                data['grupos'] = lista
                log(f"Grupo editado: {gid}")
                return jsonify({'success': True, 'grupo': g})
    return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404

@app.route('/api/grupos/<gid>', methods=['DELETE'])
def grupo_eliminar(gid):
    """Elimina un grupo (no borra sus datos). Requiere sesión superadmin."""
    token = request.headers.get('X-Superadmin-Token') or ''
    if not _es_superadmin_activo(token):
        return jsonify({'success': False, 'error': 'Requiere sesión superadmin'}), 403
    with editar_json(F_GRUPOS) as data:
        lista = data.get('grupos', [])
        nueva = [g for g in lista if g['id'] != gid]
        if len(nueva) == len(lista):
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
        data['grupos'] = nueva
    log(f"Grupo eliminado: {gid}")
    return jsonify({'success': True})

# ══════════════════════════════════════════════

# Turno simplificado (uso individual — siempre concede)
@app.route('/api/turno/solicitar', methods=['POST'])
def turno_solicitar():
    datos = request.get_json(force=True) or {}
    minutos = datos.get('duracionMinutos', 60)
    hasta = (datetime.now() + timedelta(minutes=minutos)).isoformat()
    return jsonify({'success': True, 'turnoHasta': hasta})

@app.route('/api/turno/liberar', methods=['POST'])
def turno_liberar():
    return jsonify({'success': True})

@app.route('/api/turno/renovar', methods=['POST'])
def turno_renovar():
    datos = request.get_json(force=True) or {}
    minutos = datos.get('duracionMinutos', 60)
    hasta = (datetime.now() + timedelta(minutes=minutos)).isoformat()
    return jsonify({'success': True, 'turnoHasta': hasta})

@app.route('/api/turno/estado', methods=['GET'])
def turno_estado():
    return jsonify({'turnoActivo': False})

# ══════════════════════════════════════════════
# MÓDULO 2 — CALCULADORA DE VENCIMIENTOS
# ══════════════════════════════════════════════
def _resolver_fichero_modulo(modulo, fichero_compartido, uid=None):
    """Devuelve la ruta al fichero del módulo: equipo > usuario_privado > compartido."""
    # Contexto de equipo — prioridad máxima (tabs de grupo)
    try:
        equipo = request.args.get('equipo') or None
    except RuntimeError:
        equipo = None
    if equipo:
        g = next((g for g in cargar_grupos() if g['id'] == equipo), None)
        if g and modulo in g.get('modulos', []):
            return f_dato_grupo(equipo, modulo)
    # Contexto de usuario (privado)
    if uid is None:
        if os.path.exists(F_USUARIO_ACTIVO):
            activo = cargar_json(F_USUARIO_ACTIVO)
            uid = activo.get('id')
    if uid:
        # Buscar si ese usuario tiene este módulo como privado
        usuarios = cargar_usuarios()
        u = next((x for x in usuarios if x['id'] == uid), None)
        if u and modulo in u.get('modulos_privados', []):
            return f_dato_usuario(uid, modulo)
    return fichero_compartido

@app.route('/api/vencimientos', methods=['GET'])
def vencimientos_get():
    uid = request.args.get('uid') or None
    # _resolver_fichero_modulo comprueba equipo (query), modulos_privados y compartido
    ruta = _resolver_fichero_modulo('vencimientos', F_VENCIMIENTOS, uid)
    datos = cargar_json(ruta)
    # Si el fichero privado del usuario está vacío, usar el compartido como base
    if not datos and ruta != F_VENCIMIENTOS:
        datos = cargar_json(F_VENCIMIENTOS)
    return jsonify(datos)

@app.route('/api/vencimientos', methods=['POST'])
def vencimientos_post():
    uid   = request.args.get('uid') or None
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('vencimientos', F_VENCIMIENTOS, uid)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('vencimientos', actual)
    return jsonify({'success': True})

# Compatibilidad con endpoints que usa el HTML actual (/save_data, /load_data)
@app.route('/save_data', methods=['POST'])
def vencimientos_save_compat():
    uid   = request.args.get('uid') or None
    datos = request.get_json(force=True) or {}
    ruta = _resolver_fichero_modulo('vencimientos', F_VENCIMIENTOS, uid)
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('vencimientos', actual)
    return jsonify({'success': True})

@app.route('/load_data', methods=['GET'])
def vencimientos_load_compat():
    uid = request.args.get('uid') or None
    ruta = _resolver_fichero_modulo('vencimientos', F_VENCIMIENTOS, uid)
    datos = cargar_json(ruta)
    if not datos and ruta != F_VENCIMIENTOS:
        datos = cargar_json(F_VENCIMIENTOS)
    return jsonify(datos)

# ══════════════════════════════════════════════
# MÓDULO 3 — GESTIÓN DE VACACIONES
# ══════════════════════════════════════════════
@app.route('/api/vacaciones', methods=['GET'])
def vacaciones_get():
    uid = request.args.get('uid') or None
    # _resolver_fichero_modulo comprueba equipo (query), modulos_privados y compartido
    ruta = _resolver_fichero_modulo('vacaciones', F_VACACIONES, uid)
    datos = cargar_json(ruta)
    # Si el fichero privado del usuario está vacío, usar el compartido como base
    if not datos and ruta != F_VACACIONES:
        datos = cargar_json(F_VACACIONES)
    return jsonify(datos)

@app.route('/api/vacaciones', methods=['POST'])
def vacaciones_post():
    uid   = request.args.get('uid') or None
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('vacaciones', F_VACACIONES, uid)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('vacaciones', actual)
    return jsonify({'success': True})

# Compatibilidad con el HTML existente de Vacaciones
@app.route('/api/cargar-datos', methods=['GET'])
def vacaciones_cargar_compat():
    equipo = request.args.get('equipo') or None
    if equipo:
        g = next((g for g in cargar_grupos() if g['id'] == equipo), None)
        ruta = f_dato_grupo(equipo, 'vacaciones') if g else F_VACACIONES
        return jsonify(cargar_json(ruta))
    return jsonify(cargar_json(F_VACACIONES))

@app.route('/api/guardar-datos', methods=['POST'])
def vacaciones_guardar_compat():
    equipo = request.args.get('equipo') or None
    datos  = request.get_json(force=True) or {}
    if equipo:
        g = next((g for g in cargar_grupos() if g['id'] == equipo), None)
        ruta = f_dato_grupo(equipo, 'vacaciones') if g else F_VACACIONES
    else:
        ruta = F_VACACIONES
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('vacaciones', actual)
    return jsonify({'status': 'ok', 'message': 'Datos guardados'})

# ══════════════════════════════════════════════
# MÓDULO — CONTROL DE PRESOS
# ══════════════════════════════════════════════
@app.route('/api/presos', methods=['GET'])
def presos_get():
    uid = request.args.get('uid') or None
    ruta = _resolver_fichero_modulo('presos', F_PRESOS, uid)
    datos = cargar_json(ruta)
    # Si el fichero privado del usuario está vacío, usar el compartido como base
    if not datos and ruta != F_PRESOS:
        datos = cargar_json(F_PRESOS)
    return jsonify(datos)

@app.route('/api/presos', methods=['POST'])
def presos_post():
    uid = request.args.get('uid') or None
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('presos', F_PRESOS, uid)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('presos', actual)
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# MÓDULO — SOLICITUDES DE ARCHIVO
# ══════════════════════════════════════════════
@app.route('/api/archivo', methods=['GET'])
def archivo_get():
    uid = request.args.get('uid') or None
    ruta = _resolver_fichero_modulo('archivo', F_ARCHIVO, uid)
    datos = cargar_json(ruta)
    if not datos and ruta != F_ARCHIVO:
        datos = cargar_json(F_ARCHIVO)
    return jsonify(datos)

@app.route('/api/archivo', methods=['POST'])
def archivo_post():
    uid = request.args.get('uid') or None
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('archivo', F_ARCHIVO, uid)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('archivo', actual)
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# MÓDULO — NOTIFICAJUD (GESTIÓN DE NOTIFICACIONES)
# ══════════════════════════════════════════════
@app.route('/api/notificajud', methods=['GET'])
def notificajud_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('notificajud', F_NOTIFICAJUD)))

@app.route('/api/notificajud', methods=['POST'])
def notificajud_post():
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('notificajud', F_NOTIFICAJUD)
    # MERGE: preservar datos existentes no incluidos en el payload
    # (ej: registroDiligencias no se envía desde njGuardarDatos)
    with editar_json(ruta) as existente:
        existente.update(datos)
        hacer_backup('notificajud', existente)
    return jsonify({'success': True})

# ── Registro de diligencias — SIEMPRE compartido ───────────────────────
_TIPOS_ACTO_DEFAULT = ['Notificación', 'Embargo', 'Desahucio', 'Testimonio',
                       'Requerimiento', 'Otro']

@app.route('/api/notificajud/registro', methods=['GET'])
def notificajud_registro_get():
    """Registro de diligencias — SIEMPRE fichero compartido (visible para todos)."""
    datos = cargar_json(F_NOTIFICAJUD) or {}
    return jsonify({
        'registroDiligencias': datos.get('registroDiligencias', []),
        'distritos':           datos.get('distritos', []),
        'tiposActo':           datos.get('tiposActo', _TIPOS_ACTO_DEFAULT[:]),
        'prefijoSCACE':        datos.get('prefijoSCACE', 'SCACE')
    })

@app.route('/api/notificajud/registro', methods=['POST'])
def notificajud_registro_post():
    """Guarda registro de diligencias en el fichero COMPARTIDO."""
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error': 'Sin datos'}), 400
    with editar_json(F_NOTIFICAJUD) as datos:
        datos['registroDiligencias'] = payload.get('registroDiligencias', [])
        datos['distritos']           = payload.get('distritos', [])
        datos['tiposActo']           = payload.get('tiposActo', [])
        datos['prefijoSCACE']        = payload.get('prefijoSCACE', 'SCACE')
        hacer_backup('notificajud', datos)
    return jsonify({'success': True})

@app.route('/api/guardias', methods=['GET'])
def guardias_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('guardias', F_GUARDIAS)))

@app.route('/api/guardias', methods=['POST'])
def guardias_post():
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('guardias', F_GUARDIAS)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('guardias', actual)
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# MÓDULO — AUSENCIAS DE PLAZAS
# ══════════════════════════════════════════════
@app.route('/api/ausencias', methods=['GET'])
def ausencias_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)))

@app.route('/api/ausencias', methods=['POST'])
def ausencias_post():
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('ausencias', F_AUSENCIAS)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('ausencias', actual)
    return jsonify({'success': True})

@app.route('/api/ausencias/activas', methods=['GET'])
def ausencias_activas():
    """Endpoint ligero para el banner del portal: solo ausencias activas hoy."""
    ruta = _resolver_fichero_modulo('ausencias', F_AUSENCIAS)
    datos = cargar_json(ruta) or {}
    hoy = datetime.now().strftime('%Y-%m-%d')
    plazas_out = []
    for plaza in sorted(datos.get('plazas', []), key=lambda p: p.get('orden', 0)):
        ausencias_plaza = []
        for aus in datos.get('ausencias', []):
            if (aus.get('plazaId') == plaza['id']
                    and aus.get('fechaInicio', '') <= hoy
                    and aus.get('fechaFin', '') >= hoy):
                cargo = next((c for c in plaza.get('cargos', [])
                              if c['id'] == aus.get('cargoId')), {})
                ausencias_plaza.append({
                    'cargo': cargo.get('nombre', ''),
                    'color': cargo.get('color', '#ef4444'),
                    'titular': aus.get('titular', ''),
                    'fechaFin': aus.get('fechaFin', ''),
                    'notas': aus.get('notas', ''),
                    'sustituto': aus.get('sustituto', '')
                })
        nombre = plaza.get('nombre', '')
        plazas_out.append({
            'id': plaza['id'],
            'nombre': nombre,
            'nombreCorto': nombre.split(' - ')[0] if ' - ' in nombre else nombre,
            'ausencias': ausencias_plaza
        })
    return jsonify({'plazas': plazas_out})

# ══════════════════════════════════════════════
# MÓDULO 4 — CLIPBOX (MODELOS DE RESOLUCIONES)
# ══════════════════════════════════════════════
@app.route('/api/clipbox', methods=['GET'])
def clipbox_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('clipbox', F_CLIPBOX)))

@app.route('/api/clipbox', methods=['POST'])
def clipbox_post():
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('clipbox', F_CLIPBOX)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('clipbox', actual)
    return jsonify({'success': True})

@app.route('/api/clipbox/clips', methods=['GET'])
def clipbox_clips_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('clipbox', F_CLIPBOX)).get('clips', []))

@app.route('/api/clipbox/clips', methods=['POST'])
def clipbox_clips_post():
    clips = request.get_json(force=True)
    if clips is None:
        return jsonify({'error': 'Sin datos'}), 400
    ruta = _resolver_fichero_modulo('clipbox', F_CLIPBOX)
    with editar_json(ruta) as datos:
        datos['clips'] = clips
        hacer_backup('clipbox', datos)
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# MÓDULO 5 — ALARDES JUDICIALES
# (no persiste datos propios — solo carga Excel/CSV)
# ══════════════════════════════════════════════
# No necesita endpoints de datos propios

# ══════════════════════════════════════════════
# MÓDULO 6 — PERITOS JUDICIALES
# ══════════════════════════════════════════════

# Helper para obtener o crear especialidad por nombre
def _obtener_o_crear_especialidad(d, nombre_esp):
    """Devuelve el id de la especialidad, creándola si no existe."""
    especialidades = d.setdefault('especialidades', [])
    nombre_norm = nombre_esp.strip()
    for e in especialidades:
        if e.get('nombre', '').strip().lower() == nombre_norm.lower():
            return e['id'], False
    nuevo_id = max((e.get('id', 0) for e in especialidades), default=0) + 1
    nueva = {'id': nuevo_id, 'nombre': nombre_norm, 'descripcion': ''}
    especialidades.append(nueva)
    return nuevo_id, True

# ── Especialidades ────────────────────────────
@app.route('/api/peritos/especialidades', methods=['GET'])
@app.route('/api/especialidades', methods=['GET'])
def peritos_especialidades_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('peritos', F_PERITOS)).get('especialidades', []))

@app.route('/api/peritos/especialidades', methods=['POST'])
@app.route('/api/especialidades', methods=['POST'])
def peritos_especialidades_post():
    datos = request.get_json(force=True) or []
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        d['especialidades'] = datos
        hacer_backup('peritos', d)
    return jsonify({'success': True})

@app.route('/api/especialidades/delete-all', methods=['DELETE'])
def especialidades_delete_all():
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        d['especialidades'] = []
        hacer_backup('peritos', d)
    return jsonify({'success': True, 'message': 'Todas las especialidades eliminadas'})

@app.route('/api/peritos/especialidades/<int:eid>', methods=['DELETE'])
@app.route('/api/especialidades/<int:eid>', methods=['DELETE'])
def especialidad_delete(eid):
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        d['especialidades'] = [e for e in d.get('especialidades', []) if e.get('id') != eid]
        hacer_backup('peritos', d)
    return jsonify({'success': True})

# ── Peritos ───────────────────────────────────
@app.route('/api/peritos', methods=['GET'])
def peritos_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('peritos', F_PERITOS)).get('peritos', []))

@app.route('/api/peritos', methods=['POST'])
def peritos_post():
    nuevo = request.get_json(force=True) or {}
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        peritos = d.get('peritos', [])
        nuevo['id'] = max((p.get('id', 0) for p in peritos), default=0) + 1
        nuevo['createdAt'] = datetime.now().isoformat()
        peritos.append(nuevo)
        d['peritos'] = peritos
        hacer_backup('peritos', d)
    return jsonify({'success': True, 'perito': nuevo})

@app.route('/api/peritos/delete-all', methods=['DELETE'])
def peritos_delete_all():
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        d['peritos'] = []
        hacer_backup('peritos', d)
    return jsonify({'success': True, 'message': 'Todos los peritos eliminados'})

@app.route('/api/peritos/bulk', methods=['POST'])
def peritos_bulk():
    body = request.get_json(force=True) or {}
    # El HTML envía { peritos: [...] }; también admitimos lista directa
    if isinstance(body, list):
        lista = body
    else:
        lista = body.get('peritos', [])

    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    especialidades_nuevas = []
    with editar_json(ruta) as d:
        peritos_existentes = d.get('peritos', [])
        ultimo_id = max((p.get('id', 0) for p in peritos_existentes), default=0)

        for p in lista:
            ultimo_id += 1
            p['id'] = ultimo_id
            p['createdAt'] = datetime.now().isoformat()
            # Si el perito trae campo 'especialidad' (texto), resolver/crear la especialidad
            nombre_esp = p.pop('especialidad', None)
            if nombre_esp:
                esp_id, es_nueva = _obtener_o_crear_especialidad(d, nombre_esp)
                p['especialidadId'] = esp_id
                if es_nueva:
                    # Buscar el objeto recién creado para incluirlo en la respuesta
                    for e in d['especialidades']:
                        if e['id'] == esp_id:
                            especialidades_nuevas.append(e)
                            break

        peritos_existentes.extend(lista)
        d['peritos'] = peritos_existentes
        hacer_backup('peritos', d)
    return jsonify({
        'success': True,
        'importados': len(lista),
        'especialidadesCreadas': len(especialidades_nuevas),
        'especialidades': especialidades_nuevas
    })

@app.route('/api/peritos/<int:pid>', methods=['PUT'])
def peritos_put(pid):
    actualizado = request.get_json(force=True) or {}
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        d['peritos'] = [actualizado if p.get('id') == pid else p for p in d.get('peritos', [])]
        hacer_backup('peritos', d)
    return jsonify({'success': True})

@app.route('/api/peritos/<int:pid>', methods=['DELETE'])
def peritos_delete(pid):
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        d['peritos'] = [p for p in d.get('peritos', []) if p.get('id') != pid]
        hacer_backup('peritos', d)
    return jsonify({'success': True})

# ── Selecciones ───────────────────────────────
@app.route('/api/peritos/selecciones', methods=['GET'])
@app.route('/api/selecciones', methods=['GET'])
def selecciones_get():
    return jsonify(cargar_json(_resolver_fichero_modulo('peritos', F_PERITOS)).get('selecciones', []))

@app.route('/api/peritos/selecciones/<int:sid>', methods=['PUT'])
@app.route('/api/selecciones/<int:sid>', methods=['PUT'])
def seleccion_put(sid):
    cambios = request.get_json(force=True) or {}
    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        selecciones = d.get('selecciones', [])
        idx = next((i for i, s in enumerate(selecciones) if s.get('id') == sid), None)
        if idx is None:
            return jsonify({'error': 'Selección no encontrada'}), 404
        selecciones[idx].update(cambios)
        d['selecciones'] = selecciones
        hacer_backup('peritos', d)
    return jsonify({'success': True, 'seleccion': selecciones[idx]})

@app.route('/api/peritos/selecciones/aleatoria', methods=['POST'])
@app.route('/api/selecciones/aleatoria', methods=['POST'])
def seleccion_aleatoria():
    import random
    body = request.get_json(force=True) or {}
    especialidad_id = body.get('especialidadId')
    expediente = body.get('expediente', '')
    motivo = body.get('motivo', '')

    ruta = _resolver_fichero_modulo('peritos', F_PERITOS)
    with editar_json(ruta) as d:
        peritos = [p for p in d.get('peritos', [])
                   if p.get('disponible', True) and
                   (especialidad_id is None or p.get('especialidadId') == especialidad_id)]

        if not peritos:
            return jsonify({'error': 'No hay peritos disponibles para esa especialidad'}), 404

        seleccionado = random.choice(peritos)
        registro = {
            'id': max((s.get('id', 0) for s in d.get('selecciones', [])), default=0) + 1,
            'peritoId': seleccionado.get('id'),
            'peritoNombre': seleccionado.get('nombre'),
            'especialidadId': especialidad_id,
            'expediente': expediente,
            'motivo': motivo,
            'fechaSeleccion': datetime.now().isoformat()
        }
        d.setdefault('selecciones', []).append(registro)
        hacer_backup('peritos', d)
    return jsonify({'success': True, 'perito': seleccionado, 'seleccion': registro})

# ══════════════════════════════════════════════
# MÓDULO 7 — BOLETÍN TRIMESTRAL
# ══════════════════════════════════════════════
@app.route('/api/boletin', methods=['GET'])
def boletin_get():
    return jsonify(cargar_json(F_BOLETIN))

@app.route('/api/boletin', methods=['POST'])
def boletin_post():
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'error': 'Sin datos'}), 400
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(F_BOLETIN) as actual:
        actual.update(datos)
        hacer_backup('boletin', actual)
    return jsonify({'success': True})

@app.route('/api/boletin/datos', methods=['GET'])
def boletin_datos_get():
    """Devuelve datos de un trimestre específico (por plaza/materia/ano/trimestre)."""
    plaza   = request.args.get('plaza', '')
    materia = request.args.get('materia', '')
    ano     = request.args.get('ano', '')
    trim    = request.args.get('trimestre', '')
    uid     = request.args.get('uid') or None
    fichero = _resolver_fichero_modulo('boletin', F_BOLETIN, uid)
    d = cargar_json(fichero)
    clave = f"{plaza}_{materia}_{ano}_{trim}"
    datos = d.get('datos', {}).get(clave, {})
    return jsonify({'datos': datos})

@app.route('/api/boletin/datos', methods=['POST'])
def boletin_datos_post():
    """Guarda datos de un trimestre específico."""
    body    = request.get_json(force=True) or {}
    plaza   = body.get('plaza', '')
    materia = body.get('materia', '')
    ano     = body.get('ano', '')
    trim    = body.get('trimestre', '')
    uid     = body.get('uid') or None
    datos_trim = body.get('datos', {})
    fichero = _resolver_fichero_modulo('boletin', F_BOLETIN, uid)
    clave = f"{plaza}_{materia}_{ano}_{trim}"
    with editar_json(fichero) as d:
        d.setdefault('datos', {})[clave] = datos_trim
        hacer_backup('boletin', d)
    return jsonify({'success': True})

@app.route('/api/boletin/historico', methods=['GET'])
def boletin_historico():
    """Lista trimestres con datos para una plaza y materia dadas."""
    plaza   = request.args.get('plaza', '')
    materia = request.args.get('materia', '')
    uid     = request.args.get('uid') or None
    fichero = _resolver_fichero_modulo('boletin', F_BOLETIN, uid)
    d = cargar_json(fichero)
    prefijo = f"{plaza}_{materia}_"
    trimestres = []
    for clave in d.get('datos', {}).keys():
        if clave.startswith(prefijo):
            partes = clave[len(prefijo):].split('_')
            if len(partes) == 2:
                try:
                    trimestres.append({'año': int(partes[0]), 'trimestre': int(partes[1])})
                except ValueError:
                    pass
    return jsonify({'trimestres': trimestres})

# ══════════════════════════════════════════════
# MÓDULO 8 — CONTROL DE INSTRUCCIÓN PENAL
# ══════════════════════════════════════════════
@app.route('/api/instruccion-penal', methods=['GET'])
def instruccion_get():
    uid = request.args.get('uid') or None
    return jsonify(cargar_json(_resolver_fichero_modulo('instruccion_penal', F_INSTRUCCION, uid)))

@app.route('/api/instruccion-penal', methods=['POST'])
def instruccion_post():
    uid = request.args.get('uid') or None
    datos = request.get_json(force=True) or {}
    ruta = _resolver_fichero_modulo('instruccion_penal', F_INSTRUCCION, uid)
    # MERGE: preservar datos existentes no incluidos en el payload
    with editar_json(ruta) as actual:
        actual.update(datos)
        hacer_backup('instruccion_penal', actual)
    return jsonify({'success': True})

@app.route('/api/instruccion-penal/listas', methods=['GET'])
def instruccion_listas_get():
    """Devuelve las listas personalizadas de tipos y plazas."""
    F_LISTAS = os.path.join(CONFIG_DIR, 'instruccion_listas.json')
    if os.path.exists(F_LISTAS):
        return jsonify(cargar_json(F_LISTAS))
    return jsonify({
        'tipos':  ['D.P.', 'P.A.', 'J.R.', 'P.O.', 'Sumario', 'Otro'],
        'plazas': ['Plaza 1', 'Plaza 2', 'Plaza 3', 'Decanato', 'Guardia']
    })

@app.route('/api/instruccion-penal/listas', methods=['POST'])
def instruccion_listas_post():
    """Guarda las listas personalizadas de tipos y plazas."""
    F_LISTAS = os.path.join(CONFIG_DIR, 'instruccion_listas.json')
    datos = request.get_json(force=True) or {}
    guardar_json(F_LISTAS, datos)
    return jsonify({'success': True})

@app.route('/api/instruccion-penal/urgentes', methods=['GET'])
def instruccion_urgentes():
    """Devuelve procedimientos próximos a vencer para el widget del portal."""
    from datetime import date
    datos = cargar_json(F_INSTRUCCION)
    hoy = date.today()
    resultado = []
    for p in datos.get('procedimientos', []):
        if p.get('cerrado'): continue
        try:
            fv = date.fromisoformat(p['fechaVencimiento'])
            dias = (fv - hoy).days
            p['diasRestantes'] = dias
            resultado.append(p)
        except (KeyError, ValueError, TypeError):
            pass
    resultado.sort(key=lambda x: x['fechaVencimiento'])
    return jsonify({'procedimientos': resultado[:10]})

# ══════════════════════════════════════════════
# DASHBOARD DE SALUD
# ══════════════════════════════════════════════
@app.route('/api/salud', methods=['GET'])
def api_salud():
    _salud_resetear_dia()
    # Determinar estado general
    errores = _salud_contadores['lecturas_error']
    lecturas = _salud_contadores['lecturas_ok']
    cache_hits = _salud_contadores['cache_hits']
    if errores == 0:
        estado = 'ok'
    elif cache_hits > 0 or errores > lecturas * 0.1:
        estado = 'degradado'
    else:
        estado = 'ok'
    # Último backup
    ultimo_backup = None
    try:
        cfg_b = cargar_json(F_BACKUP_CONFIG)
        ultimo_backup = cfg_b.get('ultimo_auto')
    except Exception:
        pass
    return jsonify({
        'estado': estado,
        'cache_activos': len(_cache),
        'errores_hoy': errores,
        'lecturas_ok_hoy': lecturas,
        'cache_hits_hoy': cache_hits,
        'backups_ok_hoy': _salud_contadores['backups_ok'],
        'backups_error_hoy': _salud_contadores['backups_error'],
        'ultimo_backup': ultimo_backup,
        'ultima_lectura_ok': _salud_ultima_lectura_ok,
        'eventos': list(_salud_eventos)
    })

# ══════════════════════════════════════════════
# CONFIGURACIÓN DE BACKUP
# ══════════════════════════════════════════════
@app.route('/api/config/backup', methods=['GET'])
def backup_config_get():
    cfg = cargar_backup_config()
    # Calcular próximo backup
    proximo = None
    horas = cfg.get('frecuencia_horas', 0)
    if horas and horas > 0 and cfg.get('ultimo_auto'):
        try:
            ultimo = datetime.fromisoformat(cfg['ultimo_auto'])
            proximo = (ultimo + timedelta(hours=horas)).isoformat()
        except (KeyError, ValueError, TypeError):
            pass
    return jsonify({**cfg, 'proximo_auto': proximo})

@app.route('/api/config/backup', methods=['POST'])
def backup_config_post():
    global _backup_scheduler_timer
    datos = request.get_json(force=True) or {}
    with editar_json(F_BACKUP_CONFIG) as cfg:
        # Asegurar claves por defecto
        for k, v in DEFAULT_BACKUP_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        if 'frecuencia_horas' in datos:
            cfg['frecuencia_horas'] = int(datos['frecuencia_horas'])
        if 'rutas_externas' in datos:
            cfg['rutas_externas'] = [r.strip() for r in datos['rutas_externas'] if r.strip()]
        if 'modulos' in datos:
            cfg['modulos'] = datos['modulos']
        if 'max_backups_locales' in datos:
            cfg['max_backups_locales'] = int(datos['max_backups_locales'])
        if 'intervalo_backup_min' in datos:
            cfg['intervalo_backup_min'] = max(1, int(datos['intervalo_backup_min']))
        if 'hora_inicio' in datos:
            cfg['hora_inicio'] = datos['hora_inicio']
        if 'hora_fin' in datos:
            cfg['hora_fin'] = datos['hora_fin']
    # Reprogramar el scheduler con la nueva config
    _arrancar_scheduler_backup()
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# HISTORIAL DE BACKUPS
# ══════════════════════════════════════════════
@app.route('/api/backups/lista', methods=['GET'])
def backup_historial():
    """Lista todos los backups ZIP disponibles."""
    backups = []
    try:
        for nombre in sorted(os.listdir(BACKUP_DIR), reverse=True):
            ruta = os.path.join(BACKUP_DIR, nombre)
            if nombre.endswith('.zip') and os.path.isfile(ruta):
                stat = os.stat(ruta)
                backups.append({
                    'nombre': nombre,
                    'tamanyo': stat.st_size,
                    'fecha': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'tipo': 'manual' if nombre.startswith('manual_') else 'auto'
                })
    except Exception as e:
        log(f"Error listando historial: {e}", 'WARNING')
    return jsonify({'backups': backups})

@app.route('/api/backups/descargar/<nombre>', methods=['GET'])
def descargar_zip_backup(nombre):
    """Descarga un ZIP del historial de backups."""
    # Seguridad: solo nombre de fichero, sin rutas
    nombre_seguro = os.path.basename(nombre)
    if not nombre_seguro.endswith('.zip'):
        return jsonify({'error': 'Tipo de fichero no válido'}), 400
    ruta = os.path.join(BACKUP_DIR, nombre_seguro)
    if not os.path.isfile(ruta):
        return jsonify({'error': 'Backup no encontrado'}), 404
    return send_from_directory(BACKUP_DIR, nombre_seguro, as_attachment=True)

@app.route('/api/backups/eliminar/<nombre>', methods=['DELETE'])
def eliminar_backup(nombre):
    """Elimina un ZIP del historial."""
    nombre_seguro = os.path.basename(nombre)
    if not nombre_seguro.endswith('.zip'):
        return jsonify({'error': 'Tipo de fichero no válido'}), 400
    ruta = os.path.join(BACKUP_DIR, nombre_seguro)
    if not os.path.isfile(ruta):
        return jsonify({'error': 'No encontrado'}), 404
    os.remove(ruta)
    log(f"Backup eliminado: {nombre_seguro}")
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# BACKUP MANUAL (accesible desde el portal)
# ══════════════════════════════════════════════
@app.route('/api/backup/completo', methods=['POST'])
def backup_completo():
    """Genera un backup ZIP manual de los módulos configurados."""
    zip_nombre = hacer_backup_completo_auto('manual')
    if zip_nombre:
        return jsonify({'success': True, 'archivo': zip_nombre})
    return jsonify({'success': False, 'error': 'Error al generar backup'}), 500

@app.route('/api/backup/usuarios', methods=['POST'])
def backup_usuarios():
    """Genera un ZIP con los datos privados de todos los usuarios."""
    import io
    from datetime import datetime
    try:
        if not os.path.isdir(DATOS_USR_DIR):
            return jsonify({'success': False, 'error': 'No hay datos privados de usuarios'}), 404

        entradas = []
        for uid in sorted(os.listdir(DATOS_USR_DIR)):
            uid_dir = os.path.join(DATOS_USR_DIR, uid)
            if not os.path.isdir(uid_dir):
                continue
            for fichero in sorted(os.listdir(uid_dir)):
                if fichero.endswith('.json'):
                    entradas.append((os.path.join(uid_dir, fichero), f'usuarios/{uid}/{fichero}'))

        if not entradas:
            return jsonify({'success': False, 'error': 'No hay datos privados de usuarios'}), 404

        usuarios = cargar_usuarios()
        uid_nombre = {u['id']: u.get('nombre', u['id']) for u in usuarios}
        uids_en_zip = sorted({e[1].split('/')[1] for e in entradas})

        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        nombre_zip = f'backup_usuarios_{ts}.zip'
        meta = {
            'generado': datetime.now().isoformat(),
            'tipo': 'usuarios',
            'usuarios': [{'id': u_id, 'nombre': uid_nombre.get(u_id, u_id)} for u_id in uids_en_zip]
        }

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('_tipo.txt', 'usuarios')
            zf.writestr('_meta.json', json.dumps(meta, ensure_ascii=False, indent=2))
            for ruta_abs, ruta_zip in entradas:
                zf.write(ruta_abs, ruta_zip)

        buffer.seek(0)
        log(f"Backup usuarios generado: {nombre_zip}")
        return send_file(
            buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=nombre_zip
        )
    except Exception as ex:
        log(f"Error backup usuarios: {ex}", 'ERROR')
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.route('/api/backup/equipos', methods=['POST'])
def backup_equipos():
    """Genera un ZIP con los datos compartidos de todos los equipos."""
    import io
    from datetime import datetime
    try:
        if not os.path.isdir(GRUPOS_DIR):
            return jsonify({'success': False, 'error': 'No hay datos de equipos'}), 404

        entradas = []
        for gid in sorted(os.listdir(GRUPOS_DIR)):
            gid_dir = os.path.join(GRUPOS_DIR, gid)
            if not os.path.isdir(gid_dir):
                continue
            for fichero in sorted(os.listdir(gid_dir)):
                if fichero.endswith('.json'):
                    entradas.append((os.path.join(gid_dir, fichero), f'equipos/{gid}/{fichero}'))

        if not entradas:
            return jsonify({'success': False, 'error': 'No hay datos de equipos'}), 404

        grupos = cargar_grupos()
        gid_nombre = {g['id']: g.get('nombre', g['id']) for g in grupos}
        gids_en_zip = sorted({e[1].split('/')[1] for e in entradas})

        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        nombre_zip = f'backup_equipos_{ts}.zip'
        meta = {
            'generado': datetime.now().isoformat(),
            'tipo': 'equipos',
            'equipos': [{'id': g_id, 'nombre': gid_nombre.get(g_id, g_id)} for g_id in gids_en_zip]
        }

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('_tipo.txt', 'equipos')
            zf.writestr('_meta.json', json.dumps(meta, ensure_ascii=False, indent=2))
            for ruta_abs, ruta_zip in entradas:
                zf.write(ruta_abs, ruta_zip)

        buffer.seek(0)
        log(f"Backup equipos generado: {nombre_zip}")
        return send_file(
            buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=nombre_zip
        )
    except Exception as ex:
        log(f"Error backup equipos: {ex}", 'ERROR')
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.route('/api/restaurar/<modulo>', methods=['POST'])
def restaurar_modulo(modulo):
    """Restaura los datos de un módulo desde un JSON enviado por el cliente."""
    mapa = {
        'agenda': F_AGENDA, 'vencimientos': F_VENCIMIENTOS,
        'vacaciones': F_VACACIONES, 'clipbox': F_CLIPBOX,
        'peritos': F_PERITOS, 'boletin': F_BOLETIN,
        'instruccion_penal': F_INSTRUCCION,
        'minutas': F_MINUTAS, 'correos': F_CORREOS,
        'auxilios': F_AUXILIOS, 'presos': F_PRESOS,
        'notificajud': F_NOTIFICAJUD,
        'guardias': F_GUARDIAS,
        'ausencias': F_AUSENCIAS,
        'archivo': F_ARCHIVO
    }
    if modulo not in mapa:
        return jsonify({'success': False, 'error': 'Módulo no válido'}), 404
    datos = request.get_json(force=True)
    if not datos:
        return jsonify({'success': False, 'error': 'JSON vacío o inválido'}), 400
    ruta = _resolver_fichero_modulo(modulo, mapa[modulo])
    # Hacer backup de seguridad de los datos actuales antes de sobreescribir
    if os.path.exists(ruta):
        hacer_backup(f'{modulo}_pre_restauracion', cargar_json(ruta))
    ok = guardar_json(ruta, datos)
    if ok:
        log(f"Módulo '{modulo}' restaurado desde backup del cliente")
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Error al escribir fichero'}), 500

@app.route('/api/restaurar/zip', methods=['POST'])
def restaurar_desde_zip():
    """Restaura todos los módulos desde un fichero ZIP de backup subido por el cliente."""
    if 'archivo' not in request.files:
        return jsonify({'success': False, 'error': 'No se recibió ningún fichero'}), 400
    f = request.files['archivo']
    if not f.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': 'El fichero debe ser un .zip'}), 400

    mapa = {
        'agenda': F_AGENDA, 'vencimientos': F_VENCIMIENTOS,
        'vacaciones': F_VACACIONES, 'clipbox': F_CLIPBOX,
        'peritos': F_PERITOS, 'boletin': F_BOLETIN,
        'instruccion_penal': F_INSTRUCCION,
        'minutas': F_MINUTAS, 'correos': F_CORREOS,
        'auxilios': F_AUXILIOS, 'presos': F_PRESOS,
        'notificajud': F_NOTIFICAJUD,
        'guardias': F_GUARDIAS,
        'ausencias': F_AUSENCIAS,
        'archivo': F_ARCHIVO
    }

    restaurados = []
    errores = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, 'backup.zip')
            f.save(zip_path)

            if not zipfile.is_zipfile(zip_path):
                return jsonify({'success': False, 'error': 'El fichero no es un ZIP válido'}), 400

            with zipfile.ZipFile(zip_path, 'r') as zf:
                for nombre, fichero_compartido in mapa.items():
                    candidatos = [n for n in zf.namelist()
                                  if os.path.basename(n) == f'{nombre}.json']
                    if not candidatos:
                        continue
                    entrada = candidatos[0]
                    try:
                        contenido = zf.read(entrada)
                        datos = json.loads(contenido)
                        ruta_destino = _resolver_fichero_modulo(nombre, fichero_compartido)
                        # Backup de seguridad antes de sobreescribir
                        if os.path.exists(ruta_destino):
                            hacer_backup(f'{nombre}_pre_restauracion_zip', cargar_json(ruta_destino))
                        ok = guardar_json(ruta_destino, datos)
                        if ok:
                            restaurados.append(nombre)
                            log(f"ZIP restore: módulo '{nombre}' restaurado correctamente")
                        else:
                            errores.append(nombre)
                    except Exception as ex:
                        errores.append(nombre)
                        log(f"ZIP restore: error en módulo '{nombre}': {ex}", 'WARNING')
    except Exception as ex:
        log(f"ZIP restore: error general: {ex}", 'ERROR')
        return jsonify({'success': False, 'error': str(ex)}), 500

    if not restaurados:
        return jsonify({'success': False,
                        'error': 'No se encontró ningún módulo válido en el ZIP',
                        'errores': errores}), 400

    return jsonify({'success': True, 'restaurados': restaurados, 'errores': errores})

@app.route('/api/restaurar/usuarios', methods=['POST'])
def restaurar_zip_usuarios():
    """Restaura datos privados de usuarios desde un ZIP de backup de usuarios."""
    if 'archivo' not in request.files:
        return jsonify({'success': False, 'error': 'No se recibió ningún fichero'}), 400
    f = request.files['archivo']
    if not f.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': 'El fichero debe ser un .zip'}), 400

    restaurados = []
    errores = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, 'backup.zip')
            f.save(zip_path)

            if not zipfile.is_zipfile(zip_path):
                return jsonify({'success': False, 'error': 'El fichero no es un ZIP válido'}), 400

            with zipfile.ZipFile(zip_path, 'r') as zf:
                nombres_zip = zf.namelist()
                if '_tipo.txt' not in nombres_zip:
                    return jsonify({'success': False,
                                    'error': 'ZIP de tipo incorrecto (falta _tipo.txt)'}), 400
                tipo = zf.read('_tipo.txt').decode('utf-8').strip()
                if tipo != 'usuarios':
                    return jsonify({'success': False,
                                    'error': f'ZIP de tipo incorrecto (esperado "usuarios", recibido "{tipo}")'}), 400

                for nombre_entrada in nombres_zip:
                    partes = nombre_entrada.replace('\\', '/').split('/')
                    if len(partes) != 3 or partes[0] != 'usuarios' or not partes[2].endswith('.json'):
                        continue
                    uid = partes[1]
                    modulo = partes[2][:-5]
                    clave = f'{uid}/{modulo}'
                    try:
                        contenido = zf.read(nombre_entrada)
                        datos = json.loads(contenido)
                        ruta_destino = f_dato_usuario(uid, modulo)
                        if os.path.exists(ruta_destino):
                            hacer_backup(f'usr_{uid}_{modulo}_pre_restauracion', cargar_json(ruta_destino))
                        ok = guardar_json(ruta_destino, datos)
                        if ok:
                            restaurados.append(clave)
                            log(f"ZIP restore usuarios: '{clave}' restaurado")
                        else:
                            errores.append(clave)
                    except Exception as ex:
                        errores.append(clave)
                        log(f"ZIP restore usuarios: error en '{clave}': {ex}", 'WARNING')

    except Exception as ex:
        log(f"ZIP restore usuarios: error general: {ex}", 'ERROR')
        return jsonify({'success': False, 'error': str(ex)}), 500

    if not restaurados:
        return jsonify({'success': False,
                        'error': 'No se encontraron datos de usuarios en el ZIP',
                        'errores': errores}), 400

    return jsonify({'success': True, 'restaurados': restaurados, 'errores': errores})

@app.route('/api/restaurar/equipos', methods=['POST'])
def restaurar_zip_equipos():
    """Restaura datos de equipos desde un ZIP de backup de equipos."""
    if 'archivo' not in request.files:
        return jsonify({'success': False, 'error': 'No se recibió ningún fichero'}), 400
    f = request.files['archivo']
    if not f.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': 'El fichero debe ser un .zip'}), 400

    restaurados = []
    errores = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, 'backup.zip')
            f.save(zip_path)

            if not zipfile.is_zipfile(zip_path):
                return jsonify({'success': False, 'error': 'El fichero no es un ZIP válido'}), 400

            with zipfile.ZipFile(zip_path, 'r') as zf:
                nombres_zip = zf.namelist()
                if '_tipo.txt' not in nombres_zip:
                    return jsonify({'success': False,
                                    'error': 'ZIP de tipo incorrecto (falta _tipo.txt)'}), 400
                tipo = zf.read('_tipo.txt').decode('utf-8').strip()
                if tipo != 'equipos':
                    return jsonify({'success': False,
                                    'error': f'ZIP de tipo incorrecto (esperado "equipos", recibido "{tipo}")'}), 400

                for nombre_entrada in nombres_zip:
                    partes = nombre_entrada.replace('\\', '/').split('/')
                    if len(partes) != 3 or partes[0] != 'equipos' or not partes[2].endswith('.json'):
                        continue
                    gid = partes[1]
                    modulo = partes[2][:-5]
                    clave = f'{gid}/{modulo}'
                    try:
                        contenido = zf.read(nombre_entrada)
                        datos = json.loads(contenido)
                        ruta_destino = f_dato_grupo(gid, modulo)
                        if os.path.exists(ruta_destino):
                            hacer_backup(f'grp_{gid}_{modulo}_pre_restauracion', cargar_json(ruta_destino))
                        ok = guardar_json(ruta_destino, datos)
                        if ok:
                            restaurados.append(clave)
                            log(f"ZIP restore equipos: '{clave}' restaurado")
                        else:
                            errores.append(clave)
                    except Exception as ex:
                        errores.append(clave)
                        log(f"ZIP restore equipos: error en '{clave}': {ex}", 'WARNING')

    except Exception as ex:
        log(f"ZIP restore equipos: error general: {ex}", 'ERROR')
        return jsonify({'success': False, 'error': str(ex)}), 500

    if not restaurados:
        return jsonify({'success': False,
                        'error': 'No se encontraron datos de equipos en el ZIP',
                        'errores': errores}), 400

    return jsonify({'success': True, 'restaurados': restaurados, 'errores': errores})


@app.route('/api/backup/<modulo>', methods=['GET'])
def descargar_backup(modulo):
    """Descarga el fichero JSON de un módulo directamente."""
    mapa = {
        'agenda': F_AGENDA, 'vencimientos': F_VENCIMIENTOS,
        'vacaciones': F_VACACIONES, 'clipbox': F_CLIPBOX,
        'peritos': F_PERITOS, 'boletin': F_BOLETIN,
        'instruccion_penal': F_INSTRUCCION,
        'minutas': F_MINUTAS, 'correos': F_CORREOS,
        'auxilios': F_AUXILIOS, 'presos': F_PRESOS,
        'notificajud': F_NOTIFICAJUD,
        'guardias': F_GUARDIAS,
        'ausencias': F_AUSENCIAS,
        'archivo': F_ARCHIVO
    }
    if modulo not in mapa:
        return jsonify({'error': 'Módulo no válido'}), 404
    ruta = _resolver_fichero_modulo(modulo, mapa[modulo])
    if not os.path.exists(ruta):
        return jsonify({'error': 'Sin datos'}), 404
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    from flask import Response
    return Response(
        contenido,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={modulo}_{datetime.now().strftime("%Y-%m-%d")}.json'}
    )

# ══════════════════════════════════════════════
# PERSONALIZACIÓN DEL TRIBUNAL
# ══════════════════════════════════════════════
F_TRIBUNAL = os.path.join(CONFIG_DIR, 'tribunal.json')

@app.route('/api/config/tribunal', methods=['GET'])
def tribunal_get():
    if os.path.exists(F_TRIBUNAL):
        return jsonify(cargar_json(F_TRIBUNAL))
    return jsonify({
        'titulo': 'Portal Judicial — Tribunal de Instancia',
        'subtitulo': 'Vilagarcía de Arousa'
    })

@app.route('/api/config/tribunal', methods=['POST'])
def tribunal_post():
    datos = request.get_json(force=True) or {}
    titulo    = datos.get('titulo', '').strip()
    subtitulo = datos.get('subtitulo', '').strip()
    guardar_json(F_TRIBUNAL, {'titulo': titulo, 'subtitulo': subtitulo})
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# ORDEN DE PESTAÑAS (configuración por usuario)
# ══════════════════════════════════════════════
F_ORDEN_TABS = os.path.join(CONFIG_DIR, 'orden_tabs.json')

@app.route('/api/config/orden-tabs', methods=['GET'])
def orden_tabs_get():
    if os.path.exists(F_ORDEN_TABS):
        return jsonify(cargar_json(F_ORDEN_TABS))
    return jsonify({'orden': []})

@app.route('/api/config/orden-tabs', methods=['POST'])
def orden_tabs_post():
    datos = request.get_json(force=True) or {}
    orden = datos.get('orden', [])
    guardar_json(F_ORDEN_TABS, {'orden': orden})
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# RUTA DE RED (configuración)
# ══════════════════════════════════════════════
@app.route('/api/config/ruta-red', methods=['GET'])
def config_red_get():
    if os.path.exists(RED_BACKUP):
        with open(RED_BACKUP, 'r', encoding='utf-8') as f:
            return jsonify({'ruta': f.read().strip()})
    return jsonify({'ruta': ''})

@app.route('/api/config/ruta-red', methods=['POST'])
def config_red_post():
    ruta = (request.get_json(force=True) or {}).get('ruta', '').strip()
    lock = _adquirir_lock_fichero(RED_BACKUP)
    try:
        with open(RED_BACKUP, 'w', encoding='utf-8') as f:
            f.write(ruta)
    finally:
        _liberar_lock_fichero(lock)
    return jsonify({'success': True})

# ══════════════════════════════════════════════
# SERVIR MÓDULOS HTML (para los iframes del portal)
# ══════════════════════════════════════════════
# Rutas a los HTML de cada módulo (todos en Portal_Judicial/modulos/)
MODULOS_DIR = os.path.join(BASE_DIR, 'modulos')

RUTAS_MODULOS = {k: os.path.join(MODULOS_DIR, f'{k}.html') for k in [
    'agenda', 'vencimientos', 'vacaciones', 'clipbox', 'alardes',
    'peritos', 'instruccion', 'minutas', 'correos', 'auxilios',
    'boletin', 'presos', 'notificajud', 'guardias', 'ausencias',
    'archivo', 'dir3'
]}

@app.route('/modulo/<nombre>')
def servir_modulo(nombre):
    """Sirve el HTML de cada módulo dentro del iframe del portal."""
    if nombre not in RUTAS_MODULOS:
        return f"<h2>Módulo '{_html_mod.escape(nombre)}' no encontrado</h2>", 404

    ruta = RUTAS_MODULOS[nombre]

    # Si el fichero no existe, devolver pantalla de error amigable
    if not os.path.exists(ruta):
        return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
        <style>body{{font-family:Segoe UI,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0f4ff;color:#1a3a5f}}
        .box{{text-align:center;padding:40px;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,.1);max-width:500px}}
        h2{{color:#c0392b}}p{{color:#555;margin-top:10px}}</style></head>
        <body><div class="box"><h2>⚠️ Módulo no encontrado</h2>
        <p>No se encontró el archivo del módulo <strong>{_html_mod.escape(nombre)}</strong>.</p>
        <p style="font-size:12px;margin-top:16px;color:#888">Ruta esperada:<br>{_html_mod.escape(ruta)}</p>
        </div></body></html>""", 404

    carpeta = os.path.dirname(ruta)
    nombre_fichero = os.path.basename(ruta)

    # Leer el HTML e inyectar base href para que los recursos relativos funcionen
    with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
        contenido = f.read()

    # Inyectar <base href> para recursos relativos (CSS, JS, imágenes)
    base_url = f'/modulo-recursos/{nombre}/'

    # Si se solicita en contexto de equipo, preparar el interceptor fetch/XHR
    equipo_raw  = request.args.get('equipo') or ''
    equipo_safe = ''.join(c for c in equipo_raw if c.isalnum() or c in '-_')
    if equipo_safe:
        interceptor = (
            f'<script>(function(){{'
            f'var E="{equipo_safe}";'
            f'function _a(u){{return typeof u==="string"&&u.charAt(0)==="/"?u+(u.indexOf("?")>=0?"&":"?")+"equipo="+E:u;}}'
            f'var _f=window.fetch;window.fetch=function(u,o){{return _f(_a(u),o);}};'
            f'var _x=XMLHttpRequest.prototype.open;'
            f'XMLHttpRequest.prototype.open=function(){{var a=[].slice.call(arguments);a[1]=_a(a[1]);_x.apply(this,a);}};'
            f'}})();</script>'
        )
        inject_head = f'<head>\n<base href="{base_url}">\n{interceptor}'
    else:
        inject_head = f'<head>\n<base href="{base_url}">'

    if '<head>' in contenido:
        contenido = contenido.replace('<head>', inject_head, 1)
    elif '<HEAD>' in contenido:
        contenido = contenido.replace('<HEAD>', inject_head, 1)

    # Parches de URLs hardcodeadas en módulos específicos
    # Vacaciones usa http://localhost:8765 → convertir a rutas relativas
    contenido = contenido.replace('http://localhost:8765', '')

    return contenido, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/modulo-recursos/<nombre>/<path:recurso>')
def servir_recurso_modulo(nombre, recurso):
    """Sirve recursos estáticos (CSS, JS, imágenes) de cada módulo."""
    if nombre not in RUTAS_MODULOS:
        return "No encontrado", 404

    carpeta = os.path.dirname(RUTAS_MODULOS[nombre])
    return send_from_directory(carpeta, recurso)

# Endpoint ping para keepalive
@app.route('/ping')
def ping():
    return jsonify({'pong': True})

# ══════════════════════════════════════════════
# BÚSQUEDA GLOBAL
# ══════════════════════════════════════════════

def _busqueda_global_data(q):
    """
    Busca q en todos los módulos (agenda, vencimientos, peritos, instrucción,
    clipbox, auxilios, presos, notificajud) incluyendo datos de grupos/equipos.
    Devuelve lista de dicts {modulo, icono, titulo, detalle, extra}.
    """
    if not q or len(q.strip()) < 2:
        return []
    q_low = q.strip().lower()
    resultados = []

    grupos_all = cargar_grupos()

    def _ficheros_modulo(modulo_id, f_shared):
        """Yield (ruta, grupo_label) para: usuario_privado + compartido + grupos."""
        rutas_vistas = set()
        # 1) Fichero privado del usuario activo (si el módulo es privado para él)
        uid_act = _uid_activo_actual()
        if uid_act:
            usuarios = cargar_json(F_USUARIOS_LISTA).get('usuarios', [])
            u = next((x for x in usuarios if x['id'] == uid_act), None)
            if u and modulo_id in u.get('modulos_privados', []):
                f_priv = f_dato_usuario(uid_act, modulo_id)
                if os.path.exists(f_priv):
                    rutas_vistas.add(os.path.normpath(f_priv))
                    yield f_priv, None
        # 2) Fichero compartido
        rn = os.path.normpath(f_shared)
        if rn not in rutas_vistas:
            rutas_vistas.add(rn)
            yield f_shared, None
        # 3) Ficheros de grupos
        for g in grupos_all:
            if modulo_id in g.get('modulos', []):
                f_g = f_dato_grupo(g['id'], modulo_id)
                rng = os.path.normpath(f_g)
                if os.path.exists(f_g) and rng not in rutas_vistas:
                    rutas_vistas.add(rng)
                    yield f_g, g.get('nombre', g['id'])

    def _pfx(grp, val=''):
        return (f'[{grp}] ' if grp else '') + (val or '')

    # ── AGENDA ──────────────────────────────────────────────────────────────
    for f_a, grp in _ficheros_modulo('agenda', F_AGENDA):
        try:
            for s in (cargar_json(f_a) or {}).get('senalamientos', []):
                tipo, exp = s.get('tipo',''), s.get('expediente','')
                texto = ' '.join([exp, tipo, s.get('partes',''), s.get('letrado',''),
                                  s.get('observaciones',''), s.get('plaza',''),
                                  s.get('sala',''), s.get('fecha',''),
                                  f'{tipo} {exp}', exp.split('/')[0] if '/' in exp else '']).lower()
                if q_low in texto:
                    resultados.append({'modulo':'agenda','icono':'📅',
                        'titulo': f'{tipo} {exp}',
                        'detalle': f"{s.get('fecha','')} {s.get('hora','')} · {s.get('partes','')}",
                        'extra': _pfx(grp, s.get('plaza',''))})
        except Exception:
            pass

    # ── GUARDIAS ────────────────────────────────────────────────────────────
    for f_gu, grp in _ficheros_modulo('guardias', F_GUARDIAS):
        try:
            gd = cargar_json(f_gu) or {}
            for func in gd.get('funcionarios', []):
                nombre_f = func.get('nombre', '')
                texto = ' '.join([nombre_f, func.get('dept', ''),
                                  str(func.get('codigo', ''))]).lower()
                if q_low in texto:
                    estado = '🟢 Activo' if func.get('activo') else '⚪ Inactivo'
                    resultados.append({'modulo':'guardias','icono':'🛡️',
                        'titulo': nombre_f,
                        'detalle': f"{func.get('dept','')} · Código {func.get('codigo','')}",
                        'extra': _pfx(grp, estado)})
        except Exception:
            pass

    # ── VENCIMIENTOS ─────────────────────────────────────────────────────────
    for f_v, grp in _ficheros_modulo('vencimientos', F_VENCIMIENTOS):
        try:
            vd = cargar_json(f_v) or {}
            asuntos = vd if isinstance(vd, list) else vd.get('asuntos', [])
            for a in asuntos:
                proc = a.get('procedimiento') or a.get('tipo','')
                texto = ' '.join([proc, a.get('estado',''), a.get('ultimoDia',''),
                                  a.get('plaza',''), str(a.get('plazoDias',''))]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'vencimientos','icono':'⏱️',
                        'titulo': proc or 'Vencimiento',
                        'detalle': f"Vence: {a.get('ultimoDia','?')} · {a.get('plazoDias','?')} días hábiles",
                        'extra': _pfx(grp, a.get('plaza',''))})
        except Exception:
            pass

    # ── PERITOS ──────────────────────────────────────────────────────────────
    for f_p, grp in _ficheros_modulo('peritos', F_PERITOS):
        try:
            pd = cargar_json(f_p) or {}
            esps = {e['id']: e['nombre'] for e in pd.get('especialidades', [])}
            for p in pd.get('peritos', []):
                esp_n = esps.get(p.get('especialidadId'),'')
                texto = ' '.join([p.get('nombre',''), p.get('direccion',''),
                                  p.get('email',''), p.get('telefono',''), esp_n]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'peritos','icono':'🔬',
                        'titulo': p.get('nombre',''),
                        'detalle': esp_n,
                        'extra': _pfx(grp, p.get('telefono',''))})
            for s in pd.get('selecciones', []):
                texto = ' '.join([s.get('peritoNombre',''), s.get('expediente',''),
                                  s.get('motivo',''), s.get('estadoCargo','')]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'peritos','icono':'🔬',
                        'titulo': f"Selección: {s.get('peritoNombre','')}",
                        'detalle': f"Expte: {s.get('expediente','')} · {s.get('estadoCargo','')}",
                        'extra': _pfx(grp, s.get('fechaSeleccion','')[:10] if s.get('fechaSeleccion') else '')})
        except Exception:
            pass

    # ── INSTRUCCIÓN PENAL ────────────────────────────────────────────────────
    for f_i, grp in _ficheros_modulo('instruccion_penal', F_INSTRUCCION):
        try:
            inst = cargar_json(f_i) or {}
            for p in inst.get('procedimientos', []):
                tipo, num, anyo = p.get('tipo',''), str(p.get('numero','')), str(p.get('anyo',''))
                cerrado = p.get('cerrado', False)
                es_prorroga = bool(p.get('fechaManual', False))
                fv = p.get('fechaVencimiento','')
                texto = ' '.join([tipo, num, anyo, p.get('plaza',''),
                                  p.get('descripcion',''), p.get('notas',''),
                                  f'{tipo} {num}/{anyo}', f'{num}/{anyo}', fv,
                                  'cerrado' if cerrado else 'abierto',
                                  'prorroga' if es_prorroga else '']).lower()
                if q_low in texto:
                    lbl = '🔒 Cerrado' if cerrado else ('🔄 Prórroga' if es_prorroga else '🟢 Abierto')
                    resultados.append({'modulo':'instruccion','icono':'⚖️',
                        'titulo': f'{tipo} {num}/{anyo}',
                        'detalle': p.get('descripcion','') or p.get('notas','') or p.get('plaza',''),
                        'extra': _pfx(grp, f'{lbl} · Vence: {fv}')})
        except Exception:
            pass

    # ── CLIPBOX / MODELOS ────────────────────────────────────────────────────
    for f_c, grp in _ficheros_modulo('clipbox', F_CLIPBOX):
        try:
            for c in (cargar_json(f_c) or {}).get('clips', []):
                texto = ' '.join([c.get('title',''), c.get('text',''),
                                  c.get('letrado',''), ' '.join(c.get('tags',[]))]).lower()
                if q_low in texto:
                    txt = c.get('text','')
                    resultados.append({'modulo':'clipbox','icono':'📋',
                        'titulo': c.get('title','Sin título'),
                        'detalle': (txt[:100]+'...') if len(txt)>100 else txt,
                        'extra': _pfx(grp, c.get('letrado',''))})
        except Exception:
            pass

    # ── AUXILIOS JUDICIALES ──────────────────────────────────────────────────
    for f_ax, grp in _ficheros_modulo('auxilios', F_AUXILIOS):
        try:
            for a in (cargar_json(f_ax) or {}).get('auxilios', []):
                proc = a.get('procedimiento','')
                texto = ' '.join([proc, a.get('tipo_nombre',''), a.get('tipo',''),
                                  a.get('plaza',''), a.get('estado',''),
                                  a.get('detalles',''), a.get('tribunal','')]).lower()
                if q_low in texto:
                    tipo_a = a.get('tipo_nombre') or a.get('tipo','Auxilio')
                    resultados.append({'modulo':'auxilios','icono':'🔗',
                        'titulo': tipo_a + (f' — {proc}' if proc else ''),
                        'detalle': f"{a.get('fecha','')} {a.get('hora','')} · {a.get('estado','')}",
                        'extra': _pfx(grp, a.get('plaza',''))})
        except Exception:
            pass

    # ── PRESOS ───────────────────────────────────────────────────────────────
    for f_pr, grp in _ficheros_modulo('presos', F_PRESOS):
        try:
            pd2 = cargar_json(f_pr) or {}
            lista_p = pd2 if isinstance(pd2, list) else pd2.get('presos', [])
            for p in lista_p:
                nombre_p = (p.get('nombre','') + ' ' + p.get('apellidos','')).strip()
                texto = ' '.join([nombre_p, p.get('dni',''), p.get('codigoBD',''),
                                  p.get('codigoIPENCAT',''), p.get('centro',''),
                                  p.get('situacion',''), p.get('documento',''),
                                  p.get('cod_interno',''), p.get('procedimiento',''),
                                  p.get('instructor',''), p.get('sentenciador','')]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'presos','icono':'🔒',
                        'titulo': nombre_p or p.get('codigoBD','Preso'),
                        'detalle': f"{p.get('situacion','')} · {p.get('centro','')}",
                        'extra': _pfx(grp, p.get('dni','') or p.get('documento',''))})
        except Exception:
            pass

    # ── NOTIFICAJUD ──────────────────────────────────────────────────────────
    for f_nj, grp in _ficheros_modulo('notificajud', F_NOTIFICAJUD):
        try:
            nj = cargar_json(f_nj) or {}
            for n in nj.get('notificaciones', []):
                dilig = n.get('diligencia','')
                texto = ' '.join([dilig, n.get('resultado',''), n.get('persona',''),
                                  n.get('plaza',''), n.get('relacion',''),
                                  n.get('nombreNotificado',''), n.get('funcionarioNombre','')]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'notificajud','icono':'🔔',
                        'titulo': dilig or 'Notificación',
                        'detalle': f"{n.get('resultado','')} · {n.get('persona','')}",
                        'extra': _pfx(grp, n.get('plaza',''))})
            # Buscar también en funcionarios de notificajud
            for func in nj.get('funcionarios', []):
                nombre_f = func.get('nombre', '')
                texto = ' '.join([nombre_f, func.get('email', ''),
                                  func.get('telefono', '')]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'notificajud','icono':'👤',
                        'titulo': nombre_f,
                        'detalle': 'Funcionario Notifica/Turnos',
                        'extra': _pfx(grp, func.get('telefono','') or func.get('email',''))})
            # Buscar en registro de diligencias (siempre compartido)
            for rd in nj.get('registroDiligencias', []):
                texto = ' '.join([rd.get('idSACE',''), rd.get('organo',''),
                                  rd.get('procedimiento',''), rd.get('direccion',''),
                                  rd.get('funcionarioAsignadoNombre',''),
                                  rd.get('tipoActo',''), rd.get('estado','')]).lower()
                if q_low in texto:
                    resultados.append({'modulo':'notificajud','icono':'📋',
                        'titulo': f"{rd.get('idSACE','')} - {rd.get('procedimiento','')}",
                        'detalle': f"{rd.get('tipoActo','')} · {rd.get('estado','')}",
                        'extra': _pfx(grp, rd.get('direccion',''))})
        except Exception:
            pass

    # ── AUSENCIAS ────────────────────────────────────────────────────────────
    for f_au, grp in _ficheros_modulo('ausencias', F_AUSENCIAS):
        try:
            ad = cargar_json(f_au) or {}
            plazas_map = {p['id']: p['nombre'] for p in ad.get('plazas', [])}
            cargos_map = {}
            for p in ad.get('plazas', []):
                for c in p.get('cargos', []):
                    cargos_map[c['id']] = c['nombre']
            for aus in ad.get('ausencias', []):
                titular = aus.get('titular', '')
                plaza_n = plazas_map.get(aus.get('plazaId'), '')
                cargo_n = cargos_map.get(aus.get('cargoId'), '')
                texto = ' '.join([titular, plaza_n, cargo_n,
                                  aus.get('motivo', ''), aus.get('notas', ''),
                                  aus.get('sustituto', '')]).lower()
                if q_low in texto:
                    resultados.append({'modulo': 'ausencias', 'icono': '🏛️',
                        'titulo': f'{titular} — {cargo_n}',
                        'detalle': f"{plaza_n} · {aus.get('fechaInicio','')} a {aus.get('fechaFin','')}",
                        'extra': _pfx(grp, aus.get('notas', ''))})
        except Exception:
            pass

    # ── DIR3 ────────────────────────────────────────────────────────────────
    try:
        dir3_data = _cargar_dir3()
        if dir3_data and 'registros' in dir3_data:
            palabras = _sin_acentos(q_low).split()
            count = 0
            for r in dir3_data['registros']:
                if count >= 10:
                    break
                texto = _sin_acentos(' '.join([
                    r.get('co',''), r.get('no',''),
                    r.get('cr',''), r.get('nr',''),
                    r.get('cm',''), r.get('pr','')
                ]).lower())
                if all(p in texto for p in palabras):
                    dir3code = r.get('cu') or r.get('co','')
                    dir3name = r.get('nu') or r.get('no','') if r.get('cu') else r.get('no','')
                    resultados.append({'modulo': 'dir3', 'icono': '🏢',
                        'titulo': f"{dir3code} — {dir3name}",
                        'detalle': f"{r.get('nr','')}",
                        'extra': f"{r.get('cm','')} · {r.get('pr','')}"})
                    count += 1
    except Exception:
        pass

    return resultados


@app.route('/api/search')
def busqueda_global():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'resultados': []})
    resultados = _busqueda_global_data(q)
    return jsonify({'resultados': resultados[:50], 'total': len(resultados)})

# ══════════════════════════════════════════════
# MINUTAS
# ══════════════════════════════════════════════
import uuid as _uuid

def cargar_minutas():
    if not os.path.exists(F_MINUTAS):
        guardar_json(F_MINUTAS, {'minutas': [], 'plazas_propias': []})
    return cargar_json(F_MINUTAS)

def guardar_minutas(datos):
    guardar_json(F_MINUTAS, datos)

def _uid_activo_actual():
    """Devuelve el id del usuario activo leyendo el fichero de sesión."""
    f = F_USUARIO_ACTIVO
    if os.path.exists(f):
        d = cargar_json(f)
        return d.get('id','')
    return ''

def _usuario_por_id(uid):
    """Devuelve el dict del usuario con ese id, o {} si no existe."""
    usuarios = cargar_json(F_USUARIOS_LISTA).get('usuarios', [])
    for u in usuarios:
        if u.get('id') == uid:
            return u
    return {}

@app.route('/api/minutas', methods=['GET'])
def minutas_get():
    uid = _uid_activo_actual()
    datos = cargar_minutas()
    # Devuelve minutas donde el usuario es remitente o destinatario
    resultado = [
        m for m in datos.get('minutas', [])
        if m.get('de', {}).get('id') == uid
        or any(p.get('id') == uid for p in m.get('para', []))
    ]
    return jsonify({'minutas': resultado, 'plazas_propias': datos.get('plazas_propias', [])})

@app.route('/api/minutas', methods=['POST'])
def minutas_post():
    body = request.get_json(force=True) or {}
    # Construir remitente desde usuario activo
    uid_remitente = _uid_activo_actual()
    u_remitente = _usuario_por_id(uid_remitente)
    de_obj = {
        'id': uid_remitente,
        'nombre': u_remitente.get('nombre', uid_remitente),
        'rol': u_remitente.get('rol', 'funcionario')
    }
    # Convertir lista de IDs destinatarios a lista de objetos
    para_ids = body.get('para', [])
    para_objs = []
    for pid in para_ids:
        if isinstance(pid, dict):
            # Ya viene como objeto (compatibilidad)
            para_objs.append(pid)
        else:
            u_dest = _usuario_por_id(pid)
            para_objs.append({
                'id': pid,
                'nombre': u_dest.get('nombre', pid),
                'leido': False,
                'leido_en': None
            })
    nueva = {
        'id': str(_uuid.uuid4()),
        'asunto':    body.get('asunto', ''),
        'cuerpo':    body.get('cuerpo', ''),
        'ref':       body.get('ref', {}),
        'plaza_minuta': body.get('plaza_minuta', ''),
        'de':        de_obj,
        'para':      para_objs,
        'estado':    'pendiente',
        'comentario_resolucion': '',
        'prioridad': body.get('prioridad', 'normal'),
        'creadaEn':  datetime.utcnow().isoformat() + 'Z',
        'resueltaEn': None,
        'hilo':      []
    }
    with editar_json(F_MINUTAS) as datos:
        datos.setdefault('minutas', [])
        datos['minutas'].append(nueva)
    # E2: Notificar a destinatarios
    for p in para_objs:
        pid = p.get('id', '')
        if pid and pid != uid_remitente:
            _crear_notificacion(pid, 'minuta',
                f"📄 Nueva minuta de {de_obj.get('nombre','')}: {nueva.get('asunto','')[:50]}",
                enlace='minutas')
    return jsonify({'success': True, 'minuta': nueva})

@app.route('/api/minutas/<mid>', methods=['PUT'])
def minutas_put(mid):
    body = request.get_json(force=True) or {}
    uid = _uid_activo_actual()
    with editar_json(F_MINUTAS) as datos:
        datos.setdefault('minutas', [])
        minuta = next((m for m in datos['minutas'] if m['id'] == mid), None)
        if not minuta:
            return jsonify({'error': 'No encontrada'}), 404

        # Actualizar estado
        if 'estado' in body:
            minuta['estado'] = body['estado']
            if body['estado'] == 'resuelta':
                minuta['resueltaEn'] = datetime.utcnow().isoformat() + 'Z'
            if body['estado'] == 'pendiente':
                minuta['resueltaEn'] = None

        # Actualizar comentario de resolución
        if 'comentario_resolucion' in body:
            minuta['comentario_resolucion'] = body['comentario_resolucion']

        # Marcar como leído para el usuario activo
        if body.get('marcar_leido'):
            for dest in minuta.get('para', []):
                if dest.get('id') == uid:
                    dest['leido'] = True
                    dest['leido_en'] = datetime.utcnow().isoformat() + 'Z'

        # Añadir mensaje al hilo
        if 'hilo_mensaje' in body:
            usuarios = cargar_usuarios()
            u = next((x for x in usuarios if x['id'] == uid), None)
            nombre = u['nombre'] if u else uid
            minuta['hilo'].append({
                'id': str(_uuid.uuid4()),
                'de': uid,
                'nombre': nombre,
                'texto': body['hilo_mensaje'],
                'fecha': datetime.utcnow().isoformat() + 'Z'
            })

    return jsonify({'success': True, 'minuta': minuta})

@app.route('/api/minutas/<mid>', methods=['DELETE'])
def minutas_delete(mid):
    uid = _uid_activo_actual()
    es_sa = uid in [u.get('id') for u in cargar_usuarios() if u.get('rol') == 'superadmin']
    with editar_json(F_MINUTAS) as datos:
        datos.setdefault('minutas', [])
        minuta = next((m for m in datos['minutas'] if m['id'] == mid), None)
        if not minuta:
            return jsonify({'error': 'No encontrada'}), 404
        if minuta.get('de', {}).get('id') != uid and not es_sa:
            return jsonify({'error': 'Sin permiso'}), 403
        datos['minutas'] = [m for m in datos['minutas'] if m['id'] != mid]
    return jsonify({'success': True})

@app.route('/api/minutas/sin-leer', methods=['GET'])
def minutas_sin_leer():
    uid = _uid_activo_actual()
    datos = cargar_minutas()
    count = sum(
        1 for m in datos.get('minutas', [])
        if any(p.get('id') == uid and not p.get('leido', False) for p in m.get('para', []))
    )
    return jsonify({'sinLeer': count})

@app.route('/api/minutas/plazas', methods=['GET'])
def minutas_plazas_get():
    # Plazas de agenda
    agenda = cargar_json(F_AGENDA)
    plazas_agenda = agenda.get('plazas', [])
    # Plazas propias de minutas
    datos = cargar_minutas()
    plazas_propias = datos.get('plazas_propias', [])
    return jsonify({'plazas_agenda': plazas_agenda, 'plazas_propias': plazas_propias})

@app.route('/api/minutas/plazas-propias', methods=['POST'])
def minutas_plazas_propias_post():
    body = request.get_json(force=True) or {}
    with editar_json(F_MINUTAS) as datos:
        datos['plazas_propias'] = body.get('plazas_propias', [])
    return jsonify({'success': True})

# ─────────────────────────────────────────────
# CORREOS
# ─────────────────────────────────────────────
def cargar_correos():
    if os.path.exists(F_CORREOS):
        datos = cargar_json(F_CORREOS)
        # Asegurar claves por defecto
        for k, v in DEFAULTS[F_CORREOS].items():
            if k not in datos:
                datos[k] = v
        return datos
    return dict(DEFAULTS[F_CORREOS])

def guardar_correos(datos):
    guardar_json(F_CORREOS, datos)

@app.route('/api/correos', methods=['GET'])
def correos_get():
    return jsonify(cargar_correos())

@app.route('/api/correos/sugerencias', methods=['POST'])
def correos_sugerencias_post():
    body = request.get_json(force=True) or {}
    with editar_json(F_CORREOS) as datos:
        datos['sugerencias'] = body.get('sugerencias', {})
    return jsonify({'success': True})

@app.route('/api/correos/borradores', methods=['POST'])
def correos_borradores_post():
    body = request.get_json(force=True) or {}
    with editar_json(F_CORREOS) as datos:
        datos['borradores'] = body.get('borradores', {})
    return jsonify({'success': True})

@app.route('/api/correos/sesion', methods=['POST'])
def correos_sesion_post():
    body = request.get_json(force=True) or {}
    with editar_json(F_CORREOS) as datos:
        datos['sesion'] = body.get('sesion', None)
    return jsonify({'success': True})

@app.route('/api/correos/mapa', methods=['POST'])
def correos_mapa_post():
    body = request.get_json(force=True) or {}
    with editar_json(F_CORREOS) as datos:
        datos['mapa_localidad_cp'] = body.get('mapa', {})
    return jsonify({'success': True})

@app.route('/api/correos/config', methods=['POST'])
def correos_config_post():
    body = request.get_json(force=True) or {}
    with editar_json(F_CORREOS) as datos:
        datos['config'] = body.get('config', {})
    return jsonify({'success': True})

# ─── CHAT ───────────────────────────────────────────────────

def cargar_presencia():
    return cargar_json(F_PRESENCIA) if os.path.exists(F_PRESENCIA) else {}

def cargar_chat():
    datos = cargar_json(F_CHAT) if os.path.exists(F_CHAT) else {'mensajes': []}
    # Podar mensajes > 7 días
    limite = (datetime.utcnow() - timedelta(days=7)).timestamp()
    datos['mensajes'] = [m for m in datos['mensajes'] if m.get('ts', 0) > limite]
    return datos

@app.route('/api/chat/ping', methods=['POST'])
def chat_ping():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    # Actualizar presencia
    u = _usuario_por_id(uid)
    with editar_json(F_PRESENCIA) as presencia:
        presencia[uid] = {
            'nombre': u.get('nombre', uid),
            'avatar': u.get('avatar', '👤'),
            'ts': datetime.utcnow().timestamp()
        }
    # Usuarios online (ping < 40s)
    ahora = datetime.utcnow().timestamp()
    online = [
        {'id': k, 'nombre': v['nombre'], 'avatar': v['avatar']}
        for k, v in presencia.items()
        if ahora - v.get('ts', 0) < 40 and k != uid
    ]
    # Mensajes no leídos para el usuario activo
    chat = cargar_chat()
    no_leidos = sum(
        1 for m in chat['mensajes']
        if m.get('para') == uid and not m.get('leido')
    )
    # E2: Notificaciones sin leer
    notif_data = _cargar_notificaciones()
    notif_sin_leer = sum(1 for n in notif_data.get(uid, []) if not n.get('leida'))
    # E1: Tablón sin leer
    tablon_data = _cargar_tablon()
    hoy_tbl = datetime.now().strftime('%Y-%m-%d')
    tablon_sin_leer = sum(1 for a in tablon_data.get('anuncios', [])
                          if a.get('activo', True)
                          and (not a.get('caduca') or a['caduca'] >= hoy_tbl)
                          and uid not in a.get('leido_por', []))
    return jsonify({
        'online': online, 'no_leidos': no_leidos,
        'notif_sin_leer': notif_sin_leer,
        'tablon_sin_leer': tablon_sin_leer
    })

@app.route('/api/chat/mensajes', methods=['GET'])
def chat_mensajes_get():
    uid = _uid_activo_actual()
    con = request.args.get('con', '')
    with editar_json(F_CHAT) as chat:
        chat.setdefault('mensajes', [])
        # Podar mensajes > 7 días
        limite = (datetime.utcnow() - timedelta(days=7)).timestamp()
        chat['mensajes'] = [m for m in chat['mensajes'] if m.get('ts', 0) > limite]
        # Conversación entre uid y con (ambas direcciones)
        conv = [
            m for m in chat['mensajes']
            if (m.get('de') == uid and m.get('para') == con) or
               (m.get('de') == con and m.get('para') == uid)
        ]
        conv = sorted(conv, key=lambda m: m.get('ts', 0))[-50:]
        # Marcar como leídos los mensajes recibidos
        for m in chat['mensajes']:
            if m.get('para') == uid and m.get('de') == con and not m.get('leido'):
                m['leido'] = True
    return jsonify({'mensajes': conv})

@app.route('/api/chat/mensaje', methods=['POST'])
def chat_mensaje_post():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    body = request.get_json(force=True) or {}
    # E3: Soporte para destinatarios múltiples (grupo)
    para_raw = body.get('para', '')
    texto = (body.get('texto') or '').strip()
    cita = body.get('cita') or None      # E3: mensaje citado {texto, autor}
    expediente = body.get('expediente') or None  # E3: referencia a expediente
    if not para_raw or not texto:
        return jsonify({'error': 'faltan campos'}), 400
    # Normalizar lista de destinatarios
    if isinstance(para_raw, list):
        destinatarios = para_raw
    else:
        destinatarios = [para_raw]
    u = _usuario_por_id(uid)
    mensajes_env = []
    for para in destinatarios:
        nuevo = {
            'id':        str(_uuid.uuid4()),
            'de':        uid,
            'de_nombre': u.get('nombre', uid),
            'de_avatar': u.get('avatar', '👤'),
            'para':      para,
            'texto':     texto,
            'ts':        datetime.utcnow().timestamp(),
            'leido':     False
        }
        if cita:
            nuevo['cita'] = cita
        if expediente:
            nuevo['expediente'] = expediente
        if len(destinatarios) > 1:
            nuevo['grupo'] = True
        mensajes_env.append(nuevo)
    with editar_json(F_CHAT) as chat:
        chat.setdefault('mensajes', [])
        # Podar mensajes > 7 días
        limite = (datetime.utcnow() - timedelta(days=7)).timestamp()
        chat['mensajes'] = [m for m in chat['mensajes'] if m.get('ts', 0) > limite]
        chat['mensajes'].extend(mensajes_env)
    # E2: Generar notificación para cada receptor
    for para in destinatarios:
        _crear_notificacion(para, 'chat',
            f"💬 Mensaje de {u.get('nombre', uid)}: {texto[:60]}{'…' if len(texto)>60 else ''}",
            enlace='chat')
    return jsonify({'success': True, 'mensaje': mensajes_env[0] if len(mensajes_env)==1 else mensajes_env})

# ══════════════════════════════════════════════
# E1: TABLÓN DE ANUNCIOS
# ══════════════════════════════════════════════

def _cargar_tablon():
    if not os.path.exists(F_TABLON):
        guardar_json(F_TABLON, {'anuncios': []})
    return cargar_json(F_TABLON)

@app.route('/api/tablon', methods=['GET'])
def tablon_get():
    datos = _cargar_tablon()
    hoy = datetime.now().strftime('%Y-%m-%d')
    # Filtrar caducados y no activos
    anuncios = [a for a in datos.get('anuncios', [])
                if a.get('activo', True) and (not a.get('caduca') or a['caduca'] >= hoy)]
    # Ordenar: fijados primero, luego por fecha desc
    anuncios.sort(key=lambda a: (0 if a.get('fijado') else 1, a.get('fecha', '')), reverse=False)
    anuncios.sort(key=lambda a: (0 if a.get('fijado') else 1))
    no_fijados = [a for a in anuncios if not a.get('fijado')]
    no_fijados.sort(key=lambda a: a.get('fecha', ''), reverse=True)
    fijados = [a for a in anuncios if a.get('fijado')]
    fijados.sort(key=lambda a: a.get('fecha', ''), reverse=True)
    return jsonify({'anuncios': fijados + no_fijados})

@app.route('/api/tablon', methods=['POST'])
def tablon_post():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    body = request.get_json(force=True) or {}
    titulo = (body.get('titulo') or '').strip()
    cuerpo = (body.get('cuerpo') or '').strip()
    if not titulo:
        return jsonify({'error': 'título requerido'}), 400
    u = _usuario_por_id(uid)
    categoria = body.get('categoria', 'informativo')
    if categoria not in ('urgente', 'informativo', 'recordatorio'):
        categoria = 'informativo'
    nuevo = {
        'id':        str(_uuid.uuid4()),
        'autor':     uid,
        'autor_nombre': u.get('nombre', uid),
        'autor_avatar': u.get('avatar', '📌'),
        'fecha':     datetime.now().strftime('%Y-%m-%dT%H:%M'),
        'titulo':    titulo,
        'cuerpo':    cuerpo,
        'categoria': categoria,
        'fijado':    bool(body.get('fijado', False)),
        'caduca':    body.get('caduca') or None,
        'leido_por': [uid],
        'activo':    True
    }
    with editar_json(F_TABLON) as datos:
        datos.setdefault('anuncios', [])
        datos['anuncios'].append(nuevo)
    # E2: Notificar a todos los usuarios excepto al autor
    todos = _listar_usuarios()
    for usr in todos:
        if usr.get('id') != uid and usr.get('rol') != 'superadmin':
            _crear_notificacion(usr['id'], 'tablon',
                f"📌 Nuevo aviso: {titulo[:50]}{'…' if len(titulo)>50 else ''}",
                enlace='tablon')
    return jsonify({'success': True, 'anuncio': nuevo})

@app.route('/api/tablon/<anuncio_id>', methods=['PUT'])
def tablon_put(anuncio_id):
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    body = request.get_json(force=True) or {}
    with editar_json(F_TABLON) as datos:
        for a in datos.get('anuncios', []):
            if a.get('id') == anuncio_id:
                # Solo el autor o superadmin puede editar
                u = _usuario_por_id(uid)
                if a.get('autor') != uid and u.get('rol') != 'superadmin':
                    return jsonify({'error': 'sin permiso'}), 403
                if 'titulo' in body:    a['titulo']    = body['titulo']
                if 'cuerpo' in body:    a['cuerpo']    = body['cuerpo']
                if 'categoria' in body: a['categoria'] = body['categoria']
                if 'fijado' in body:    a['fijado']    = bool(body['fijado'])
                if 'caduca' in body:    a['caduca']    = body['caduca'] or None
                if 'activo' in body:    a['activo']    = bool(body['activo'])
                return jsonify({'success': True})
        return jsonify({'error': 'no encontrado'}), 404

@app.route('/api/tablon/<anuncio_id>', methods=['DELETE'])
def tablon_delete(anuncio_id):
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    u = _usuario_por_id(uid)
    with editar_json(F_TABLON) as datos:
        before = len(datos.get('anuncios', []))
        datos['anuncios'] = [a for a in datos.get('anuncios', [])
                             if not (a.get('id') == anuncio_id and
                                     (a.get('autor') == uid or u.get('rol') == 'superadmin'))]
        if len(datos.get('anuncios', [])) < before:
            return jsonify({'success': True})
        return jsonify({'error': 'no encontrado o sin permiso'}), 404

@app.route('/api/tablon/<anuncio_id>/leido', methods=['POST'])
def tablon_marcar_leido(anuncio_id):
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    with editar_json(F_TABLON) as datos:
        for a in datos.get('anuncios', []):
            if a.get('id') == anuncio_id:
                if uid not in a.get('leido_por', []):
                    a.setdefault('leido_por', []).append(uid)
                return jsonify({'success': True})
    return jsonify({'error': 'no encontrado'}), 404

@app.route('/api/tablon/sin-leer', methods=['GET'])
def tablon_sin_leer():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'sinLeer': 0})
    datos = _cargar_tablon()
    hoy = datetime.now().strftime('%Y-%m-%d')
    sin_leer = sum(1 for a in datos.get('anuncios', [])
                   if a.get('activo', True)
                   and (not a.get('caduca') or a['caduca'] >= hoy)
                   and uid not in a.get('leido_por', []))
    return jsonify({'sinLeer': sin_leer})


# ══════════════════════════════════════════════
# E2: NOTIFICACIONES INTERNAS
# ══════════════════════════════════════════════

def _cargar_notificaciones():
    if not os.path.exists(F_NOTIFICACIONES):
        guardar_json(F_NOTIFICACIONES, {})
    return cargar_json(F_NOTIFICACIONES)

def _crear_notificacion(uid_destino, tipo, texto, enlace=''):
    """Crea una notificación para un usuario. Tipos: chat, minuta, tablon, vencimiento, guardia"""
    with editar_json(F_NOTIFICACIONES) as datos:
        datos.setdefault(uid_destino, [])
        nueva = {
            'id':     str(_uuid.uuid4()),
            'tipo':   tipo,
            'texto':  texto,
            'fecha':  datetime.now().strftime('%Y-%m-%dT%H:%M'),
            'leida':  False,
            'enlace': enlace
        }
        datos[uid_destino].insert(0, nueva)
        # Mantener máximo 100 notificaciones por usuario
        datos[uid_destino] = datos[uid_destino][:100]

@app.route('/api/notificaciones', methods=['GET'])
def notificaciones_get():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'notificaciones': [], 'sinLeer': 0})
    datos = _cargar_notificaciones()
    mis = datos.get(uid, [])
    sin_leer = sum(1 for n in mis if not n.get('leida'))
    return jsonify({'notificaciones': mis[:50], 'sinLeer': sin_leer})

@app.route('/api/notificaciones/leer', methods=['POST'])
def notificaciones_leer():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    body = request.get_json(force=True) or {}
    nid = body.get('id', '')
    with editar_json(F_NOTIFICACIONES) as datos:
        for n in datos.get(uid, []):
            if n.get('id') == nid:
                n['leida'] = True
                break
    return jsonify({'success': True})

@app.route('/api/notificaciones/leer-todas', methods=['POST'])
def notificaciones_leer_todas():
    uid = _uid_activo_actual()
    if not uid:
        return jsonify({'error': 'sin usuario'}), 401
    with editar_json(F_NOTIFICACIONES) as datos:
        for n in datos.get(uid, []):
            n['leida'] = True
    return jsonify({'success': True})


# ══════════════════════════════════════════════
# AUXILIOS JUDICIALES
# ══════════════════════════════════════════════
def _cargar_auxilios():
    if not os.path.exists(F_AUXILIOS):
        guardar_json(F_AUXILIOS, {'auxilios': []})
    return cargar_json(F_AUXILIOS)

@app.route('/api/auxilios', methods=['GET'])
def auxilios_get():
    datos = _cargar_auxilios()
    auxilios = datos.get('auxilios', [])
    # Filtros opcionales por query string
    fecha_desde = request.args.get('desde')
    fecha_hasta = request.args.get('hasta')
    estado      = request.args.get('estado')
    tipo        = request.args.get('tipo')
    plaza       = request.args.get('plaza')
    if fecha_desde:
        auxilios = [a for a in auxilios if a.get('fecha','') >= fecha_desde]
    if fecha_hasta:
        auxilios = [a for a in auxilios if a.get('fecha','') <= fecha_hasta]
    if estado:
        auxilios = [a for a in auxilios if a.get('estado') == estado]
    if tipo:
        auxilios = [a for a in auxilios if a.get('tipo') == tipo]
    if plaza:
        auxilios = [a for a in auxilios if a.get('plaza') == plaza]
    auxilios = sorted(auxilios, key=lambda a: (a.get('fecha',''), a.get('hora','')))
    return jsonify({'auxilios': auxilios})

@app.route('/api/auxilios', methods=['POST'])
def auxilio_crear():
    body = request.get_json(force=True) or {}
    nuevo = {
        'id':           str(_uuid.uuid4()),
        'fecha':        body.get('fecha', ''),
        'hora':         body.get('hora', ''),
        'tipo':         body.get('tipo', 'otro'),
        'tipo_nombre':  body.get('tipo_nombre', ''),
        'estado':       body.get('estado', 'pendiente'),
        'tribunal':     body.get('tribunal', ''),
        'procedimiento':body.get('procedimiento', ''),
        'plaza':        body.get('plaza', ''),
        'detalles':     body.get('detalles', ''),
        'observaciones':body.get('observaciones', ''),
        'alerta_min':   int(body.get('alerta_min', 0)),
        'creado':       datetime.now().isoformat(),
        'actualizado':  datetime.now().isoformat(),
    }
    with editar_json(F_AUXILIOS) as datos:
        datos.setdefault('auxilios', []).append(nuevo)
        hacer_backup('auxilios', datos)
    return jsonify({'success': True, 'auxilio': nuevo})

@app.route('/api/auxilios/<auxilio_id>', methods=['PUT'])
def auxilio_actualizar(auxilio_id):
    body  = request.get_json(force=True) or {}
    with editar_json(F_AUXILIOS) as datos:
        for a in datos.get('auxilios', []):
            if a.get('id') == auxilio_id:
                for k in ('fecha','hora','tipo','tipo_nombre','estado','tribunal',
                          'procedimiento','plaza','detalles','observaciones','alerta_min'):
                    if k in body:
                        a[k] = body[k]
                a['actualizado'] = datetime.now().isoformat()
                hacer_backup('auxilios', datos)
                return jsonify({'success': True, 'auxilio': a})
    return jsonify({'success': False, 'error': 'No encontrado'}), 404

@app.route('/api/auxilios/<auxilio_id>', methods=['DELETE'])
def auxilio_eliminar(auxilio_id):
    with editar_json(F_AUXILIOS) as datos:
        antes = len(datos.get('auxilios', []))
        datos['auxilios'] = [a for a in datos.get('auxilios', []) if a.get('id') != auxilio_id]
        if len(datos['auxilios']) == antes:
            return jsonify({'success': False, 'error': 'No encontrado'}), 404
    return jsonify({'success': True})

@app.route('/api/auxilios/proximos', methods=['GET'])
def auxilios_proximos():
    """Auxilios pendientes en las próximas N minutos (default 60)."""
    minutos = int(request.args.get('min', 60))
    ahora   = datetime.now()
    limite  = ahora + timedelta(minutes=minutos)
    datos   = _cargar_auxilios()
    proximos = []
    for a in datos.get('auxilios', []):
        if a.get('estado') != 'pendiente':
            continue
        try:
            dt = datetime.strptime(f"{a['fecha']} {a['hora']}", '%Y-%m-%d %H:%M')
            if ahora <= dt <= limite:
                proximos.append({**a, 'minutos_restantes': int((dt - ahora).total_seconds() // 60)})
        except (KeyError, ValueError, TypeError):
            pass
    return jsonify({'proximos': proximos})

@app.route('/api/plazas', methods=['GET'])
def plazas_get():
    """Plazas únicas extraídas de la agenda."""
    datos = cargar_json(F_AGENDA) if os.path.exists(F_AGENDA) else {}
    senalamientos = datos.get('senalamientos', [])
    plazas = sorted(set(s.get('plaza', '').strip() for s in senalamientos if s.get('plaza','').strip()))
    return jsonify({'plazas': plazas})

# ─────────────────────────────────────────────
# ARRANQUE
# ─────────────────────────────────────────────
def puerto_libre():
    s = socket.socket()
    s.bind(('', 0))
    p = s.getsockname()[1]
    s.close()
    return p

def _obtener_ip_lan():
    """Obtiene la IP de la red local (LAN) de este PC."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def abrir_navegador(url):
    _time_mod.sleep(1.5)
    # new=0 → reutiliza la ventana/pestaña existente si el navegador ya está abierto
    # (evita abrir ventana duplicada si Chrome/Edge tiene el portal en la sesión anterior)
    webbrowser.open(url, new=0)

# Fichero donde se guarda la URL del servidor para que los clientes la lean
F_SERVIDOR_URL = os.path.join(CONFIG_DIR, 'servidor_url.txt')

# ══════════════════════════════════════════════════════════════════════════════
# ASISTENTE JUDICIAL — Motor NLP + Endpoints
# ══════════════════════════════════════════════════════════════════════════════

import re

# ── Utilidades de fecha ──────────────────────────────────────────────────────

# ── Tabla de proveedores LLM (OpenAI-compatible) ─────────────────────────────

PROVEEDORES_LLM = {
    'groq': {
        'nombre':    'Groq',
        'url':       'https://api.groq.com/openai/v1',
        'key_field': 'groq_api_key',
        'modelo_def':'llama-3.1-8b-instant',
        'fallbacks': ['llama-3.1-8b-instant', 'llama3-8b-8192'],
    },
    'gemini': {
        'nombre':    'Google Gemini',
        'url':       'https://generativelanguage.googleapis.com/v1beta/openai/',
        'key_field': 'gemini_api_key',
        'modelo_def':'gemini-2.0-flash',
        'fallbacks': ['gemini-2.0-flash', 'gemini-1.5-flash'],
    },
    'openrouter': {
        'nombre':    'OpenRouter',
        'url':       'https://openrouter.ai/api/v1',
        'key_field': 'openrouter_api_key',
        # qwen3-235b (no :free en lista pero precio=0 si tiene thinking) y gpt-oss-120b:free
        # Los modelos Gemma (:free) no soportan role:system → se usa fallback sin system
        'modelo_def':'openai/gpt-oss-120b:free',
        'fallbacks': ['openai/gpt-oss-20b:free', 'qwen/qwen3-235b-a22b-thinking-2507',
                      'google/gemma-3-27b-it:free', 'meta-llama/llama-3.3-70b-instruct:free'],
    },
    'mistral': {
        'nombre':    'Mistral AI',
        'url':       'https://api.mistral.ai/v1',
        'key_field': 'mistral_api_key',
        'modelo_def':'mistral-small-latest',
        'fallbacks': ['mistral-small-latest'],
    },
    'openai': {
        'nombre':    'OpenAI',
        'url':       'https://api.openai.com/v1',
        'key_field': 'openai_api_key',
        'modelo_def':'gpt-4o-mini',
        'fallbacks': ['gpt-4o-mini'],
    },
    'cerebras': {
        'nombre':    'Cerebras',
        'url':       'https://api.cerebras.ai/v1',
        'key_field': 'cerebras_api_key',
        'modelo_def':'llama3.1-8b',
        'fallbacks': ['llama3.1-8b', 'qwen-3-235b-a22b-instruct-2507'],
    },
}

def _llm_cfg():
    """
    Lee la configuración activa del LLM.
    Devuelve (prov_id, prov_dict, api_key, modelo) o (None, None, '', '') si no hay config.
    Soporta proveedores built-in (PROVEEDORES_LLM) y custom (proveedores_custom en config).
    """
    try:
        cfg = cargar_json(F_CONFIG_LLM) or {}
        prov_id = cfg.get('proveedor', '').strip()
        # Compatibilidad con configs antiguas (solo groq_api_key sin campo 'proveedor')
        if not prov_id:
            if cfg.get('groq_api_key', '').strip():
                prov_id = 'groq'
            else:
                return None, None, '', ''
        # Buscar en built-in
        prov = PROVEEDORES_LLM.get(prov_id)
        if prov:
            key    = cfg.get(prov['key_field'], '').strip()
            modelo = cfg.get('modelo', prov['modelo_def'])
            if not key:
                return None, None, '', ''
            return prov_id, prov, key, modelo
        # Buscar en proveedores custom
        customs = cfg.get('proveedores_custom', {})
        cprov = customs.get(prov_id)
        if not cprov:
            return None, None, '', ''
        key    = cprov.get('api_key', '').strip()
        modelo = cfg.get('modelo', '') or cprov.get('modelo', '')
        if not key:
            return None, None, '', ''
        # Construir prov_dict compatible con built-in
        prov = {
            'nombre':    cprov.get('nombre', prov_id),
            'url':       cprov.get('url', ''),
            'key_field': f'{prov_id}_api_key',
            'modelo_def': cprov.get('modelo', ''),
            'fallbacks': [],
            'formato':   cprov.get('formato', 'openai'),
        }
        return prov_id, prov, key, modelo
    except Exception:
        return None, None, '', ''

def _anonimizar_senalamiento(s):
    """Elimina datos personales antes de enviar al LLM.
    El número de expediente (ej. '100/2025') es referencia de caso,
    no dato personal — se incluye para que la IA pueda citarlo."""
    return {
        'fecha':      s.get('fecha', ''),
        'hora':       s.get('hora', ''),
        'tipo':       s.get('tipo', ''),
        'expediente': s.get('expediente', ''),
        'plaza':      s.get('plaza', ''),
        'sala':       s.get('sala', ''),
        'estado': ('anulado'    if s.get('anulado')    else
                   'celebrado'  if s.get('celebrado')  else
                   'suspendido' if s.get('suspendido') else 'pendiente')
    }

_LLM_SISTEMA_BASE = (
    "Eres el asistente de un juzgado español. Responde SIEMPRE en español. "
    "Usa SOLO los datos del contexto que recibirás — no inventes nada. "
    "Si los datos están vacíos, dilo claramente. "
    "Cuando haya señalamientos, LISTA cada uno con su hora, tipo y plaza (no resumas). "
    "Formato: una línea por señalamiento, con emoji de reloj. "
    "Para preguntas de guardia, turnos o vencimientos sé conciso (máximo 6 líneas). "
    "Usa emojis con moderación."
)

# ── Glosario IA ───────────────────────────────────────────────────────────────

_glosario_cache = None  # cargado una sola vez en memoria

def _cargar_glosario():
    """Carga datos/glosario_ia.txt y lo cachea. Devuelve str o '' si no existe."""
    global _glosario_cache
    if _glosario_cache is not None:
        return _glosario_cache
    try:
        if os.path.exists(F_GLOSARIO_IA):
            with open(F_GLOSARIO_IA, 'r', encoding='utf-8') as f:
                _glosario_cache = f.read().strip()
        else:
            _glosario_cache = ''
    except Exception:
        _glosario_cache = ''
    return _glosario_cache

def _generar_glosario_si_falta():
    """
    Si glosario_ia.txt no existe, intenta extraerlo del docx oficial.
    Silencioso: no falla si el docx no está accesible.
    """
    if os.path.exists(F_GLOSARIO_IA):
        return
    docx_src = os.path.join(
        BASE_DIR, '..', 'IMPORTAR Y EXPORTAR INDIVIDUAL',
        'Glosario Oficial para Chat con IA.docx'
    )
    docx_src = os.path.normpath(docx_src)
    if not os.path.exists(docx_src):
        return
    try:
        import zipfile as _zf, re as _re
        with _zf.ZipFile(docx_src, 'r') as z:
            xml = z.read('word/document.xml').decode('utf-8')
        txt = _re.sub(r'</w:p>', '\n', xml)
        txt = _re.sub(r'<[^>]+>', '', txt)
        txt = _re.sub(r'[ \t]+', ' ', txt)
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        # Eliminar líneas consecutivas duplicadas
        dedup = []
        prev = None
        for l in lines:
            if l != prev:
                dedup.append(l)
            prev = l
        final = '\n'.join(dedup)
        with open(F_GLOSARIO_IA, 'w', encoding='utf-8') as f:
            f.write(final)
        log(f'[IA] Glosario generado desde docx: {len(final)} chars → {F_GLOSARIO_IA}')
    except Exception as ex:
        log(f'[IA] No se pudo generar glosario desde docx: {ex}')

# ── Constructor del system prompt con glosario ────────────────────────────────

# Ventana de contexto aproximada (en tokens) por modelo — para truncar el glosario
# Los modelos de 8k contexto no pueden recibir el glosario completo (33k chars ≈ 8400 tokens)
_CTX_TOKENS_MODELO = {
    # Cerebras
    'llama3.1-8b':                              8_192,   # Cerebras — contexto pequeño
    # Groq (llama-3.1-8b-instant tiene 128k aunque el nombre sugiera 8k)
    'llama3-8b-8192':                           8_192,   # Groq — contexto pequeño
    'llama-3.1-8b-instant':                   131_072,
    'llama-3.3-70b-versatile':                131_072,
    'qwen/qwen3-32b':                          32_768,
    # Gemini
    'gemini-2.0-flash':                     1_000_000,
    'gemini-2.5-flash':                     1_000_000,
    'gemini-1.5-flash':                     1_000_000,
    # OpenRouter
    'google/gemma-3-27b-it:free':             131_072,
    'google/gemma-3-12b-it:free':             131_072,
    'meta-llama/llama-3.3-70b-instruct:free': 131_072,
    'mistralai/mistral-small-3.1-24b-instruct:free': 32_768,
    # Mistral / OpenAI / Cerebras grandes
    'mistral-small-latest':                    32_768,
    'gpt-4o-mini':                            128_000,
    'qwen-3-235b-a22b-instruct-2507':          32_768,
    'gpt-oss-120b':                            32_768,
    'zai-glm-4.7':                             32_768,
}
_CTX_DEFAULT = 32_768   # si el modelo no está en la tabla, asumir 32k (conservador)

# Mapeo intención → palabras clave de las secciones del glosario
# Se usa para extraer SOLO la sección relevante en modelos con contexto pequeño
_GLOSARIO_INTENCION_KW = {
    'senalamiento_dia':    ['señalamiento', 'agenda', 'sala', 'juicio', 'vista'],
    'semana':              ['señalamiento', 'agenda', 'sala', 'juicio', 'vista'],
    'mes':                 ['señalamiento', 'agenda', 'sala', 'juicio', 'vista'],
    'crear_senalamiento':    ['señalamiento', 'agenda', 'sala', 'juicio', 'vista'],
    'anular_senalamiento':   ['señalamiento', 'anular', 'cancelar', 'suspender'],
    'marcar_celebrado':      ['señalamiento', 'celebrado', 'celebrar', 'realizado', 'visto'],
    'modificar_senalamiento':['señalamiento', 'modificar', 'cambiar', 'mover'],
    'huecos_libres':         ['señalamiento', 'agenda', 'sala', 'juicio', 'vista'],
    'conflictos':          ['señalamiento', 'agenda', 'sala', 'juicio', 'vista'],
    'guardia':             ['guardia', 'rotaci', 'diaoverride', 'turno semanal'],
    'mi_guardia':          ['guardia', 'turno', 'rotación', 'me toca'],
    'vacaciones':          ['vacaci', 'ausencia', 'permiso', 'días no laborable'],
    'vencimientos':        ['vencimiento', 'plazo', 'dies a quo', 'hábil', 'cómputo'],
    'turnos':              ['turno', 'notificajud', 'diligencia', 'notificaci', 'registro', 'scace'],
    'anotar_notificacion': ['notificaci', 'turno', 'diligencia', 'acto de comunicaci'],
    'insacular_perito':    ['perito', 'insaculación', 'selección', 'especialidad', 'sorteo'],
    'peritos':             ['perito', 'tasador', 'especialidad', 'informe pericial'],
    'presos':              ['preso', 'interno', 'penitenciario', 'recluso', 'preventivo', 'penado'],
    'auxilios':            ['auxilio', 'videoconferencia', 'exhorto', 'videoconfer'],
    'estadisticas':        ['bolet', 'estadíst', 'trimestral', 'boletín'],
    'instruccion_penal':   ['instrucción', 'instruccion', 'prórroga', 'prorroga', 'diligencias previas', 'plazo instruc'],
    'correos':             ['correo', 'envío postal', 'carta', 'remesa', 'lote', 'postal'],
    'ausencias_plazas':    ['ausencia', 'plaza', 'magistrad', 'letrad', 'sustitut', 'cargo ausent'],
    'modelos_ia':          ['groq', 'cerebras', 'mistral', 'openrouter', 'llm', 'modelo ia'],
    'buscar_expediente':   ['expediente', 'procedimiento', 'tipo procedimiento'],
    'clipbox':             ['modelo', 'plantilla', 'clipbox', 'copiar', 'texto predefinido', 'formulario'],
    'minutas':             ['minuta', 'acta', 'resolución', 'notificación postal', 'minuta judicial'],
    'archivo':             ['archivo', 'expediente archivo', 'solicitud archivo', 'desarchiv', 'archivar'],
    'ayuda':               ['ayuda', 'help', 'qué puedes hacer', 'comandos', 'funciones', 'cómo funciona'],
    'navegar':             [],   # genérico, usar cabecera
    'asignar_guardia':     ['guardia', 'asignar', 'turno', 'rotación', 'poner guardia'],
    'quitar_guardia':      ['guardia', 'quitar', 'eliminar', 'vaciar'],
    'intercambiar_guardia':['guardia', 'intercambiar', 'permutar', 'canjear', 'swap'],
    'crear_ausencia':      ['ausencia', 'registrar', 'crear', 'plaza', 'magistrad', 'letrad'],
    'cancelar_ausencia':   ['ausencia', 'cancelar', 'quitar', 'eliminar', 'anular'],
    'historial_ausencias': ['ausencia', 'historial', 'histórico', 'pasadas', 'anteriores'],
    'buscar_dir3':         ['dir3', 'directorio común', 'código organismo', 'unidad', 'oficina'],
    'resumen_semanal':     ['resumen', 'semana', 'semanal', 'panorama', 'briefing'],
    'publicar_tablon':     ['tablón', 'aviso', 'anuncio', 'publicar', 'colgar'],
    'consultar_tablon':    ['tablón', 'aviso', 'anuncio', 'recientes'],
    'buscar_tablon':       ['tablón', 'buscar', 'aviso'],
    'ver_notificaciones':  ['notificación', 'pendiente', 'campanita', 'sin leer'],
}

def _glosario_para_intencion(intencion='', modelo=''):
    """
    Devuelve la porción del glosario más relevante para la intención dada.
    Estrategia:
      - Si el glosario completo cabe en el contexto del modelo → devolverlo íntegro.
      - Si no cabe → extraer la sección más relevante + cabecera general.
    Así modelos de 8k siempre reciben la sección del módulo correcto,
    no solo los primeros N chars del glosario completo.
    """
    glosario = _cargar_glosario()
    if not glosario:
        return ''

    ctx       = _CTX_TOKENS_MODELO.get(modelo, _CTX_DEFAULT)
    max_chars = max(500, (ctx - 2800) * 3)   # 3 chars/token, reservar 2800 tokens

    # Si cabe completo, devolver completo
    if len(glosario) <= max_chars:
        return glosario

    lines = glosario.splitlines()

    # ── Extraer cabecera (líneas previas a la primera sección "2.X …") ──────
    header_lines = []
    sec_inicio   = 0
    for i, line in enumerate(lines):
        if re.match(r'^\s*2\.\d+', line) and i > 2:
            sec_inicio = i
            break
        header_lines.append(line)
    # Limitar cabecera a 30 líneas para no gastar demasiado contexto
    header = '\n'.join(header_lines[:30])

    # ── Dividir el glosario en secciones "2.X …" ────────────────────────────
    secciones = []     # lista de strings, una por sección
    sec_actual = []
    for i in range(sec_inicio, len(lines)):
        line = lines[i]
        if re.match(r'^\s*2\.\d+', line) and sec_actual:
            secciones.append('\n'.join(sec_actual))
            sec_actual = [line]
        else:
            sec_actual.append(line)
    if sec_actual:
        secciones.append('\n'.join(sec_actual))

    keywords = _GLOSARIO_INTENCION_KW.get(intencion, [])

    # ── Puntuar secciones por relevancia ────────────────────────────────────
    def _score(sec_txt):
        txt_low = sec_txt.lower()
        return sum(txt_low.count(kw.lower()) for kw in keywords)

    if keywords:
        secciones_ord = sorted(secciones, key=_score, reverse=True)
    else:
        secciones_ord = secciones   # sin keywords: orden original

    # ── Construir resultado: cabecera + sección más relevante + resto si hay hueco ──
    resultado = header
    espacio   = max_chars - len(resultado) - 4   # 4 chars para separadores

    for sec in secciones_ord:
        if espacio <= 100:
            break
        bloque = '\n\n' + sec
        if len(bloque) <= espacio:
            resultado += bloque
            espacio   -= len(bloque)
        else:
            # Añadir lo que quepa (cortando por línea completa)
            recortado = bloque[:espacio]
            ultimo_nl = recortado.rfind('\n')
            if ultimo_nl > espacio // 2:
                recortado = recortado[:ultimo_nl]
            resultado += recortado + '\n...[sección truncada]'
            break

    return resultado

def _llm_sistema(modelo='', intencion=''):
    """
    Devuelve el prompt de sistema con la sección del glosario relevante inyectada.
    Para modelos con contexto pequeño (8k) solo incluye la sección del módulo
    que corresponde a la intención, no el glosario completo.
    """
    glosario = _glosario_para_intencion(intencion, modelo)
    if not glosario:
        return _LLM_SISTEMA_BASE
    return _LLM_SISTEMA_BASE + "\n\n=== GLOSARIO DEL PORTAL ===\n" + glosario + "\n"

def _http_post_json(url, headers, payload, timeout=12):
    """
    POST JSON a url usando urllib.request (stdlib — sin dependencias externas).
    Devuelve (status_code:int, response_dict:dict).
    Lanza Exception en caso de error de red/timeout.
    """
    import urllib.request as _ureq
    import urllib.error   as _uerr
    body = json.dumps(payload).encode('utf-8')
    req  = _ureq.Request(url, data=body, headers=headers, method='POST')
    try:
        with _ureq.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except _uerr.HTTPError as e:
        try:
            rj = json.loads(e.read().decode('utf-8'))
        except Exception:
            rj = {'error': {'message': str(e), 'code': e.code}}
        return e.code, rj

def _llamar_llm(contexto_txt, pregunta, intencion='', modo_combinado=False):
    """
    Llama al proveedor LLM configurado via API OpenAI-compatible o Anthropic (urllib stdlib).
    Compatible con: Groq, Google Gemini, OpenRouter, Mistral, OpenAI, Cerebras, Anthropic, custom.
    Devuelve (texto, None) si OK, o (None, error_str) si falla.
    En caso de rate-limit (429) prueba los fallbacks del proveedor.
    intencion: se usa para seleccionar la sección del glosario más relevante.
    modo_combinado: si True, añade instrucción de preservar formato al system prompt.
    """
    prov_id, prov, key, modelo = _llm_cfg()
    if not prov:
        return None, 'sin_clave'

    sistema  = _llm_sistema(modelo, intencion)   # inyecta solo la sección del glosario relevante
    if modo_combinado:
        sistema += ("\n\nIMPORTANTE: El contexto ya contiene datos formateados del motor de reglas. "
                    "Reproduce TODOS los datos tal cual (no omitas ninguno). "
                    "Puedes añadir una breve intro en lenguaje natural antes de los datos.")
    msg_user = f"Pregunta: {pregunta}\n\nDatos del juzgado:\n{contexto_txt}"

    # ── Formato Anthropic (/v1/messages) ──────────────────────────────────────
    if prov.get('formato') == 'anthropic':
        url = prov['url'].rstrip('/') + '/messages'
        headers = {
            "x-api-key":         key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        }
        payload = {
            "model":      modelo,
            "max_tokens": 400,
            "system":     sistema,
            "messages":   [{"role": "user", "content": msg_user}],
        }
        nom = prov['nombre']
        try:
            status, rj = _http_post_json(url, headers, payload, timeout=15)
            if status == 200:
                txt = rj.get('content', [{}])[0].get('text', '')
                return txt.strip() or None, None
            log(f'[LLM/{nom}] Error Anthropic {status}: {rj}')
            return None, f'error de conexión con {nom} ({status})'
        except Exception as e:
            log(f'[LLM/{nom}] Excepción Anthropic: {e}')
            return None, f'error de conexión con {nom}'

    # ── Formato OpenAI-compatible (/chat/completions) ─────────────────────────
    mensajes = [
        {"role": "system", "content": sistema},
        {"role": "user",   "content": msg_user}
    ]
    payload = {"model": modelo, "messages": mensajes,
               "temperature": 0.3, "max_tokens": 400, "top_p": 0.95}

    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json",
               "User-Agent": "python-requests/2.31.0"}   # evita bloqueo Cloudflare en Cerebras y otros
    if prov_id == 'openrouter':
        headers['HTTP-Referer'] = 'http://localhost'
        headers['X-Title']      = 'Portal Judicial'

    url = prov['url'].rstrip('/') + '/chat/completions'
    nom = prov['nombre']

    def _es_rate_limit(status, rj):
        if status == 429:
            return True
        msg = str(rj).lower()
        return 'rate_limit' in msg or 'rate limit' in msg or 'quota' in msg or 'too many' in msg

    def _no_soporta_system(status, rj):
        """Algunos modelos (Gemma, etc.) no aceptan role:system → reintentar sin él."""
        if status != 400:
            return False
        msg = str(rj).lower()
        return ('instruction' in msg or 'system' in msg or 'developer' in msg
                or 'system_prompt' in msg or 'role' in msg)

    def _limpiar(t):
        t = re.sub(r'<think>.*?</think>', '', t or '', flags=re.DOTALL).strip()
        return t or None

    def _llamar_modelo(mdl):
        return _http_post_json(url, headers, {**payload, 'model': mdl})

    def _llamar_modelo_sin_system(mdl):
        """Fusiona el system prompt en el mensaje de usuario (para modelos que no aceptan role:system)."""
        sys_txt = sistema[:600]   # resumen del sistema para no inflar el contexto
        msgs_fusionados = [
            {'role': 'user', 'content':
                f"[Instrucciones: {sys_txt}]\n\n{mensajes[-1]['content']}"}
        ]
        return _http_post_json(url, headers, {**payload, 'model': mdl, 'messages': msgs_fusionados})

    # ── 1. Modelo configurado ─────────────────────────────────────────────────
    _usar_fallbacks = False
    try:
        status, rj = _llamar_modelo(modelo)
        if status == 200:
            return _limpiar(rj['choices'][0]['message']['content']), None
        if _es_rate_limit(status, rj):
            log(f'[LLM/{nom}] Rate-limit en {modelo}, probando fallback...')
            _usar_fallbacks = True
        elif _no_soporta_system(status, rj):
            log(f'[LLM/{nom}] Modelo {modelo} no soporta system role, reintentando sin él...')
            try:
                status2, rj2 = _llamar_modelo_sin_system(modelo)
                if status2 == 200:
                    log(f'[LLM/{nom}] Reintento sin system OK para {modelo}')
                    return _limpiar(rj2['choices'][0]['message']['content']), None
            except Exception as e2:
                log(f'[LLM/{nom}] Excepción en reintento sin system: {e2}')
            _usar_fallbacks = True
        else:
            log(f'[LLM/{nom}] Error {status} en {modelo}: {rj}')
            _usar_fallbacks = True
    except Exception as e:
        log(f'[LLM/{nom}] Excepción en {modelo}: {e}, probando fallback...')
        _usar_fallbacks = True

    # ── 2. Fallbacks ──────────────────────────────────────────────────────────
    if not _usar_fallbacks:
        return None, f'error de conexión con {nom}'
    for fb in prov.get('fallbacks', []):
        if fb == modelo:
            continue
        try:
            status, rj = _llamar_modelo(fb)
            if status == 200:
                log(f'[LLM/{nom}] Fallback OK con {fb}')
                return _limpiar(rj['choices'][0]['message']['content']), None
            if _es_rate_limit(status, rj):
                log(f'[LLM/{nom}] Rate-limit en fallback {fb}')
                continue
            if _no_soporta_system(status, rj):
                log(f'[LLM/{nom}] Fallback {fb} no soporta system, reintentando sin él...')
                try:
                    status2, rj2 = _llamar_modelo_sin_system(fb)
                    if status2 == 200:
                        return _limpiar(rj2['choices'][0]['message']['content']), None
                except Exception:
                    pass
            log(f'[LLM/{nom}] Error en fallback {fb}: {rj}')
            break
        except Exception as e:
            log(f'[LLM/{nom}] Excepción en fallback {fb}: {e}')
            break

    return None, f'límite diario de {nom} alcanzado — reintenta en ~1h'

# ─────────────────────────────────────────────────────────────────────────────

_DIAS_ES = {
    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
    'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
}
_MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12
}

def _extraer_fecha(texto, hoy=None):
    """Extrae una fecha del texto en español. Devuelve str YYYY-MM-DD o None."""
    if hoy is None:
        hoy = date.today()
    t = texto.lower()

    # hoy / mañana / pasado mañana
    if re.search(r'\bhoy\b', t):      return hoy.isoformat()
    if re.search(r'\bma[ñn]ana\b', t): return (hoy + timedelta(1)).isoformat()
    if re.search(r'\bpasado ma[ñn]ana\b', t): return (hoy + timedelta(2)).isoformat()

    # ayer
    if re.search(r'\bayer\b', t):     return (hoy - timedelta(1)).isoformat()

    # ► DD [de] MES [de YYYY] → PRIORIDAD sobre "día de semana"
    # "el martes 3 de marzo" → 2026-03-03, no "próximo martes"
    # También acepta "1 enero 2026" sin "de"
    m = re.search(r'\b(\d{1,2})\s+(?:de\s+)?(' + '|'.join(_MESES_ES) + r')(?:\s+(?:de\s+)?(\d{4}))?\b', t)
    if m:
        d_num, mes_str, yr = int(m.group(1)), m.group(2), m.group(3)
        year = int(yr) if yr else hoy.year
        try:
            return date(year, _MESES_ES[mes_str], d_num).isoformat()
        except ValueError:
            pass

    # "el lunes/martes/..." → próximo día de la semana (solo si no hay "N de mes")
    m = re.search(r'\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b', t)
    if m:
        dow_target = _DIAS_ES[m.group(1)]
        delta = (dow_target - hoy.weekday()) % 7
        if delta == 0: delta = 7  # "el lunes" = próximo, no hoy si hoy es lunes
        return (hoy + timedelta(delta)).isoformat()

    # "esta semana" → devuelve inicio de semana (lunes)
    if re.search(r'\besta semana\b', t):
        lunes = hoy - timedelta(hoy.weekday())
        return lunes.isoformat()

    # "la semana que viene" / "próxima semana"
    if re.search(r'\bpr[oó]xima semana\b|\bsemana que viene\b|\bla semana siguiente\b', t):
        lunes = hoy - timedelta(hoy.weekday()) + timedelta(7)
        return lunes.isoformat()

    # "este mes"
    if re.search(r'\beste mes\b', t):
        return date(hoy.year, hoy.month, 1).isoformat()

    # DD/MM[/YYYY]  —  ANTES de "día N" para que "día 1/01/2026" no se confunda
    m = re.search(r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b', t)
    if m:
        d_num, mo, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(yr) if yr else hoy.year
        if year < 100: year += 2000
        try:
            return date(year, mo, d_num).isoformat()
        except ValueError:
            pass

    # "día 3" / "dia 3" / "el día 3" / "el dia 3" → día N del mes actual (siguiente si ya pasó)
    # También captura: "para el día 3", "señalamientos día 3"
    # Lookahead negativo (?![/\-]) evita capturar "día 1/01" como "día 1"
    m = re.search(r'\b(?:el\s+)?d[ií]a\s+(\d{1,2})\b(?![/\-])', t)
    if not m:
        # "para el 3" como atajo de fecha (solo con "para el" para evitar falsos positivos)
        m = re.search(r'\bpara el\s+(\d{1,2})\b(?![/\-])', t)
    if m:
        day_num = int(m.group(1))
        if 1 <= day_num <= 31:
            try:
                d = date(hoy.year, hoy.month, day_num)
                if d < hoy:
                    # Ya pasó ese día este mes → ir al mes siguiente
                    next_mo = hoy.month + 1
                    next_yr = hoy.year + (1 if next_mo > 12 else 0)
                    next_mo = ((next_mo - 1) % 12) + 1
                    d = date(next_yr, next_mo, day_num)
                return d.isoformat()
            except ValueError:
                pass  # día inválido para ese mes (ej: 31 en febrero)

    return None

def _extraer_semana(texto, hoy=None):
    """Devuelve (fecha_inicio, fecha_fin) de semana mencionada, o None."""
    if hoy is None:
        hoy = date.today()
    t = texto.lower()
    if re.search(r'\besta semana\b', t):
        lunes = hoy - timedelta(hoy.weekday())
        return lunes, lunes + timedelta(6)
    if re.search(r'\bpr[oó]xima semana\b|\bsemana que viene\b', t):
        lunes = hoy - timedelta(hoy.weekday()) + timedelta(7)
        return lunes, lunes + timedelta(6)
    if re.search(r'\bsemana del\b', t):
        f = _extraer_fecha(texto, hoy)
        if f:
            fd = date.fromisoformat(f)
            lunes = fd - timedelta(fd.weekday())
            return lunes, lunes + timedelta(6)
    return None

def _extraer_mes(texto, hoy=None):
    """Devuelve (año, mes) si se menciona un mes, o None."""
    if hoy is None:
        hoy = date.today()
    t = texto.lower()
    if re.search(r'\beste mes\b', t):
        return hoy.year, hoy.month
    if re.search(r'\bel mes que viene\b|\bpr[oó]ximo mes\b', t):
        nxt = date(hoy.year, hoy.month, 1) + timedelta(32)
        return nxt.year, nxt.month
    m = re.search(r'\b(' + '|'.join(_MESES_ES) + r')(?:\s+(?:de\s+)?(\d{4}))?\b', t)
    if m:
        mes = _MESES_ES[m.group(1)]
        year = int(m.group(2)) if m.group(2) else hoy.year
        return year, mes
    return None

def _extraer_plaza(texto, plazas_disponibles=None):
    """Extrae el número/nombre de plaza del texto."""
    t = texto.lower()
    # Plaza N
    m = re.search(r'plaza\s+(\d+)', t)
    if m:
        n = int(m.group(1))
        if plazas_disponibles:
            for p in plazas_disponibles:
                if re.search(rf'\bplaza\s*{n}\b', p.lower()):
                    return p
        return f'Plaza {n}'
    # "la primera/segunda/tercera plaza"
    ordinal_map = {'primera': 1, 'segunda': 2, 'tercera': 3, 'cuarta': 4}
    for pal, num in ordinal_map.items():
        if pal in t:
            if plazas_disponibles:
                for p in plazas_disponibles:
                    if re.search(rf'\bplaza\s*{num}\b', p.lower()):
                        return p
            return f'Plaza {num}'
    return None

def _extraer_expediente(texto):
    """Detecta un número de expediente tipo 123/2025.
    Usa lookbehind negativo para no confundir con fechas DD/MM/YYYY."""
    m = re.search(r'(?<!/)\b(\d+/\d{4})\b', texto)
    return m.group(1) if m else None

def _extraer_hora(texto):
    """Extrae hora del texto. Devuelve 'HH:MM' o None."""
    t = texto.lower()
    m = re.search(r'\b(\d{1,2})[:\.](\d{2})\b', t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    m = re.search(r'\ba las?\s+(\d{1,2})\b', t)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"
    return None

_PATRON_MESES = '|'.join(_MESES_ES.keys())

def _extraer_tipo(texto, tipos_disponibles=None):
    """Extrae el tipo/clase de procedimiento del texto (ej: X53, LEVE, JO, DP...)."""
    t_up = texto.upper()
    # 1. Buscar primero en los tipos existentes en la agenda (word boundary, no subcadenas)
    if tipos_disponibles:
        for tipo in sorted(tipos_disponibles, key=len, reverse=True):
            if tipo and re.search(r'\b' + re.escape(tipo.upper()) + r'\b', t_up):
                return tipo
    # 2. Códigos cortos alfanuméricos tipo X53, B12, DPA, EJ, JO, JP...
    m = re.search(r'\b([A-ZÁÉÍÓÚÑ]{1,4}\d{1,3}|[A-ZÁÉÍÓÚÑ]{2,5})\b', texto)
    if m:
        candidato = m.group(1).upper()
        # Evitar palabras genéricas
        excluir = {'PLAZA', 'HORAS', 'LIBRE', 'LUNES', 'PARA', 'AGENDA', 'TODOS', 'TIPO',
                   'MARZO', 'MAYO', 'ABRIL', 'JUNIO', 'JULIO', 'HOY', 'MES', 'AÑO', 'DIA',
                   'SEMANA', 'TODO', 'LOS', 'LAS', 'QUE', 'HAY', 'DEL', 'EN', 'DE', 'LA',
                   'EL', 'UNA', 'UN', 'CON', 'POR', 'SIN', 'QUE', 'NO', 'SI', 'AL', 'SE',
                   'CREA', 'CREAR', 'NUEVO', 'NUEVA', 'ANULA', 'ANULAR', 'CAMBIA', 'MUEVE',
                   'SUSPENDE', 'SUSPENDER', 'CANCELA', 'CANCELAR', 'MODIFICA', 'MODIFICAR',
                   'CELEBRA', 'CELEBRADO', 'CELEBRAR', 'MARCA', 'MARCAR', 'REALIZADO',
                   'BORRA', 'BORRAR', 'ELIMINA', 'ELIMINAR', 'QUITA', 'QUITAR',
                   'SELECCIONA', 'SELECCIONAR', 'ASIGNA', 'ASIGNAR', 'INSACULA',
                   'SORTEA', 'DESIGNA', 'NECESITO', 'PERITO'}
        meses_up = {m.upper() for m in _MESES_ES.keys()}
        if candidato not in excluir and candidato not in meses_up and len(candidato) >= 2:
            return candidato
    return None

def _detectar_intencion(texto):
    """Clasifica la intención de la pregunta en una de las categorías."""
    t = texto.lower()
    # ── AYUDA / HELP (prioridad máxima) ─────────────────────────────────────
    if re.search(
        r'\bayuda\b|\bhelp\b|\bqu[eé] puedes hacer\b|\bqu[eé] sabes\b|'
        r'\bc[oó]mo funciona[s]?\b|\bqu[eé] comandos\b|\bqu[eé] funciones\b|'
        r'\bc[oó]mo te uso\b|\bc[oó]mo te pregunto\b|\bqu[eé] m[oó]dulos\b|'
        r'\bno entiendo\b|\bc[oó]mo va esto\b|\bqu[eé] hago\b|'
        r'\bexpl[ií]came\b|\benseñ[aá]me\b|\bqu[eé] opciones\b', t):
        return 'ayuda'

    # ── RESUMEN DEL DÍA / BRIEFING MATINAL ───────────────────────────────────
    if re.search(
        r'\bresumen\b.*\bd[ií]a\b|\bresumen\b.*\bhoy\b|\bbriefing\b|'
        r'\bbuenos? d[ií]as?\b|\bbuen d[ií]a\b|\bqu[eé] tengo hoy\b|\bqu[eé] hay hoy\b|'
        r'\bresumen diario\b|\bpanorama\b.*\bhoy\b|\bqu[eé] me espera\b|'
        r'\bc[oó]mo est[aá] el d[ií]a\b|\bqu[eé] toca hoy\b|'
        r'\ba ver qu[eé] hay\b|\bempezamos\b|\bdame un resumen\b|'
        r'\bresumen r[aá]pido\b|\bresumen matinal\b|\bbuenas?\b$|'
        r'\bc[oó]mo viene el d[ií]a\b|\bqu[eé] tenemos hoy\b|'
        r'\bqu[eé] nos espera hoy\b|\barrancar el d[ií]a\b', t):
        return 'resumen_dia'

    # ── RESUMEN SEMANAL (antes de clipbox para que "resumen de la semana" no caiga en otro) ─
    if re.search(
        r'\bresumen\b.*\bsemana\b|\bresumen semanal\b|\bc[oó]mo viene la semana\b|'
        r'\bqu[eé] tenemos esta semana\b|\bqu[eé] hay esta semana\b|'
        r'\bpanorama.*semana\b|\bbriefing semanal\b|'
        r'\bqu[eé] nos espera esta semana\b|\bla semana\b.*\bresumen\b|'
        r'\bresumen\b.*\bpr[oó]xima semana\b', t):
        return 'resumen_semanal'

    # ── CLIPBOX / MODELOS / PLANTILLAS ────────────────────────────────────────
    if re.search(
        r'\bclipbox\b|\bplantilla[s]?\b|\bmodelo[s]? de texto\b|'
        r'\btexto[s]? predefinido[s]?\b|\bformulario[s]? predefinido[s]?\b|'
        r'\bmodelo[s]? de documento\b|\bcopiar modelo\b|'
        r'\bmodelo[s]? de providencia\b|\bmodelo[s]? de auto\b|'
        r'\btextos guardados\b|\btextos del juzgado\b', t) \
       and not re.search(r'\bmodelo[s]?\s*(de\s+)?ia\b|\bllm\b|\bgroq\b', t):
        return 'clipbox'

    # ── BOLETÍN TRIMESTRAL ────────────────────────────────────────────────────
    if re.search(
        r'\bbolet[ií]n\b|\btrimestral\b|\binforme trimestral\b|'
        r'\bestad[ií]sticas? trimestral\b|\bdatos del trimestre\b|'
        r'\basuntos ingresados\b|\basuntos resueltos\b|'
        r'\bdatos del bolet[ií]n\b|\bbolet[ií]n estad[ií]stic', t) \
       and not re.search(r'\bmodelo[s]?\s*(de\s+)?ia\b', t):
        return 'boletin'

    # ── MINUTAS JUDICIALES ────────────────────────────────────────────────────
    if re.search(
        r'\bminuta[s]?\b|\bacta[s]? de notificaci[oó]n\b|'
        r'\bminuta judicial\b|\bminuta[s]? de\b|'
        r'\b[uú]ltima minuta\b', t):
        return 'minutas'

    # ── TURNOS (antes que guardia para evitar colisión) ───────────────────────
    if re.search(
        r'\bturno[s]?\b|\bservicios.*hoy\b|\bqui[eé]n.*notifica\b|'
        r'\bnotificacion.*hoy\b|\bqui[eé]n.*hace.*vistas\b|\bqui[eé]n.*cubre\b|'
        r'\bservicio de turno|\bqui[eé]n.*est[aá] en turno|'
        r'\bqui[eé]n.*toca.*hoy\b|\breparto de turnos\b|'
        r'\ba qui[eé]n le toca hoy\b|\bqui[eé]n hace.*hoy\b', t):
        return 'turnos'

    # ── REGISTRO DE DILIGENCIAS (consulta, antes de anotar) ───────────────────
    if re.search(
        r'\bdiligencias?\b.*\bpendiente|\bdiligencias?\b.*\bplanificad|'
        r'\bregistro\b.*\bdiligencia|\bdiligencias?\b.*\bregistrad|'
        r'\bver diligencia|\bconsultar diligencia|\bdiligencias del d[ií]a\b|'
        r'\bdiligencias hoy\b|\bestado.*diligencia|'
        r'\bcu[aá]ntas diligencias\b|\bdiligencias que faltan\b|'
        r'\bdiligencias sin hacer\b|\bdiligencias realizad', t) \
       and not re.search(r'\banotar\b|\bregistrar\b', t):
        return 'registro_diligencias'

    # ── ANOTAR / REGISTRAR NOTIFICACIÓN ───────────────────────────────────────
    if re.search(
        r'\banotar\b|\bregistrar.*notificaci|\bnotifico\b|\bnotificar\b|'
        r'\bnotificaci.*positiva\b|\bnotificaci.*negativa\b|'
        r'\banotar.*positiva\b|\banotar.*negativa\b|\bsalida.*notific|'
        r'\bhe notificado\b|\bacabo de notificar\b|\bnotificaci[oó]n hecha\b', t):
        return 'anotar_notificacion'

    # ── INSACULAR / SELECCIONAR PERITO (acción) ───────────────────────────────
    if re.search(
        r'\bselecciona[r]?\b.*perito|\basigna[r]?\b.*perito|\binsacula[r]?\b|'
        r'\bsortea[r]?\b.*perito|\bnecesito\b.*perito|\bdesigna[r]?\b.*perito|'
        r'\bperito.*\bselecciona|\bperito.*\basigna|\bperito.*\bsortea|'
        r'\bdame un perito\b|\bbusca.*perito.*para\b|\bnombrar perito\b|'
        r'\belige.*perito\b|\bperito.*aleatorio\b|\bperito.*sorteo\b', t):
        return 'insacular_perito'

    # ── PERITOS / TASADORES / ESPECIALISTAS ───────────────────────────────────
    if re.search(
        r'\bperito[s]?\b|\btasador(?:es)?\b|\bforense[s]?\b|\bpericial\b|'
        r'\barquitecto[s]?\b|\bingeniero[s]?\b|\bpsic[oó]logo[s]?\b|'
        r'\bm[eé]dico[s]? forense[s]?\b|\bvalorador[es]?\b|\btasaci[oó]n\b|'
        r'\binforme pericial\b|\bpericiales?\b|\bexperto[s]? judicial[es]?\b|'
        r'\bespecialista[s]?\b.*\bjudicial\b|\blistado? de perito\b', t):
        return 'peritos'

    # ── PRESOS / INTERNOS / RECLUSOS ──────────────────────────────────────────
    if re.search(
        r'\bpreso[s]?\b|\binterno[s]?\b|\brecluso[s]?\b|\bpenado[s]?\b|'
        r'\bpreventivo[s]?\b|\bprisi[oó]n\b|\bpenitenciari|\bipencat\b|'
        r'\bcontrol de presos\b|\bc[aá]rcel\b|\bcentro penitenciario\b|'
        r'\blibertad condicional\b|\btercer grado\b|\bcondena[s]?\b.*\bpreso|'
        r'\bsituaci[oó]n penitenciaria\b', t):
        return 'presos'

    # ── SOLICITUDES DE ARCHIVO ────────────────────────────────────────────────
    if re.search(
        r'\barchivo\b.*\bexpediente|\bexpediente\b.*\barchivo|'
        r'\bsolicitud\b.*\barchivo|\bdesarchiv|\barchivar\b|'
        r'\bpedir\b.*\bexpediente.*\barchivo|\bsacar del archivo\b|'
        r'\bexpediente archivado\b', t):
        return 'archivo'

    # ── CREAR AUXILIO / VIDEOCONFERENCIA (antes de consulta genérica) ─────────
    if re.search(
        r'\bcrear?\b.*\baux[ií]lio|\bnuev[oa]?\b.*\baux[ií]lio|\ba[ñn]adir\b.*\baux[ií]lio|'
        r'\bcrear?\b.*\bvideoconferencia|\bnueva?\b.*\bvideoconferencia|'
        r'\bprogramar\b.*\bvideoconferencia|\bregistrar\b.*\baux[ií]lio|'
        r'\bcrear?\b.*\bexhorto|\bnuevo?\b.*\bexhorto|\ba[ñn]adir\b.*\bexhorto|'
        r'\bfijar\b.*\bvideoconferencia|\bmeter\b.*\bvideoconferencia|'
        r'\bponer\b.*\bvideoconferencia|\bponer\b.*\bvc\b|'
        r'\bcrear?\b.*\bcomisi[oó]n rogatoria', t):
        return 'crear_auxilio'

    # ── AUXILIOS JUDICIALES ───────────────────────────────────────────────────
    if re.search(
        r'\baux[ií]lio[s]?\b|\bvideoconferencia[s]?\b|\bexhorto[s]?\b|'
        r'\bvc\b.*\bpendiente|\btengo.*\bvc\b|\bhay.*\bvc\b|'
        r'\bcomisi[oó]n rogatoria\b|\bcooperaci[oó]n judicial\b', t) \
       and not re.search(r'\bse[ñn]alamiento\b', t):
        return 'auxilios'

    # ── CREAR / REGISTRAR AUSENCIA (acción — antes de consulta) ─────────────────
    if re.search(
        r'\bregistra[r]?\b.*\bausencia|\bcrea[r]?\b.*\bausencia|\ba[ñn]ade\b.*\bausencia|'
        r'\ba[ñn]adir\b.*\bausencia|\bpone[r]?\b.*\bausencia|\bnueva?\b.*\bausencia|'
        r'\banotar\b.*\bausencia|\bmeter\b.*\bausencia|'
        r'\bregistrar que\b.*\bausent|\bregistrar que\b.*\bfalta', t):
        return 'crear_ausencia'

    # ── CANCELAR / QUITAR AUSENCIA ───────────────────────────────────────────────
    if re.search(
        r'\bcancela[r]?\b.*\bausencia|\bquita[r]?\b.*\bausencia|\belimina[r]?\b.*\bausencia|'
        r'\bborra[r]?\b.*\bausencia|\banula[r]?\b.*\bausencia|'
        r'\bausencia\b.*\bcancela|\bausencia\b.*\bquita|\bausencia\b.*\belimina', t):
        return 'cancelar_ausencia'

    # ── HISTORIAL DE AUSENCIAS ───────────────────────────────────────────────────
    if re.search(
        r'\bhistorial\b.*\bausencia|\bhistor[ií]c[oa]\b.*\bausencia|'
        r'\bausencia[s]?\b.*\bhistorial|\bausencia[s]?\b.*\bpasad[oa]s|'
        r'\bausencia[s]?\b.*\banter|'
        r'\btodas las ausencias\b|\bausencias? de\b.*\b\d{4}\b', t):
        return 'historial_ausencias'

    # ── AUSENCIAS DE PLAZAS (magistrados, letrados, cargos) ───────────────────
    if re.search(
        r'\bausencia.*plaza|\bplaza.*ausent|\bmagistrad.*ausent|\bletrad.*ausent|'
        r'\bsustitut|\bcargo.*ausent|\bqui[eé]n sustit|\bausencias activas\b|'
        r'\bausencias hoy\b|\bplazas?\s+sin\b|\bausencias?\s+de\s+plazas?|'
        r'\bqu[eé] juez falta\b|\bqui[eé]n falta.*plaza\b|'
        r'\bmagistrad.*falta\b|\bletrad.*falta\b|'
        r'\bsustituciones?\b|\breemplaz', t) \
       and not re.search(r'\bvacaciones\b', t):
        return 'ausencias_plazas'

    # ── VACACIONES / AUSENCIAS DE PERSONAL ────────────────────────────────────
    if re.search(
        r'\bvacaciones?\b|\bausencias?\b|\basuntos propios\b|'
        r'\bincapacidad temporal\b|\bincapacidad\b|\bpermisos?\b|'
        r'\bqui[eé]n no viene\b|\bqui[eé]n est[aá] de baja\b|'
        r'\bde baja\b|\b[ií]\.?t\.?\b|\bd[ií]as? de asuntos\b|'
        r'\bqui[eé]n falta\b|\bd[ií]as? libres?\b.*\bpersonal', t) \
       and not re.search(r'\bse[ñn]alamiento\b|\bhueco\b|\bhora libre\b', t):
        return 'vacaciones'

    # ── INSTRUCCIÓN PENAL / PRÓRROGAS ─────────────────────────────────────────
    if re.search(
        r'\binstrucci[oó]n\b|\binstruccion\b|\bpl[aá]zo[s]? de instrucci|\b'
        r'pr[oó]rroga[s]?\b|\bprorrogar\b|\bampliar.*plazo\b|'
        r'\bperiodo[s]? de instrucci|\bfecha.*vencimiento.*instrucci|'
        r'\bdiligencias previas\b|\bdiligi.*previa\b|'
        r'\bplazo.*investigaci[oó]n\b|\binvestigaci[oó]n.*penal\b', t):
        return 'instruccion_penal'

    # ── CORREOS / ENVÍOS POSTALES ─────────────────────────────────────────────
    if re.search(
        r'\bcorreo[s]?\b|\benv[ií]o[s]? postal[es]?\b|\benvios postales\b|'
        r'\bcarta[s]?\b|\bremesa[s]?\b|\blote[s]? de env[ií]o[s]?\b|'
        r'\bregistro postal\b|\benv[ií]o[s]? de correo\b|\bnotificaci[oó]n postal\b|'
        r'\bcorreo certificado\b|\bcorreos pendientes\b|\bfichero de correos\b|'
        r'\bgenerar lote\b.*\bcorreo|\benviar cartas\b', t) \
       and not re.search(r'\bcorreo electr[oó]nico\b|\bemail\b', t):
        return 'correos'

    # ── MODELOS IA CONFIGURADOS ───────────────────────────────────────────────
    if re.search(
        r'\bmodelos?\b.*\bia\b|\bia\b.*\bmodelos?\b|\bmodelos? llm\b|'
        r'\bmodelos? groq\b|\bmodelos? cerebras\b|\bmodelos? disponibles\b|'
        r'\bqu[eé] modelos?\b|\bmodelos? configurados?\b|'
        r'\bconfigurar groq\b|\bclave de groq\b|\bapi key\b|'
        r'\bcambiar proveedor\b|\bproveedor de ia\b', t):
        return 'modelos_ia'

    # ── SINCRONIZAR / CAMBIAR NOMBRE ──────────────────────────────────────────
    if re.search(
        r'\bcambi(ar|o)\b.*\bnombre\b|\brenombr|\bsincroniz|\bactualiz.*nombre|'
        r'\bcorregir nombre\b|\bnombre.*equivocad|\bnombre.*mal\b|'
        r'\bcambiar.*apellido\b', t):
        return 'sincronizar_nombre'

    # ── ASIGNAR / PONER GUARDIA (acción — antes de consulta) ──────────────────
    if re.search(
        r'\basigna[r]?\b.*\bguardia|\bpon[er]?\b.*\bguardia|\bcambia[r]?\b.*\bguardia|'
        r'\bmodifica[r]?\b.*\bguardia|\bmueve\b.*\bguardia|\bguardia\b.*\basigna|'
        r'\bguardia\b.*\bpon|\bguardia\b.*\bcambia|\bguardia\b.*\bmodifica|'
        r'\bmeter\b.*\bguardia|\bfija[r]?\b.*\bguardia|'
        r'\bponer de guardia\b|\basignar guardia\b', t) \
       and not re.search(r'\bqui[eé]n\b|\bcu[aá]ndo\b|\bme toca\b|\bmi guardia\b|\bhay\b|\bqu[eé] guardia\b', t):
        return 'asignar_guardia'

    # ── QUITAR / ELIMINAR GUARDIA ───────────────────────────────────────────────
    if re.search(
        r'\bquita[r]?\b.*\bguardia|\belimina[r]?\b.*\bguardia|\bborra[r]?\b.*\bguardia|'
        r'\bvac[ií]a[r]?\b.*\bguardia|\blimpia[r]?\b.*\bguardia|'
        r'\bguardia\b.*\bquita|\bguardia\b.*\belimina|\bguardia\b.*\bborra', t):
        return 'quitar_guardia'

    # ── INTERCAMBIAR / PERMUTAR GUARDIA ─────────────────────────────────────────
    if re.search(
        r'\bintercambia[r]?\b.*\bguardia|\bpermuta[r]?\b.*\bguardia|'
        r'\bcanje[ar]?\b.*\bguardia|\bswap\b.*\bguardia|'
        r'\bguardia\b.*\bintercambi|\bguardia\b.*\bpermut|'
        r'\bcambia[r]?\b.*\bturno.*\bcon\b|\bintercambiar turno', t):
        return 'intercambiar_guardia'

    # ── MI GUARDIA (consulta personal — antes de guardia genérica) ────────────
    if re.search(
        r'\bme toca\b.*guardia|\bmi\s+(?:pr[oó]xima\s+)?guardia|'
        r'\bcu[aá]ndo.*me toca\b|\bmi turno\b|\bcu[aá]ndo.*guardia.*\byo\b|'
        r'\btengo guardia\b|\bcu[aá]ndo me toca\b|'
        r'\bmi pr[oó]xima guardia\b|\bguardia.*\bm[ií]a\b|'
        r'\bcu[aá]ndo tengo guardia\b|\bme toca pronto\b', t):
        return 'mi_guardia'

    # ── GUARDIA (consulta general) ────────────────────────────────────────────
    if re.search(
        r'\bguardia[s]?\b|\bde guardia\b|\bqui[eé]n lleva la guardia\b|'
        r'\bturno[s]?\b|\bqui[eé]n est[aá] de turno\b|\brotaci[oó]n\b|'
        r'\bequipo de guardia\b|\bqui[eé]n est[aá] de servicio\b|'
        r'\bservicio de guardia\b|\bqui[eé]n tiene guardia\b|'
        r'\ba qui[eé]n le toca guardia\b', t) \
       and not re.search(r'\bse[ñn]alamiento', t):
        return 'guardia'

    # ── CREAR VENCIMIENTO / NUEVO PLAZO (antes de consulta genérica) ──────────
    if re.search(
        r'\bcrear?\b.*\bvencimiento|\bnuevo?\b.*\bvencimiento|\ba[ñn]adir\b.*\bvencimiento|'
        r'\bcrear?\b.*\bplazo|\bnuevo?\b.*\bplazo|\ba[ñn]adir\b.*\bplazo|'
        r'\bregistrar\b.*\bvencimiento|\bregistrar\b.*\bplazo|'
        r'\bmeter\b.*\bvencimiento|\bponer\b.*\bplazo|\bapuntar\b.*\bplazo|'
        r'\bapuntar\b.*\bvencimiento', t):
        return 'crear_vencimiento'

    # ── VENCIMIENTOS / PLAZOS ─────────────────────────────────────────────────
    if re.search(
        r'\bvencimiento[s]?\b|\bplazo[s]?\b|\bvence|\bcaduca|\btermina.*plazo\b|'
        r'\bse me pasa\b.*\bplazo|\balgo que caduque\b|\bplazos pr[oó]ximos\b|'
        r'\bplazo[s]? pendiente|\bqu[eé] plazo\b|\bhay plazos?\b|'
        r'\bfecha l[ií]mite\b|\bd[ií]as h[aá]biles\b', t):
        return 'vencimientos'

    # ── BUSCAR EXPEDIENTE CONCRETO ────────────────────────────────────────────
    if re.search(r'\bexpediente\b|\bbuscar\b', t) and _extraer_expediente(texto):
        return 'buscar_expediente'

    # ── E4: PUBLICAR EN TABLÓN ─────────────────────────────────────────────────
    if re.search(
        r'\bpublica[r]?\b.*\btabl[oó]n|\btabl[oó]n\b.*\bpublica|'
        r'\bpon[er]?\b.*\btabl[oó]n|\btabl[oó]n\b.*\bpon|'
        r'\baviso\b.*\btabl[oó]n|\banuncio\b.*\btabl[oó]n|'
        r'\bescrib[eir]*\b.*\btabl[oó]n|\bcolgar?\b.*\btabl[oó]n|'
        r'\bpublicar aviso\b|\bponer aviso\b|\bnuevo aviso\b', t):
        return 'publicar_tablon'

    # ── E4: CONSULTAR TABLÓN ─────────────────────────────────────────────────
    if re.search(
        r'\btabl[oó]n\b|\bavisos?\b.*\bhoy|\bqu[eé] hay en el tabl|'
        r'\bavisos? del tabl|\bavisos? recientes?\b|\banuncios?\b.*\brecientes?|'
        r'\bver avisos?\b|\bver tabl[oó]n\b|\b[uú]ltimos? avisos?\b|'
        r'\bqu[eé] avisos?\b|\bhay avisos?\b', t) \
       and not re.search(r'\bpublica|\bpon[er]|\bescrib|\bcolga', t):
        return 'consultar_tablon'

    # ── E4: BUSCAR EN TABLÓN ─────────────────────────────────────────────────
    if re.search(
        r'\bbusca[r]?\b.*\btabl[oó]n|\btabl[oó]n\b.*\bbusca|'
        r'\bbusca[r]?\b.*\baviso|\baviso\b.*\bbusca', t):
        return 'buscar_tablon'

    # ── E4: VER NOTIFICACIONES ───────────────────────────────────────────────
    if re.search(
        r'\bnotificacion[es]*\b.*\bpendiente|\bmis notificacion|\bver notificacion|'
        r'\btengo notificacion|\bhay notificacion|\bcampanita\b|\bcampana\b|'
        r'\bnotificaciones sin leer\b|\bqu[eé] notificacion', t) \
       and not re.search(r'\bnotifica.*jud|\bnotificajud|\bcédula\b|\bedicto\b', t):
        return 'ver_notificaciones'

    # ── BUSCAR DIR3 ────────────────────────────────────────────────────────────
    if re.search(
        r'\bdir3\b|\bdirectorio com[uú]n\b|\bc[oó]digo.*organismo\b|'
        r'\borganismo.*c[oó]digo\b|\bunidad.*dir3\b|\boficina.*dir3\b|'
        r'\bc[oó]digo dir\b|\bregistro.*dir3\b|\bbusca[r]?.*dir3\b|'
        r'\bdir3.*busca|\bc[oó]digo.*juzgado\b|\bc[oó]digo.*tribunal\b|'
        r'\bc[oó]digo.*ayuntamiento\b|\bc[oó]digo.*registro\b.*\bgeneral\b|'
        r'\bc[oó]digo.*organismo\b', t):
        return 'buscar_dir3'

    # ── BÚSQUEDA GLOBAL CROSS-MÓDULO ──────────────────────────────────────────
    if re.search(
        r'\bbusca[r]?\b|\bencuentra[r]?\b|\blocaliza[r]?\b|'
        r'\bd[oó]nde\s+est[aá]\b|\bqu[eé]\s+hay\s+de\b|'
        r'\bd[oó]nde aparece\b|\ben qu[eé] m[oó]dulo\b', t) \
       and not _extraer_expediente(texto):
        return 'busqueda_global'

    # ── ESTADÍSTICAS / CUÁNTOS ────────────────────────────────────────────────
    if re.search(
        r'\bcu[aá]ntos\b|\bcu[aá]ntas\b|\bestad[ií]stic|\brecuento\b|\btotal\b|'
        r'\bresumen num[eé]rico\b|\bn[uú]meros? del mes\b|\bdatos del mes\b', t):
        return 'estadisticas'

    # ── CONFLICTOS / SOLAPAMIENTOS ────────────────────────────────────────────
    if re.search(
        r'\bconflict|\bsolapam|\bdoble\b|'
        r'\bse pisan\b|\bcolisi[oó]n\b|\bchoque\b.*\bhorario|'
        r'\bmisma hora\b.*\bmisma sala\b|\bcoinciden\b', t):
        return 'conflictos'

    # ── HUECOS / DISPONIBILIDAD ───────────────────────────────────────────────
    if re.search(
        r'\bhueco[s]?\b|\bhora.*disponib|\blibre[s]?\b|\bhora.*libre|\bpuedo se[ñn]alar|'
        r'\bpara se[ñn]alar|\bpuedo meter|\bpuedo agendar|\btengo sitio\b|'
        r'\ba qu[eé] hora puedo\b|\bcu[aá]ndo hay sitio\b|\bhay sitio\b|'
        r'\bhorario[s]? libre|\bdonde? cabe\b|\bcabe algo\b|'
        r'\bhay hueco\b|\bqu[eé] horas? hay\b.*\blibre', t):
        return 'huecos_libres'

    # ── ANULAR / CANCELAR / SUSPENDER SEÑALAMIENTO ────────────────────────────
    if re.search(
        r'\banula[r]?\b.*se[ñn]ala|\bcancela[r]?\b.*se[ñn]ala|\bsuspende[r]?\b.*se[ñn]ala|'
        r'\bborra[r]?\b.*se[ñn]ala|\belimina[r]?\b.*se[ñn]ala|'
        r'\bse[ñn]ala.*\banula|\bse[ñn]ala.*\bcancela|\bse[ñn]ala.*\bsuspende|'
        r'\bse[ñn]ala.*\bborra|\bse[ñn]ala.*\belimina|'
        r'\bquita[r]?\b.*se[ñn]ala|\bdesconvoca[r]?\b|'
        r'\banula[r]?\b.*vista|\bcancela[r]?\b.*vista|\bsuspende[r]?\b.*vista|'
        r'\banula[r]?\b.*juicio|\bcancela[r]?\b.*juicio|\bsuspende[r]?\b.*juicio', t):
        return 'anular_senalamiento'

    # ── MARCAR CELEBRADO ──────────────────────────────────────────────────────
    if re.search(
        r'\bcelebrad[oa]?\b.*se[ñn]ala|\bse[ñn]ala.*\bcelebrad|\bmarcar?\b.*celebrad|'
        r'\bcelebra[r]?\b.*se[ñn]ala|\bse celebr[oó]\b|\bya se celebr|'
        r'\bse[ñn]ala.*\brealiz|\brealiz.*se[ñn]ala|\bvisto para sentencia\b|'
        r'\bya termin[oó]\b.*se[ñn]ala|\bse ha celebrado\b|'
        r'\bha terminado\b.*\bjuicio|\bha terminado\b.*\bvista|'
        r'\bjuicio.*\bcelebrad|\bvista.*\bcelebrad|'
        r'\bmarcar.*\brealizado\b|\bse hizo\b.*\bvista', t):
        return 'marcar_celebrado'

    # ── MODIFICAR SEÑALAMIENTO ────────────────────────────────────────────────
    if re.search(
        r'\bmodifica[r]?\b.*se[ñn]ala|\bcambia[r]?\b.*(?:hora|fecha|plaza).*se[ñn]ala|'
        r'\bmueve[r]?\b.*se[ñn]ala|\bmover\b.*se[ñn]ala|\bcambia[r]?\b.*se[ñn]ala|'
        r'\bse[ñn]ala.*\bmodifica|\bse[ñn]ala.*\bcambia|\bse[ñn]ala.*\bmueve|'
        r'\baplaza[r]?\b.*se[ñn]ala|\bpospone[r]?\b.*se[ñn]ala|'
        r'\bretrasa[r]?\b.*se[ñn]ala|\badelanta[r]?\b.*se[ñn]ala|'
        r'\baplaza[r]?\b.*vista|\baplaza[r]?\b.*juicio|'
        r'\bpospone[r]?\b.*vista|\bpospone[r]?\b.*juicio|'
        r'\bcambia[r]?\b.*vista|\bcambia[r]?\b.*juicio|'
        r'\bmover\b.*vista|\bmover\b.*juicio', t):
        return 'modificar_senalamiento'

    # ── CREAR SEÑALAMIENTO ────────────────────────────────────────────────────
    if re.search(
        r'\bcrear?\b|\bnuevo se[ñn]alamiento|\bagendar\b|\ba[ñn]adir se[ñn]alamiento|'
        r'\bcita nueva\b|\bse[ñn]ala[r]?\b.*(?:\d{1,2}[/\.]\d{1,2}|\bhoy\b|\bma[ñn]ana\b)|'
        r'\bmeter\b.*\bse[ñn]ala|\bponer\b.*\bvista|\bponer\b.*\bjuicio|'
        r'\bnueva vista\b|\bnuevo juicio\b|\bfijar\b.*\bvista|'
        r'\bfijar\b.*\bse[ñn]ala|\bconvocar\b.*\bvista|\bconvocar\b.*\bjuicio', t):
        return 'crear_senalamiento'

    # ── IR A / NAVEGAR ────────────────────────────────────────────────────────
    if re.search(
        r'\bvoy\b|\bir a[l]?\b|\bnavegar\b|\babrir agenda|\bll[eé]vame\b|'
        r'\bve al\b|\bmuéstrame el\b.*\bd[ií]a\b|\babrir el\b.*\bd[ií]a\b', t):
        return 'navegar'

    # ── SEMANA EXPLÍCITA ──────────────────────────────────────────────────────
    if re.search(
        r'\besta semana\b|\bla semana\b|\bpr[oó]xima semana\b|\bsemana del\b|'
        r'\bsemana que viene\b|\bsemana entrante\b|\btoda la semana\b', t):
        return 'semana'

    # ── PRÓXIMOS SEÑALAMIENTOS ────────────────────────────────────────────────
    if re.search(
        r'\bpr[oó]xim[oa]s?\b.*\bse[ñn]alamiento|\bsiguiente[s]?\b.*\bse[ñn]alamiento|'
        r'\bpr[oó]xim[oa]s?\b.*\bvista|\bsiguiente[s]?\b.*\bvista|'
        r'\bpr[oó]xim[oa]s?\b.*\bjuicio|\bqu[eé] viene\b|\bqu[eé] tenemos\b.*\bpr[oó]xim|'
        r'\bpr[oó]xim[oa]s?\b.*\bjornada|\bsiguiente.*agenda\b|'
        r'\bqu[eé] tenemos pendiente\b|\bqu[eé] queda\b.*\bagenda|'
        r'\bpendientes? de celebrar\b|\bqu[eé] falta por celebrar\b|'
        r'\bqu[eé] nos queda\b', t):
        return 'proximos_senalamientos'

    # ► Fecha específica "N de mes" → siempre día concreto (precede al check de mes)
    if re.search(rf'\b\d{{1,2}}\s+de\s+(?:{_PATRON_MESES})\b', t):
        return 'senalamiento_dia'
    # Mes sin día numérico delante → consulta mensual
    if re.search(rf'\b(?:en|de|para|durante|del\s+mes\s+de)\s+(?:{_PATRON_MESES})\b', t):
        return 'mes'
    # Si solo se menciona el mes sin preposición ("señalamientos marzo plaza 1")
    if re.search(rf'\b(?:{_PATRON_MESES})\b', t) and not re.search(r'\d{1,2}\s+de\s+', t):
        return 'mes'
    # Por defecto: consulta de señalamientos del día
    return 'senalamiento_dia'

# ── Formateadores de respuesta ───────────────────────────────────────────────

def _fmt_senalamiento(s):
    partes_str = f" — {s['partes']}" if s.get('partes') else ''
    estado = ''
    if s.get('anulado'):     estado = ' ❌'
    elif s.get('celebrado'): estado = ' ✅'
    elif s.get('suspendido'): estado = ' ⏸️'
    return f"  • {s['hora']} — {s.get('tipo','?')} {s.get('expediente','')} {s.get('sala','')}{partes_str}{estado}".strip()

def _fmt_fecha(f):
    """YYYY-MM-DD → 'lunes 2 de marzo de 2026'"""
    try:
        d = date.fromisoformat(f)
        dias = ['lunes','martes','miércoles','jueves','viernes','sábado','domingo']
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio',
                 'agosto','septiembre','octubre','noviembre','diciembre']
        return f"{dias[d.weekday()]} {d.day} de {meses[d.month-1]} de {d.year}"
    except Exception:
        return f

# ── Lógica de consulta ───────────────────────────────────────────────────────

def _consultar_agenda(uid=None, equipo=None):
    """Carga el JSON de agenda usando la misma lógica que _resolver_fichero_modulo:
       equipo (si 'agenda' está en sus módulos) > usuario (solo si 'agenda' es privada) > compartida."""
    try:
        # 1. Equipo tiene prioridad
        if equipo:
            g = next((g for g in cargar_grupos() if g['id'] == equipo), None)
            if g and 'agenda' in g.get('modulos', []):
                datos = cargar_json(f_dato_grupo(equipo, 'agenda'))
                if datos:
                    return datos
        # 2. Usuario — solo si 'agenda' está marcada como módulo privado
        if uid:
            usuarios = cargar_usuarios()
            u = next((x for x in usuarios if x['id'] == uid), None)
            if u and 'agenda' in u.get('modulos_privados', []):
                datos = cargar_json(f_dato_usuario(uid, 'agenda'))
                if datos:
                    return datos
        # 3. Agenda compartida (caso habitual)
        return cargar_json(F_AGENDA) or {}
    except Exception:
        return cargar_json(F_AGENDA) or {}

def _consultar_guardias():
    try:
        return cargar_json(F_GUARDIAS) or {}
    except Exception:
        return {}

def _consultar_vencimientos(uid=None, equipo=None):
    """Misma lógica que _consultar_agenda: equipo > usuario privado > compartido."""
    try:
        if equipo:
            g = next((g for g in cargar_grupos() if g['id'] == equipo), None)
            if g and 'vencimientos' in g.get('modulos', []):
                datos = cargar_json(f_dato_grupo(equipo, 'vencimientos'))
                if datos:
                    return datos
        if uid:
            usuarios = cargar_usuarios()
            u = next((x for x in usuarios if x['id'] == uid), None)
            if u and 'vencimientos' in u.get('modulos_privados', []):
                datos = cargar_json(f_dato_usuario(uid, 'vencimientos'))
                if datos:
                    return datos
        return cargar_json(F_VENCIMIENTOS) or {}
    except Exception:
        return cargar_json(F_VENCIMIENTOS) or {}

def _consultar_notificajud():
    """Carga el JSON de notificajud (turnos, notificaciones, funcionarios)."""
    try:
        return cargar_json(_resolver_fichero_modulo('notificajud', F_NOTIFICAJUD)) or {}
    except Exception:
        return {}

def _consultar_registro_diligencias():
    """Carga el registro de diligencias del fichero COMPARTIDO (siempre visible)."""
    try:
        datos = cargar_json(F_NOTIFICAJUD) or {}
        return datos.get('registroDiligencias', [])
    except Exception:
        return []

# ── Configuración del LLM (API key de Groq) ──────────────────────────────────

@app.route('/api/asistente/config', methods=['GET', 'POST'])
def asistente_config():
    """Lee o guarda la configuración del LLM (multi-proveedor + modo + custom)."""
    if request.method == 'GET':
        prov_id, prov, key, modelo = _llm_cfg()
        cfg_raw = cargar_json(F_CONFIG_LLM) or {}
        customs = cfg_raw.get('proveedores_custom', {})
        # Lista de proveedores built-in que ya tienen clave guardada
        claves_guardadas = [
            pid for pid, pdata in PROVEEDORES_LLM.items()
            if cfg_raw.get(pdata['key_field'], '').strip()
        ]
        # Añadir custom que tienen clave
        for cid, cdata in customs.items():
            if cdata.get('api_key', '').strip():
                claves_guardadas.append(cid)
        # Merge proveedores built-in + custom para la UI
        proveedores_all = {
            k: {'nombre': v['nombre'], 'modelo_def': v['modelo_def']}
            for k, v in PROVEEDORES_LLM.items()
        }
        for cid, cdata in customs.items():
            proveedores_all[cid] = {
                'nombre':    cdata.get('nombre', cid),
                'modelo_def': cdata.get('modelo', ''),
                'custom':    True,
                'url':       cdata.get('url', ''),
                'formato':   cdata.get('formato', 'openai'),
            }
        return jsonify({
            'configurado':      bool(prov),
            'proveedor':        prov_id   or '',
            'proveedor_nombre': prov['nombre'] if prov else '',
            'modelo':           modelo    or '',
            'modo':             cfg_raw.get('modo', 'reglas'),
            'claves_guardadas': claves_guardadas,
            'proveedores':      proveedores_all,
        })
    # POST: guardar nueva configuración
    datos   = request.get_json(force=True) or {}
    prov_id = datos.get('proveedor', 'groq').strip()
    api_key = datos.get('api_key', '').strip()
    modelo  = datos.get('modelo', '').strip()
    modo    = datos.get('modo', '').strip()
    custom_data = datos.get('custom')  # {nombre, url, formato, modelo}
    _resp = None
    with editar_json(F_CONFIG_LLM) as cfg:
        # Guardar modo si se envía
        if modo in ('reglas', 'ia', 'combinado'):
            cfg['modo'] = modo
        # ── Proveedor custom (nuevo o existente) ──────────────────────────────
        if custom_data:
            customs = cfg.setdefault('proveedores_custom', {})
            # Generar ID si es nuevo
            if prov_id == 'custom_new' or prov_id not in customs:
                prov_id = 'custom_' + str(len(customs) + 1)
                while prov_id in customs:
                    prov_id = 'custom_' + str(int(prov_id.split('_')[1]) + 1)
            api_key_final = api_key or customs.get(prov_id, {}).get('api_key', '')
            if not api_key_final:
                _resp = (jsonify({'error': 'Introduce la API key'}), 400)
                raise _NoGuardar()
            customs[prov_id] = {
                'nombre':  custom_data.get('nombre', 'Custom'),
                'url':     custom_data.get('url', '').rstrip('/'),
                'formato': custom_data.get('formato', 'openai'),
                'modelo':  modelo or custom_data.get('modelo', ''),
                'api_key': api_key_final,
            }
            cfg['proveedor'] = prov_id
            cfg['modelo']    = modelo or custom_data.get('modelo', '')
            nombre = customs[prov_id]['nombre']
            log(f'[LLM] Config guardada: proveedor={prov_id} ({nombre}) modelo={cfg["modelo"]} modo={cfg.get("modo","reglas")}')
            _resp = jsonify({'ok': True, 'proveedor': prov_id, 'nombre': nombre})
        else:
            # ── Proveedor built-in o custom existente ─────────────────────────
            prov = PROVEEDORES_LLM.get(prov_id)
            if not prov:
                customs = cfg.get('proveedores_custom', {})
                if prov_id in customs:
                    if api_key:
                        customs[prov_id]['api_key'] = api_key
                    cfg['proveedor'] = prov_id
                    cfg['modelo']    = modelo or customs[prov_id].get('modelo', '')
                    log(f'[LLM] Config guardada: proveedor={prov_id} modelo={cfg["modelo"]} modo={cfg.get("modo","reglas")}')
                    _resp = jsonify({'ok': True, 'proveedor': prov_id, 'nombre': customs[prov_id].get('nombre', prov_id)})
                else:
                    _resp = (jsonify({'error': f'Proveedor desconocido: {prov_id}'}), 400)
                    raise _NoGuardar()
            else:
                if api_key:
                    cfg[prov['key_field']] = api_key
                else:
                    if not cfg.get(prov['key_field'], '').strip():
                        _resp = (jsonify({'error': f'Introduce la API key de {prov["nombre"]}'}), 400)
                        raise _NoGuardar()
                cfg['proveedor'] = prov_id
                cfg['modelo']    = modelo or prov['modelo_def']
                log(f'[LLM] Config guardada: proveedor={prov_id} modelo={cfg["modelo"]} modo={cfg.get("modo","reglas")}')
                _resp = jsonify({'ok': True, 'proveedor': prov_id, 'nombre': prov['nombre']})
    return _resp

@app.route('/api/asistente/config/custom/<cid>', methods=['DELETE'])
def asistente_config_delete_custom(cid):
    """Elimina un proveedor custom."""
    _resp = None
    with editar_json(F_CONFIG_LLM) as cfg:
        customs = cfg.get('proveedores_custom', {})
        if cid not in customs:
            _resp = (jsonify({'error': 'Proveedor no encontrado'}), 404)
            raise _NoGuardar()
        del customs[cid]
        # Si era el proveedor activo, resetear a reglas
        if cfg.get('proveedor') == cid:
            cfg['proveedor'] = ''
        log(f'[LLM] Proveedor custom eliminado: {cid}')
        _resp = jsonify({'ok': True})
    return _resp

@app.route('/api/asistente/glosario/reload', methods=['POST'])
def glosario_reload():
    """Fuerza la recarga del glosario_ia.txt en memoria (útil tras actualizar el docx)."""
    global _glosario_cache
    _glosario_cache = None
    g = _cargar_glosario()
    return jsonify({'ok': True, 'chars': len(g),
                    'mensaje': f'Glosario recargado: {len(g)} caracteres'})

@app.route('/api/asistente/diagnostico', methods=['GET'])
def asistente_diagnostico():
    """Diagnóstico completo del LLM configurado y del motor de reglas."""
    resultado = {}

    # 1. Configuración activa
    prov_id, prov, key, modelo = _llm_cfg()
    resultado['proveedor']         = prov_id or '(ninguno)'
    resultado['proveedor_nombre']  = prov['nombre'] if prov else '(ninguno)'
    resultado['clave_configurada'] = bool(key)
    resultado['clave_prefijo']     = key[:12] + '...' if key else '(vacía)'
    resultado['modelo']            = modelo or '(ninguno)'

    # 2. Test de conexión real con el proveedor configurado (usa urllib, sin dependencias)
    if key and prov:
        try:
            hdrs_test = {"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json",
                         "User-Agent": "python-requests/2.31.0"}   # evita bloqueo Cloudflare
            if prov_id == 'openrouter':
                hdrs_test['HTTP-Referer'] = 'http://localhost'
                hdrs_test['X-Title']      = 'Portal Judicial'
            url_test = prov['url'].rstrip('/') + '/chat/completions'
            status, rj = _http_post_json(url_test, hdrs_test, {
                "model": modelo,
                "messages": [
                    {"role": "system", "content": "Responde solo con: CONEXIÓN OK"},
                    {"role": "user",   "content": "test"}
                ],
                "temperature": 0, "max_tokens": 10
            }, timeout=10)
            if status == 200:
                resultado['llm_ok']        = True
                resultado['llm_respuesta'] = rj['choices'][0]['message']['content'].strip()
            else:
                resultado['llm_ok']      = False
                resultado['llm_error']   = str(rj)
                resultado['llm_status']  = status
        except Exception as e:
            resultado['llm_ok']        = False
            resultado['llm_exception'] = str(e)
    else:
        resultado['llm_ok']    = False
        resultado['llm_error'] = 'Sin clave o proveedor no configurado'

    # 3. Glosario IA
    g = _cargar_glosario()
    resultado['glosario_cargado']      = bool(g)
    resultado['glosario_chars']        = len(g)
    resultado['glosario_tokens_aprox'] = len(g) // 4

    # 4. Test de detección de intención
    frases_test = [
        'que hay el martes 3 de marzo', 'señalamientos de marzo',
        'señalamientos hoy', 'quién está de guardia esta semana',
        'peritos tasadores de inmuebles', 'presos preventivos plaza 1',
        'videoconferencias esta semana', 'vacaciones en agosto',
    ]
    resultado['test_intentos'] = {f: _detectar_intencion(f) for f in frases_test}

    # 5. Test de extracción de fechas
    hoy = date.today()
    resultado['test_fechas'] = {
        'el martes 3 de marzo': _extraer_fecha('el martes 3 de marzo', hoy),
        'el 15 de abril':       _extraer_fecha('el 15 de abril', hoy),
        'el próximo lunes':     _extraer_fecha('el próximo lunes', hoy),
        'hoy':                  _extraer_fecha('hoy', hoy),
    }

    return jsonify(resultado)

# ── Endpoint principal del asistente ─────────────────────────────────────────

@app.route('/api/asistente', methods=['POST'])
def asistente_endpoint():
    """Motor de lenguaje natural para el asistente judicial."""
    try:
        return _asistente_endpoint_impl()
    except Exception as _exc:
        log(f'[ASISTENTE] Error no capturado: {_exc}', 'ERROR')
        import traceback as _tb
        log(_tb.format_exc(), 'ERROR')
        return jsonify({
            'respuesta': '⚠️ Error interno del servidor al procesar la consulta.',
            'accion': None, 'intencion': 'error', 'fuente': 'error',
            'fuente_nombre': 'Error', 'groq_error': str(_exc),
            '_debug': {'error': str(_exc)}
        })

def _asistente_endpoint_impl():
    datos_req = request.get_json(force=True) or {}
    pregunta   = datos_req.get('pregunta', '').strip()
    ctx        = datos_req.get('contexto', {})
    uid        = ctx.get('uid')
    equipo     = ctx.get('equipo')
    hoy        = date.today()

    if not pregunta:
        return jsonify({'respuesta': 'Por favor escribe tu pregunta.', 'accion': None})

    intencion  = _detectar_intencion(pregunta)
    fecha_str  = _extraer_fecha(pregunta, hoy)
    semana     = _extraer_semana(pregunta, hoy)
    mes_info   = _extraer_mes(pregunta, hoy)
    expediente = _extraer_expediente(pregunta)
    hora_str   = _extraer_hora(pregunta)

    agenda_datos = _consultar_agenda(uid, equipo)
    senalamientos = agenda_datos.get('senalamientos', [])
    plazas_disp   = list({s.get('plaza','') for s in senalamientos if s.get('plaza')})
    tipos_disp    = list({s.get('tipo','') for s in senalamientos if s.get('tipo')})
    plaza_str  = _extraer_plaza(pregunta, plazas_disp)
    tipo_str   = _extraer_tipo(pregunta, tipos_disp)

    respuesta    = ''
    accion       = None
    contexto_groq = ''   # contexto anonimizado para Groq (sin datos personales)

    # ── TURNOS (quién está en cada servicio hoy) ──────────────────────────────
    if intencion == 'turnos':
        ndata  = _consultar_notificajud()
        funcs  = ndata.get('funcionarios', [])
        t_asig   = ndata.get('turnosAsignaciones', {})
        svc_list = ndata.get('serviciosTurnos', [])
        # Clave del martes de la semana actual (o de la fecha mencionada)
        fd     = date.fromisoformat(fecha_str) if fecha_str else hoy
        diff   = (fd.weekday() - 1) % 7
        martes = (fd - timedelta(days=diff)).isoformat()
        # FIX: 'cambios' es clave raíz de t_asig, NO anidada dentro de la semana
        top_cambios = t_asig.get('cambios', {})
        sem   = top_cambios.get(martes) or t_asig.get(martes) or {}
        t_hoy = dict(sem) if isinstance(sem, dict) else {}
        # Lista de servicios: dinámica desde serviciosTurnos o fallback hardcoded
        if svc_list:
            SVC = [(s['id'], '📋 ' + s.get('nombre', s['id'])) for s in svc_list]
        else:
            SVC = [('vistas','⚖️ Vistas'), ('guardia','🚨 Guardia'),
                   ('atencion','🎧 Atención Público'), ('notificaciones','📋 Notificaciones')]
        def _fn(fid):
            f = next((x for x in funcs if x.get('id') == fid), None)
            if not f: return f'ID:{fid}'
            p = f.get('nombre','').split(',')
            return f"{p[1].strip()} {p[0].strip()}" if len(p) > 1 else f.get('nombre','').strip()
        dias_es = ['lunes','martes','miércoles','jueves','viernes','sábado','domingo']
        dia_txt = f"{dias_es[fd.weekday()].capitalize()} {fd.day:02d}/{fd.month:02d}/{fd.year}"
        lineas  = [f"📋 Turnos del {dia_txt}:"]
        hay     = False
        for svc_id, svc_nom in SVC:
            ids = t_hoy.get(svc_id, [])
            if ids:
                hay = True
                lineas.append(f"  {svc_nom}: {', '.join(_fn(i) for i in ids)}")
        if not hay:
            lineas.append("No hay turnos asignados para esta semana todavía.")
            lineas.append("Puedes asignarlos en el módulo Notificajud → Turnos.")
        respuesta = '\n'.join(lineas)
        accion    = {'tipo': 'navegar_modulo', 'modulo': 'notificajud'}
        # Contexto para LLM: servicios cubiertos CON nombres reales
        svcs_txt = []
        for svc_id, svc_nom in SVC:
            ids = t_hoy.get(svc_id, [])
            if ids:
                svcs_txt.append(f"{svc_nom}: {', '.join(_fn(i) for i in ids)}")
        contexto_groq  = (
            f"Turnos semana del martes {martes} ({dia_txt}):\n"
            + ('\n'.join(svcs_txt) if svcs_txt else "Sin turnos asignados.")
        )

    # ── ANOTAR NOTIFICACIÓN ──────────────────────────────────────────────────
    elif intencion == 'anotar_notificacion':
        t_low    = pregunta.lower()
        positiva = bool(re.search(r'\bpositiva\b', t_low))
        negativa = bool(re.search(r'\bnegativa\b', t_low))
        expte    = _extraer_expediente(pregunta)
        partes   = []
        if positiva:   partes.append("resultado: positiva ✅")
        elif negativa: partes.append("resultado: negativa ❌")
        if expte:      partes.append(f"expediente: {expte}")
        if fecha_str:  partes.append(f"fecha: {_fmt_fecha(fecha_str)}")
        detalle  = "\nHe detectado: " + " | ".join(partes) + "." if partes else ""
        respuesta = (
            f"Para registrar el acto de comunicación, abre el módulo Notificajud.{detalle}\n"
            f"📋 Allí puedes rellenar todos los campos y registrar si fue positiva o negativa."
        )
        accion = {'tipo': 'navegar_modulo', 'modulo': 'notificajud'}

        # Añadir info de registro de diligencias si hay pendientes
        reg = _consultar_registro_diligencias()
        pendientes = [r for r in reg if r.get('estado') == 'Pendiente']
        planificados = [r for r in reg if r.get('estado') == 'Planificado']
        if pendientes or planificados:
            resumen = f"\n📊 Registro: {len(pendientes)} pendiente(s), {len(planificados)} planificado(s)."
            respuesta += resumen

    # ── INSACULAR PERITO ────────────────────────────────────────────────────
    elif intencion == 'insacular_perito':
        pdata   = cargar_json(_resolver_fichero_modulo('peritos', F_PERITOS)) or {}
        peritos_all = pdata.get('peritos', [])
        esps    = pdata.get('especialidades', [])
        t_low   = _sin_acentos(pregunta.lower())

        # Detectar especialidad (comparación sin acentos)
        esp_match = None
        for esp in sorted(esps, key=lambda e: len(e.get('nombre','')), reverse=True):
            if _sin_acentos(esp.get('nombre','').lower()) in t_low:
                esp_match = esp; break
        if not esp_match:
            KW_ESP = [('inmueble','inmueble'),('tasac','tasac'),('forense','forense'),
                      ('psicolog','psicolog'),('contab','contab'),('inform','inform'),
                      ('caligr','caligr'),('arquitect','arquitect'),('ingeni','ingeni'),
                      ('medic','medic'),('econom','econom'),('digital','digital')]
            for kw, frag in KW_ESP:
                if kw in t_low:
                    for esp in esps:
                        if frag in _sin_acentos(esp.get('nombre','').lower()):
                            esp_match = esp; break
                    if esp_match: break

        if not esp_match:
            # Listar especialidades disponibles
            disp = [e.get('nombre','') for e in esps[:15]]
            respuesta = (
                "No pude identificar la especialidad de perito.\n"
                "Indica la especialidad, por ejemplo:\n"
                "  «selecciona un perito psicólogo»\n\n"
                "📋 Especialidades disponibles:\n  • " + '\n  • '.join(disp)
            )
            if len(esps) > 15:
                respuesta += f"\n  … y {len(esps)-15} más."
            accion = {'tipo': 'navegar_modulo', 'modulo': 'peritos'}
        else:
            eid = esp_match.get('id')
            nombre_esp = esp_match.get('nombre', '')
            # Filtrar peritos disponibles de esa especialidad
            disponibles = [p for p in peritos_all
                           if p.get('disponible', True) and
                           (p.get('especialidadId') == eid or eid in (p.get('especialidades') or []))]

            if not disponibles:
                respuesta = f"No hay peritos disponibles de «{nombre_esp}»."
                accion = {'tipo': 'navegar_modulo', 'modulo': 'peritos'}
            else:
                exp_txt = ((tipo_str + ' ') if tipo_str else '') + (expediente or '')
                exp_txt = exp_txt.strip()
                respuesta = (
                    f"🎲 Insaculación de perito:\n"
                    f"  📋 Especialidad: {nombre_esp}\n"
                    f"  👥 Disponibles: {len(disponibles)} perito(s)\n"
                )
                if exp_txt:
                    respuesta += f"  📁 Expediente: {exp_txt}\n"
                respuesta += "\n¿Confirmar la selección aleatoria?"
                accion = {
                    'tipo': 'confirmar_insaculacion',
                    'especialidadId': eid,
                    'nombre_esp': nombre_esp,
                    'expediente': exp_txt,
                    'motivo': ''
                }

    # ── PERITOS / TASADORES ──────────────────────────────────────────────────
    elif intencion == 'peritos':
        pdata   = cargar_json(_resolver_fichero_modulo('peritos', F_PERITOS)) or {}
        peritos = pdata.get('peritos', [])
        esps    = pdata.get('especialidades', [])
        t_low   = _sin_acentos(pregunta.lower())
        # Buscar especialidad por nombre (sin acentos)
        esp_match = None
        for esp in sorted(esps, key=lambda e: len(e.get('nombre','')), reverse=True):
            if _sin_acentos(esp.get('nombre','').lower()) in t_low:
                esp_match = esp; break
        # Palabras clave → especialidad
        if not esp_match:
            KW = [('inmueble','inmueble'),('tasac','inmueble'),('forense','forense'),
                  ('psicolog','psicolog'),('contab','contab'),('inform','inform')]
            for kw, frag in KW:
                if kw in t_low:
                    for esp in esps:
                        if frag in _sin_acentos(esp.get('nombre','').lower()):
                            esp_match = esp; break
                    if esp_match: break
        if esp_match:
            eid       = esp_match.get('id')
            filtro    = [p for p in peritos if p.get('especialidadId') == eid or eid in (p.get('especialidades') or [])]
            subtitulo = esp_match.get('nombre','')
        else:
            filtro, subtitulo = peritos, None
        if not filtro:
            filtro = peritos  # fallback
        if not filtro:
            respuesta = "No hay peritos registrados en el sistema todavía.\n🔬 Puedes añadirlos en el módulo Peritos."
        else:
            cab = "🔬 Peritos" + (f" — {subtitulo}" if subtitulo else f" ({len(filtro)} en total)") + ":"
            lineas = [cab]
            for i, p in enumerate(filtro[:12], 1):
                nombre = p.get('nombre', 'Sin nombre')
                tel    = p.get('telefono','')
                noms_e = []
                for eid2 in (p.get('especialidades') or []):
                    e = next((x for x in esps if x.get('id') == eid2), None)
                    if e: noms_e.append(e.get('nombre',''))
                lineas.append(
                    f"  {i}. {nombre}"
                    + (f" — {' / '.join(noms_e)}" if noms_e else "")
                    + (f"  📞{tel}" if tel else "")
                )
            if len(filtro) > 12:
                lineas.append(f"  … y {len(filtro)-12} más en el módulo.")
            respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'peritos'}
        # Contexto para Groq: especialidades y total (sin nombres de peritos)
        esps_presentes = list(set(
            next((e.get('nombre','?') for e in esps if e.get('id') == eid2), '?')
            for p in filtro[:20] for eid2 in (p.get('especialidades') or [])
        ))
        contexto_groq = (
            f"Peritos{(' — '+subtitulo) if subtitulo else ''}: {len(filtro)} registrados\n"
            + (f"Especialidades: {', '.join(esps_presentes)}" if esps_presentes else '')
        )

    # ── PRESOS / INTERNOS ─────────────────────────────────────────────────────
    elif intencion == 'presos':
        pdata  = cargar_json(F_PRESOS) or {}
        presos = pdata.get('presos', [])
        t_low  = pregunta.lower()
        # Filtrar por plaza instructora o sentenciadora
        if plaza_str:
            filtro_p = [p for p in presos
                        if plaza_str.lower() in p.get('plazaInstructora', '').lower()
                        or plaza_str.lower() in p.get('plazaSentenciadora', '').lower()]
        else:
            filtro_p = presos
        # Filtrar por situación procesal
        sit = None
        if re.search(r'\bpreventivo[s]?\b', t_low):          sit = 'preventivo'
        elif re.search(r'\bpenado[s]?\b', t_low):            sit = 'penado'
        elif re.search(r'\blibertad condicional\b', t_low):  sit = 'libertad condicional'
        elif re.search(r'\btercer grado\b', t_low):          sit = 'tercer grado'
        elif re.search(r'\bextinguida\b', t_low):            sit = 'extinguida'
        if sit:
            filtro_p = [p for p in filtro_p if sit.lower() in p.get('situacion', '').lower()]
        p_txt   = f" en {plaza_str}" if plaza_str else ''
        sit_txt = f" en situación '{sit}'" if sit else ''
        if not filtro_p:
            respuesta = f"No hay internos registrados{p_txt}{sit_txt} en el sistema."
        else:
            lineas = [f"👤 Internos registrados{p_txt}{sit_txt}: {len(filtro_p)}"]
            for i, p in enumerate(filtro_p[:12], 1):
                centro  = p.get('centroPenitenciario', '?')
                sit_p   = p.get('situacion', '?')
                dias    = p.get('diasEnPrision', '')
                codigo  = p.get('codigoInterno', '')
                lineas.append(
                    f"  {i}. [{codigo}] {centro} — {sit_p}"
                    + (f" ({dias} días)" if dias else "")
                )
            if len(filtro_p) > 12:
                lineas.append(f"  … y {len(filtro_p)-12} más en el módulo Presos.")
            respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'presos'}
        # Contexto anonimizado para Groq (sin nombre, sin documento)
        centros_uniq = list(set(p.get('centroPenitenciario', '?') for p in filtro_p[:20]))
        sits_uniq    = list(set(p.get('situacion', '?') for p in filtro_p))
        contexto_groq = (
            f"Total internos{p_txt}: {len(filtro_p)}\n"
            + (f"Situación filtrada: {sit}\n" if sit else '')
            + (f"Centros: {', '.join(centros_uniq)}\n" if centros_uniq else '')
            + (f"Situaciones presentes: {', '.join(sits_uniq)}" if sits_uniq else '')
        )

    # ── SOLICITUDES DE ARCHIVO ─────────────────────────────────────────────
    elif intencion == 'archivo':
        adata = cargar_json(_resolver_fichero_modulo('archivo', F_ARCHIVO)) or {}
        sols  = adata.get('solicitudes', [])
        plzs  = adata.get('plazas', [])
        if not sols:
            respuesta = "No hay solicitudes de archivo registradas en el sistema."
        else:
            pendientes = [s for s in sols if s.get('estado') == 'solicitado']
            entregados = [s for s in sols if s.get('estado') == 'entregado']
            devueltos  = [s for s in sols if s.get('estado') == 'devuelto']
            lineas = [f"Solicitudes de archivo: {len(sols)} total"]
            if pendientes: lineas.append(f"  - Solicitados: {len(pendientes)}")
            if entregados: lineas.append(f"  - Entregados: {len(entregados)}")
            if devueltos:  lineas.append(f"  - Devueltos: {len(devueltos)}")
            respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'archivo'}
        contexto_groq = f"Total solicitudes archivo: {len(sols)}, plazas: {len(plzs)}"

    # ── AUXILIOS JUDICIALES ───────────────────────────────────────────────────
    elif intencion == 'auxilios':
        adata   = cargar_json(F_AUXILIOS) or {}
        auxilios = adata.get('auxilios', [])
        t_low   = pregunta.lower()
        # Filtrar por tipo
        tipo_aux = None
        if re.search(r'\bvideoconferencia[s]?\b|\bvc\b|\bvideo\b', t_low):
            tipo_aux = 'Videoconferencia'
        elif re.search(r'\bexhorto[s]?\b', t_low):
            tipo_aux = 'Exhorto'
        # Filtrar por estado
        solo_pend = bool(re.search(r'\bpendiente[s]?\b', t_low))
        solo_real = bool(re.search(r'\brealizado[s]?\b|\bcompletado[s]?\b', t_low))
        filtro_a = auxilios
        if plaza_str:
            filtro_a = [a for a in filtro_a
                        if plaza_str.lower() in a.get('plaza', '').lower()]
        if tipo_aux:
            filtro_a = [a for a in filtro_a
                        if tipo_aux.lower() in a.get('tipo', '').lower()]
        if solo_pend:
            filtro_a = [a for a in filtro_a
                        if a.get('estado', '').lower() == 'pendiente']
        elif solo_real:
            filtro_a = [a for a in filtro_a
                        if a.get('estado', '').lower() == 'realizado']
        # Filtrar por fecha si se indica
        if fecha_str:
            filtro_a = [a for a in filtro_a if a.get('fecha', '') == fecha_str]
        t_txt   = f" — {tipo_aux}" if tipo_aux else ''
        p_txt   = f" en {plaza_str}" if plaza_str else ''
        est_txt = " pendientes" if solo_pend else (" realizados" if solo_real else '')
        if not filtro_a:
            respuesta = f"No hay auxilios judiciales{est_txt}{p_txt}{t_txt} en el sistema."
        else:
            lineas = [f"📹 Auxilios{est_txt}{p_txt}{t_txt}: {len(filtro_a)}"]
            for i, a in enumerate(sorted(filtro_a, key=lambda x: x.get('fecha', ''))[:12], 1):
                fecha_a  = _fmt_fecha(a['fecha']) if a.get('fecha') else '?'
                hora_a   = a.get('hora', '')
                tipo_a   = a.get('tipo_nombre') or a.get('tipo', '?')
                estado_a = a.get('estado', '?')
                plaza_a  = a.get('plaza', '')
                proc_a   = a.get('procedimiento', '')
                det_a    = a.get('detalles', '') or a.get('observaciones', '')
                lineas.append(
                    f"  {i}. {tipo_a} — {fecha_a}"
                    + (f" {hora_a}" if hora_a else '') + f" — {estado_a}"
                )
                extra = []
                if proc_a: extra.append(proc_a)
                if plaza_a and not p_txt: extra.append(plaza_a)
                if det_a: extra.append(det_a[:60] + ('…' if len(det_a) > 60 else ''))
                if extra:
                    lineas.append(f"     {' · '.join(extra)}")
            if len(filtro_a) > 12:
                lineas.append(f"  … y {len(filtro_a)-12} más en el módulo Auxilios.")
            respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'auxilios'}
        contexto_groq = (
            f"Auxilios judiciales{est_txt}{p_txt}: {len(filtro_a)} registros\n"
            + '\n'.join(
                f"{a.get('tipo_nombre') or a.get('tipo','?')} — "
                f"{a.get('fecha','?')} {a.get('hora','')} — "
                f"{a.get('estado','?')} — "
                f"{a.get('procedimiento') or '(sin proc.)'}"
                + (f" — {a.get('detalles','')[:60]}" if a.get('detalles') else '')
                for a in filtro_a[:10]
            )
        )

    # ── VACACIONES / AUSENCIAS ────────────────────────────────────────────────
    elif intencion == 'vacaciones':
        vac_datos    = cargar_json(F_VACACIONES) or {}
        funcionarios = vac_datos.get('funcionarios', [])
        vacaciones_l = vac_datos.get('vacaciones', [])
        t_low        = pregunta.lower()
        # Filtrar por mes o fecha
        filtro_v = vacaciones_l
        if mes_info:
            year_v, mes_v = mes_info
            mes_str = f"{year_v}-{mes_v:02d}"
            filtro_v = [v for v in filtro_v
                        if v.get('inicio', '')[:7] <= mes_str <= v.get('fin', '')[:7]]
        elif fecha_str:
            filtro_v = [v for v in filtro_v
                        if v.get('inicio', '') <= fecha_str <= v.get('fin', '')]
        # Filtrar por tipo de ausencia
        tipo_aus2 = None
        if re.search(r'\bincapacidad\b|\bit\b', t_low):   tipo_aus2 = 'IT'
        elif re.search(r'\basuntos propios\b', t_low):    tipo_aus2 = 'Asuntos Propios'
        elif re.search(r'\bpermiso\b', t_low):            tipo_aus2 = 'Permiso'
        elif re.search(r'\bvacacion\b', t_low):           tipo_aus2 = 'Vacaciones'
        if tipo_aus2:
            filtro_v = [v for v in filtro_v
                        if tipo_aus2.lower() in v.get('tipo', '').lower()]
        def _nom_func(fid):
            f = next((x for x in funcionarios if x.get('id') == fid), None)
            if not f: return '—'
            return f.get('nombre', '—')
        mes_nombre_v = list(_MESES_ES.keys())[mes_info[1]-1] if mes_info else ''
        etiq_v   = f" en {mes_nombre_v} {mes_info[0]}" if mes_info else (f" el {_fmt_fecha(fecha_str)}" if fecha_str else '')
        aus_txt  = f" — {tipo_aus2}" if tipo_aus2 else ''
        if not filtro_v:
            respuesta = f"No hay ausencias registradas{etiq_v}{aus_txt}."
        else:
            lineas = [f"📅 Ausencias{etiq_v}{aus_txt}: {len(filtro_v)}"]
            for v in sorted(filtro_v, key=lambda x: x.get('inicio', ''))[:12]:
                nombre_v = _nom_func(v.get('funcionarioId'))
                tipo_v   = v.get('tipo', '?')
                ini_v    = _fmt_fecha(v['inicio']) if v.get('inicio') else '?'
                fin_v    = _fmt_fecha(v['fin'])    if v.get('fin')    else '?'
                lineas.append(f"  • {nombre_v} — {tipo_v}: del {ini_v} al {fin_v}")
            if len(filtro_v) > 12:
                lineas.append(f"  … y {len(filtro_v)-12} más en el módulo Vacaciones.")
            respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'vacaciones'}
        tipos_aus_uniq = list(set(v.get('tipo', '?') for v in filtro_v))
        contexto_groq = (
            f"Ausencias{etiq_v}: {len(filtro_v)} registros\n"
            + (f"Tipos: {', '.join(tipos_aus_uniq)}" if tipos_aus_uniq else '')
        )

    # ── AUSENCIAS DE PLAZAS ───────────────────────────────────────────────
    elif intencion == 'ausencias_plazas':
        adata     = cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)) or {}
        plazas    = adata.get('plazas', [])
        todas_aus = adata.get('ausencias', [])
        hoy_str   = hoy.isoformat()
        # Filtrar ausencias activas hoy
        activas = [a for a in todas_aus
                   if a.get('fechaInicio', '') <= hoy_str <= a.get('fechaFin', '9')]
        plazas_map = {p['id']: p for p in plazas}
        if not activas:
            respuesta = "No hay ausencias activas en ninguna plaza hoy.\n🏛️ Puedes consultar y registrar ausencias en el módulo Ausencias."
        else:
            lineas = [f"🏛️ Ausencias activas hoy ({len(activas)}):"]
            for a in activas:
                plaza   = plazas_map.get(a.get('plazaId'), {})
                plaza_n = plaza.get('nombre', '?')
                cargo   = next((c for c in plaza.get('cargos', [])
                                if c['id'] == a.get('cargoId')), {})
                cargo_n = cargo.get('nombre', '?')
                titular = a.get('titular', '?')
                sust    = a.get('sustituto', '')
                motivo  = a.get('motivo', '')
                lineas.append(f"  • {plaza_n} — {cargo_n}: {titular}")
                extra = []
                if sust:   extra.append(f"Sustituye: {sust}")
                if motivo: extra.append(motivo)
                if extra:
                    lineas.append(f"    {' · '.join(extra)}")
            respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'ausencias'}
        contexto_groq = (
            f"Ausencias de plazas activas hoy: {len(activas)} de {len(todas_aus)} totales "
            f"en {len(plazas)} plazas configuradas."
        )

    # ── MI GUARDIA (consulta personal) ──────────────────────────────────────
    elif intencion == 'mi_guardia':
        g_datos = _consultar_guardias()
        funcionarios = g_datos.get('funcionarios', [])
        guardias_sem = g_datos.get('guardias', {})

        # Obtener nombre del usuario activo
        usr_info = _usuario_por_id(uid) if uid else {}
        nombre_usr = usr_info.get('nombre', '')

        # Buscar funcionario que coincida con el usuario
        # Formato portal: "JOSE FERREIROS" | Formato guardias: "FERREIROS FERRO, JOSE"
        # Comparamos por palabras comunes (al menos 2: nombre + un apellido)
        func_match = None
        if nombre_usr:
            nu = nombre_usr.upper().strip()
            usr_words = set(nu.split())
            mejor_score = 0
            for f in funcionarios:
                if not f.get('activo'):
                    continue
                fn = f['nombre'].upper().strip()
                f_words = set(fn.replace(',', '').split())
                common = usr_words & f_words
                if len(common) >= 2 and len(common) > mejor_score:
                    mejor_score = len(common)
                    func_match = f

        if not func_match:
            respuesta = (
                f"No pude encontrarte en la lista de funcionarios de guardias.\n"
                f"Tu usuario: {nombre_usr or '(sin nombre)'}\n\n"
                f"Abre el módulo de guardias para verificar tu nombre en la lista."
            )
            contexto_groq = "Usuario no encontrado en la lista de funcionarios de guardias."
        else:
            fid = func_match['id']
            dept = func_match.get('dept', '')
            # Mapear dept → campo en guardia
            campo_map = {'gestion': 'gestorId', 'tramitacion': 'tramitadorId', 'auxilio': 'auxilioId'}
            campo = campo_map.get(dept)
            dept_label = {'gestion': 'Gestión', 'tramitacion': 'Tramitación', 'auxilio': 'Auxilio'}.get(dept, dept)

            # Nombre formateado
            partes_n = func_match['nombre'].split(',')
            nombre_fmt = f"{partes_n[1].strip()} {partes_n[0].strip()}" if len(partes_n) > 1 else func_match['nombre']

            # Buscar próximas guardias (hasta 16 semanas adelante)
            proximas = []
            dow = hoy.weekday()
            martes_actual = hoy - timedelta((dow - 1) % 7)

            for i in range(16):
                sem_martes = martes_actual + timedelta(weeks=i)
                wk = sem_martes.isoformat()
                gs = guardias_sem.get(wk, {})
                if not gs:
                    continue
                # Comprobar si este funcionario tiene guardia en algún rol
                roles = []
                if campo and gs.get(campo) == fid:
                    roles.append(dept_label)
                # También comprobar AF
                if gs.get('fiscalId') == fid:
                    roles.append('Apoyo Fiscal')
                # Comprobar otros roles (por si está en otro dept por override)
                for d2, c2 in campo_map.items():
                    if d2 != dept and gs.get(c2) == fid:
                        lbl2 = {'gestion': 'Gestión', 'tramitacion': 'Tramitación', 'auxilio': 'Auxilio'}.get(d2, d2)
                        if lbl2 not in roles:
                            roles.append(lbl2)

                if roles:
                    fin_sem = sem_martes + timedelta(6)
                    rango = f"{sem_martes.strftime('%d/%m')} – {fin_sem.strftime('%d/%m/%Y')}"
                    proximas.append((rango, ', '.join(roles)))

            if proximas:
                lineas = [f"🛡️ Próximas guardias de {nombre_fmt} ({dept_label}):"]
                for rango, rol in proximas[:8]:
                    lineas.append(f"  📅 {rango} — {rol}")
                if len(proximas) > 8:
                    lineas.append(f"  ... y {len(proximas) - 8} más")
                respuesta = '\n'.join(lineas)
            else:
                respuesta = f"No encontré guardias asignadas para {nombre_fmt} en las próximas 16 semanas."
            contexto_groq = respuesta

        accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}

    # ── GUARDIA ──────────────────────────────────────────────────────────────
    elif intencion == 'guardia':
        g_datos = _consultar_guardias()
        funcionarios = g_datos.get('funcionarios', [])
        guardias_sem = g_datos.get('guardias', {})
        dia_overrides = g_datos.get('diaOverrides', {})
        plazas_g = g_datos.get('plazas', [])

        def nombre_f(fid):
            f = next((x for x in funcionarios if x.get('id') == fid), None)
            if not f: return '—'
            partes = f['nombre'].split(',')
            return f"{partes[1].strip()} {partes[0].strip()}" if len(partes) > 1 else f['nombre']

        def plaza_nombre(pid):
            p = next((x for x in plazas_g if x.get('id') == pid), None)
            return p['nombre'] if p else None

        # ── Detectar si preguntan por una PERSONA concreta ────────────────
        # Extraer palabras en mayúsculas/candidatas a nombre propio de la pregunta
        # Eliminamos keywords conocidas para quedarnos solo con el nombre
        _kw_guardia = {'guardia', 'guardias', 'cuando', 'esta', 'está', 'de', 'le', 'toca',
                       'tiene', 'que', 'a', 'el', 'la', 'los', 'las', 'en', 'del', 'al',
                       'semana', 'mes', 'dia', 'hoy', 'mañana', 'manana', 'turno', 'turnos',
                       'quien', 'quién', 'como', 'próxima', 'proxima', 'proximas', 'próximas',
                       'siguiente', 'servicio', 'equipo', 'rotacion', 'rotación', 'marzo',
                       'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
                       'noviembre', 'diciembre', 'enero', 'febrero', 'lunes', 'martes',
                       'miercoles', 'miércoles', 'jueves', 'viernes', 'sabado', 'sábado',
                       'domingo', 'esta', 'este', 'esta', 'ese', 'esa', 'para', 'por',
                       'con', 'sin', 'hay', 'ver', 'dime', 'muestra', 'enseña'}
        _palabras_pregunta = [w for w in re.split(r'[\s,;.?!]+', pregunta) if w]
        _candidatas_nombre = [w for w in _palabras_pregunta if _sin_acentos(w.lower()) not in _kw_guardia and len(w) > 1]

        func_persona = None
        if _candidatas_nombre and len(_candidatas_nombre) >= 1:
            # Buscar funcionario cuyo nombre contenga TODAS las palabras candidatas
            cand_norm = [_sin_acentos(w.upper()) for w in _candidatas_nombre]
            mejor_score = 0
            for f in funcionarios:
                fn_norm = _sin_acentos(f['nombre'].upper()).replace(',', '')
                fn_words = set(fn_norm.split())
                # Contar cuántas palabras candidatas coinciden
                hits = sum(1 for c in cand_norm if c in fn_words)
                if hits >= 1 and hits > mejor_score:
                    # Exigir al menos 1 apellido (>= 1 hit) pero preferir más hits
                    mejor_score = hits
                    func_persona = f
            # Solo aceptar si al menos 1 palabra coincide Y es un score razonable
            if func_persona and mejor_score < 1:
                func_persona = None

        # Si se detectó una persona, buscar sus guardias (reutilizar lógica mi_guardia)
        if func_persona:
            fid_p = func_persona['id']
            dept_p = func_persona.get('dept', '')
            campo_map_p = {'gestion': 'gestorId', 'tramitacion': 'tramitadorId', 'auxilio': 'auxilioId'}
            campo_p = campo_map_p.get(dept_p)
            dept_label_p = {'gestion': 'Gestión', 'tramitacion': 'Tramitación', 'auxilio': 'Auxilio'}.get(dept_p, dept_p)
            partes_np = func_persona['nombre'].split(',')
            nombre_fmt_p = f"{partes_np[1].strip()} {partes_np[0].strip()}" if len(partes_np) > 1 else func_persona['nombre']

            proximas_p = []
            dow_p = hoy.weekday()
            martes_p = hoy - timedelta((dow_p - 1) % 7)
            for i_p in range(16):
                sem_m = martes_p + timedelta(weeks=i_p)
                wk_p = sem_m.isoformat()
                gs_p = guardias_sem.get(wk_p, {})
                if not gs_p:
                    continue
                roles_p = []
                if campo_p and gs_p.get(campo_p) == fid_p:
                    roles_p.append(dept_label_p)
                if gs_p.get('fiscalId') == fid_p:
                    roles_p.append('Apoyo Fiscal')
                for d2p, c2p in campo_map_p.items():
                    if d2p != dept_p and gs_p.get(c2p) == fid_p:
                        lbl2p = {'gestion': 'Gestión', 'tramitacion': 'Tramitación', 'auxilio': 'Auxilio'}.get(d2p, d2p)
                        if lbl2p not in roles_p:
                            roles_p.append(lbl2p)
                if roles_p:
                    fin_p = sem_m + timedelta(6)
                    rango_p = f"{sem_m.strftime('%d/%m')} – {fin_p.strftime('%d/%m/%Y')}"
                    proximas_p.append((rango_p, ', '.join(roles_p)))

            if proximas_p:
                lineas_p = [f"🛡️ Guardias de {nombre_fmt_p} ({dept_label_p}):"]
                for rng, rol in proximas_p[:8]:
                    lineas_p.append(f"  📅 {rng} — {rol}")
                if len(proximas_p) > 8:
                    lineas_p.append(f"  ... y {len(proximas_p) - 8} más")
                respuesta = '\n'.join(lineas_p)
            else:
                respuesta = f"No encontré guardias asignadas para {nombre_fmt_p} en las próximas 16 semanas."
            contexto_groq = respuesta
            accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}
        # Si no se detectó persona, consulta genérica (semana/mes)
        if not func_persona:
            def _fmt_guardia_semana(martes_d, g_sem):
                """Formatea una semana de guardia en líneas de texto."""
                rango = f"{martes_d.strftime('%d/%m')} – {(martes_d + timedelta(6)).strftime('%d/%m/%Y')}"
                ls = [f"📅 Semana {rango}:"]
                if g_sem.get('gestorId'):     ls.append(f"  • Gestión:     {nombre_f(g_sem['gestorId'])}")
                if g_sem.get('tramitadorId'): ls.append(f"  • Tramitación: {nombre_f(g_sem['tramitadorId'])}")
                if g_sem.get('auxilioId'):    ls.append(f"  • Auxilio:     {nombre_f(g_sem['auxilioId'])}")
                if g_sem.get('fiscalId'):    ls.append(f"  • Apoyo Fiscal: {nombre_f(g_sem['fiscalId'])}")
                pn = plaza_nombre(g_sem.get('plazaId'))
                if pn: ls.append(f"  🏛️ {pn}")
                return ls, rango

            # Determinar fecha de referencia
            fd = date.fromisoformat(fecha_str) if fecha_str else hoy

            # ¿Consulta multi-semana? (mes o varias semanas)
            if mes_info:
                anyo, mes_n = mes_info
                primer_dia = date(anyo, mes_n, 1)
                if mes_n == 12:
                    ultimo_dia = date(anyo + 1, 1, 1) - timedelta(1)
                else:
                    ultimo_dia = date(anyo, mes_n + 1, 1) - timedelta(1)
                d = primer_dia
                dow_d = d.weekday()
                martes_d = d - timedelta((dow_d - 1) % 7)
                semanas_vistas = set()
                all_lineas = []
                _meses_es = ['enero','febrero','marzo','abril','mayo','junio',
                             'julio','agosto','septiembre','octubre','noviembre','diciembre']
                while martes_d <= ultimo_dia:
                    wk = martes_d.isoformat()
                    if wk not in semanas_vistas:
                        semanas_vistas.add(wk)
                        gs = guardias_sem.get(wk, {})
                        if gs:
                            ls, _ = _fmt_guardia_semana(martes_d, gs)
                            all_lineas.extend(ls)
                            all_lineas.append('')
                    martes_d += timedelta(7)
                if all_lineas:
                    respuesta = f"🛡️ Guardias de {_meses_es[mes_n-1]} {anyo}:\n\n" + '\n'.join(all_lineas)
                else:
                    respuesta = f"No hay guardias asignadas para {_meses_es[mes_n-1]} {anyo}."
                contexto_groq = respuesta
            else:
                # Consulta de una semana / día concreto
                dow = fd.weekday()
                martes = fd - timedelta((dow - 1) % 7)
                wk = martes.isoformat()
                g = guardias_sem.get(wk, {})

                # Comprobar diaOverride para el día concreto
                g_final = g.copy() if g else {}
                if fecha_str and fecha_str in dia_overrides:
                    ov = dia_overrides[fecha_str]
                    for k in ('gestorId', 'tramitadorId', 'auxilioId', 'fiscalId', 'plazaId'):
                        if k in ov:
                            g_final[k] = ov[k]

                if g_final:
                    ls, rango_txt = _fmt_guardia_semana(martes, g_final)
                    if fecha_str and fecha_str in dia_overrides:
                        ls.insert(1, f"  ✏️ (asignación específica del día {fd.strftime('%d/%m')})")
                    respuesta = '\n'.join(ls)
                    contexto_groq = (
                        f"Guardia semana {rango_txt}:\n"
                        f"Gestión:     {nombre_f(g_final.get('gestorId'))}\n"
                        f"Tramitación: {nombre_f(g_final.get('tramitadorId'))}\n"
                        f"Auxilio:     {nombre_f(g_final.get('auxilioId'))}"
                    )
                else:
                    rango_txt = f"{martes.strftime('%d/%m')} – {(martes + timedelta(6)).strftime('%d/%m/%Y')}"
                    respuesta = f"No hay datos de guardia para la semana {rango_txt}."
                    contexto_groq = f"Sin datos de guardia para la semana {rango_txt}."

        accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}

    # ── ASIGNAR / PONER GUARDIA ─────────────────────────────────────────────
    elif intencion == 'asignar_guardia':
        g_datos = _consultar_guardias()
        funcionarios = g_datos.get('funcionarios', [])
        guardias_sem = g_datos.get('guardias', {})

        def _nombre_f_g(fid):
            f = next((x for x in funcionarios if x.get('id') == fid), None)
            if not f: return '—'
            p = f['nombre'].split(',')
            return f"{p[1].strip()} {p[0].strip()}" if len(p) > 1 else f['nombre']

        # Detectar rol mencionado
        t_low = pregunta.lower()
        rol_detectado = None
        rol_campo = None
        for _rlabel, _rcampo, _rpat in [
            ('Gestión', 'gestorId', r'\bgesti[oó]n\b|\bgestor\b'),
            ('Tramitación', 'tramitadorId', r'\btramitaci[oó]n\b|\btramitador\b'),
            ('Auxilio', 'auxilioId', r'\bauxilio\b|\bauxiliar\b'),
            ('Apoyo Fiscal', 'fiscalId', r'\bfiscal\b|\bapoyo fiscal\b'),
        ]:
            if re.search(_rpat, t_low):
                rol_detectado = _rlabel
                rol_campo = _rcampo
                break

        # Detectar persona mencionada
        _kw_asig = {'asigna', 'asignar', 'pon', 'poner', 'cambia', 'cambiar', 'modifica',
                     'modificar', 'guardia', 'guardias', 'de', 'a', 'el', 'la', 'los', 'las',
                     'en', 'del', 'al', 'para', 'semana', 'esta', 'proxima', 'próxima',
                     'gestion', 'gestión', 'gestor', 'tramitacion', 'tramitación', 'tramitador',
                     'auxilio', 'auxiliar', 'fiscal', 'apoyo', 'meter', 'fijar', 'fija', 'mete',
                     'que', 'como', 'poner'}
        _pals_asig = [w for w in re.split(r'[\s,;.?!]+', pregunta) if w]
        _cands_asig = [w for w in _pals_asig if _sin_acentos(w.lower()) not in _kw_asig and len(w) > 1]

        func_asig = None
        if _cands_asig:
            cn = [_sin_acentos(w.upper()) for w in _cands_asig]
            mejor = 0
            for f in funcionarios:
                if not f.get('activo'): continue
                fn = _sin_acentos(f['nombre'].upper()).replace(',', '')
                fw = set(fn.split())
                hits = sum(1 for c in cn if c in fw)
                if hits >= 1 and hits > mejor:
                    mejor = hits
                    func_asig = f

        # Determinar semana
        fd_g = date.fromisoformat(fecha_str) if fecha_str else hoy
        dow_g = fd_g.weekday()
        martes_g = fd_g - timedelta((dow_g - 1) % 7)
        wk_g = martes_g.isoformat()
        rango_g = f"{martes_g.strftime('%d/%m')} – {(martes_g + timedelta(6)).strftime('%d/%m/%Y')}"

        if not func_asig:
            respuesta = (
                f"¿A quién quieres asignar la guardia de la semana {rango_g}?\n"
                f"Indica nombre y rol (gestión/tramitación/auxilio).\n"
                f"Ejemplo: «asigna guardia de gestión a Ferreiros la semana del 24»"
            )
        elif not rol_campo:
            # Auto-detectar rol por departamento del funcionario
            dept_a = func_asig.get('dept', '')
            if dept_a:
                _dm = {'gestion': ('Gestión', 'gestorId'), 'tramitacion': ('Tramitación', 'tramitadorId'),
                       'auxilio': ('Auxilio', 'auxilioId')}
                if dept_a in _dm:
                    rol_detectado, rol_campo = _dm[dept_a]
            if not rol_campo:
                pn = func_asig['nombre'].split(',')
                nf = f"{pn[1].strip()} {pn[0].strip()}" if len(pn) > 1 else func_asig['nombre']
                respuesta = (
                    f"¿En qué rol asigno a {nf} la semana {rango_g}?\n"
                    f"Opciones: gestión, tramitación, auxilio, fiscal."
                )
                accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}
                contexto_groq = respuesta
        if func_asig and rol_campo:
            pn = func_asig['nombre'].split(',')
            nf = f"{pn[1].strip()} {pn[0].strip()}" if len(pn) > 1 else func_asig['nombre']
            # Verificar si ya hay alguien asignado
            gs_actual = guardias_sem.get(wk_g, {})
            anterior = _nombre_f_g(gs_actual.get(rol_campo)) if gs_actual.get(rol_campo) else None
            # Ejecutar asignación
            ruta_g = _resolver_fichero_modulo('guardias', F_GUARDIAS)
            with editar_json(ruta_g) as datos_g:
                gss = datos_g.setdefault('guardias', {})
                sem_data = gss.setdefault(wk_g, {})
                sem_data[rol_campo] = func_asig['id']
                hacer_backup('guardias', datos_g)
            if anterior and anterior != '—':
                respuesta = (
                    f"✅ Guardia de **{rol_detectado}** semana {rango_g}:\n"
                    f"  Anterior: {anterior}\n"
                    f"  Nuevo: **{nf}**"
                )
            else:
                respuesta = f"✅ Guardia de **{rol_detectado}** asignada a **{nf}** — semana {rango_g}."
            contexto_groq = respuesta
        accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}

    # ── QUITAR GUARDIA ───────────────────────────────────────────────────────
    elif intencion == 'quitar_guardia':
        g_datos = _consultar_guardias()
        funcionarios = g_datos.get('funcionarios', [])
        guardias_sem = g_datos.get('guardias', {})

        def _nombre_f_q(fid):
            f = next((x for x in funcionarios if x.get('id') == fid), None)
            if not f: return '—'
            p = f['nombre'].split(',')
            return f"{p[1].strip()} {p[0].strip()}" if len(p) > 1 else f['nombre']

        t_low = pregunta.lower()
        rol_q = None
        rol_campo_q = None
        for _rl, _rc, _rp in [
            ('Gestión', 'gestorId', r'\bgesti[oó]n\b|\bgestor\b'),
            ('Tramitación', 'tramitadorId', r'\btramitaci[oó]n\b|\btramitador\b'),
            ('Auxilio', 'auxilioId', r'\bauxilio\b|\bauxiliar\b'),
            ('Apoyo Fiscal', 'fiscalId', r'\bfiscal\b|\bapoyo fiscal\b'),
        ]:
            if re.search(_rp, t_low):
                rol_q = _rl
                rol_campo_q = _rc
                break

        fd_q = date.fromisoformat(fecha_str) if fecha_str else hoy
        dow_q = fd_q.weekday()
        martes_q = fd_q - timedelta((dow_q - 1) % 7)
        wk_q = martes_q.isoformat()
        rango_q = f"{martes_q.strftime('%d/%m')} – {(martes_q + timedelta(6)).strftime('%d/%m/%Y')}"

        if not rol_campo_q:
            respuesta = (
                f"¿Qué rol quieres vaciar de la semana {rango_q}?\n"
                f"Opciones: gestión, tramitación, auxilio, fiscal.\n"
                f"Ejemplo: «quita guardia de gestión de esta semana»"
            )
        else:
            gs_q = guardias_sem.get(wk_q, {})
            anterior_q = _nombre_f_q(gs_q.get(rol_campo_q)) if gs_q.get(rol_campo_q) else None
            if not anterior_q or anterior_q == '—':
                respuesta = f"No hay nadie asignado en **{rol_q}** la semana {rango_q}."
            else:
                ruta_gq = _resolver_fichero_modulo('guardias', F_GUARDIAS)
                with editar_json(ruta_gq) as datos_gq:
                    gss_q = datos_gq.get('guardias', {})
                    if wk_q in gss_q and rol_campo_q in gss_q[wk_q]:
                        del gss_q[wk_q][rol_campo_q]
                    hacer_backup('guardias', datos_gq)
                respuesta = f"✅ Guardia de **{rol_q}** eliminada — semana {rango_q}.\n  Anterior: {anterior_q}"
        accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}
        contexto_groq = respuesta

    # ── INTERCAMBIAR GUARDIA ─────────────────────────────────────────────────
    elif intencion == 'intercambiar_guardia':
        g_datos = _consultar_guardias()
        funcionarios = g_datos.get('funcionarios', [])
        guardias_sem = g_datos.get('guardias', {})

        def _nombre_f_i(fid):
            f = next((x for x in funcionarios if x.get('id') == fid), None)
            if not f: return '—'
            p = f['nombre'].split(',')
            return f"{p[1].strip()} {p[0].strip()}" if len(p) > 1 else f['nombre']

        # Detectar dos personas y rol
        t_low = pregunta.lower()
        rol_i = None
        rol_campo_i = None
        for _rl, _rc, _rp in [
            ('Gestión', 'gestorId', r'\bgesti[oó]n\b|\bgestor\b'),
            ('Tramitación', 'tramitadorId', r'\btramitaci[oó]n\b|\btramitador\b'),
            ('Auxilio', 'auxilioId', r'\bauxilio\b|\bauxiliar\b'),
            ('Apoyo Fiscal', 'fiscalId', r'\bfiscal\b|\bapoyo fiscal\b'),
        ]:
            if re.search(_rp, t_low):
                rol_i = _rl
                rol_campo_i = _rc
                break

        # Extraer dos semanas si se mencionan (ej: "intercambia guardia semana 24 con semana 31")
        fechas_mencionadas = re.findall(r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b', pregunta)
        semanas_i = []
        for dm, mm, ym in fechas_mencionadas[:2]:
            y = int(ym) if ym else hoy.year
            if y < 100: y += 2000
            try:
                fd_i = date(y, int(mm), int(dm))
                dow_i = fd_i.weekday()
                m_i = fd_i - timedelta((dow_i - 1) % 7)
                semanas_i.append(m_i)
            except ValueError:
                pass

        if len(semanas_i) < 2:
            # Intentar con "semana del X" y "con semana del Y" o "esta semana con la próxima"
            if re.search(r'\besta semana\b.*\bpr[oó]xima\b|\bpr[oó]xima\b.*\besta semana\b', t_low):
                lun = hoy - timedelta(hoy.weekday())
                mar1 = lun + timedelta(1) if lun.weekday() == 0 else lun - timedelta((lun.weekday() - 1) % 7)
                mar1 = hoy - timedelta((hoy.weekday() - 1) % 7)
                mar2 = mar1 + timedelta(7)
                semanas_i = [mar1, mar2]

        if len(semanas_i) >= 2 and rol_campo_i:
            wk1, wk2 = semanas_i[0].isoformat(), semanas_i[1].isoformat()
            gs1 = guardias_sem.get(wk1, {})
            gs2 = guardias_sem.get(wk2, {})
            p1 = gs1.get(rol_campo_i)
            p2 = gs2.get(rol_campo_i)
            if not p1 and not p2:
                respuesta = f"No hay nadie asignado en **{rol_i}** en ninguna de las dos semanas."
            else:
                ruta_gi = _resolver_fichero_modulo('guardias', F_GUARDIAS)
                with editar_json(ruta_gi) as datos_gi:
                    gss_i = datos_gi.setdefault('guardias', {})
                    s1 = gss_i.setdefault(wk1, {})
                    s2 = gss_i.setdefault(wk2, {})
                    s1[rol_campo_i], s2[rol_campo_i] = p2, p1
                    hacer_backup('guardias', datos_gi)
                n1 = _nombre_f_i(p1) if p1 else '(vacío)'
                n2 = _nombre_f_i(p2) if p2 else '(vacío)'
                r1 = f"{semanas_i[0].strftime('%d/%m')}"
                r2 = f"{semanas_i[1].strftime('%d/%m')}"
                respuesta = (
                    f"✅ Intercambio de **{rol_i}** realizado:\n"
                    f"  Semana {r1}: {n1} → {n2}\n"
                    f"  Semana {r2}: {n2} → {n1}"
                )
        else:
            respuesta = (
                "Para intercambiar guardias necesito:\n"
                "  • Rol (gestión/tramitación/auxilio/fiscal)\n"
                "  • Dos semanas (ej: «esta semana con la próxima»)\n\n"
                "Ejemplo: «intercambia guardia de gestión esta semana con la próxima»"
            )
        accion = {'tipo': 'navegar_modulo', 'modulo': 'guardias'}
        contexto_groq = respuesta

    # ── CREAR / REGISTRAR AUSENCIA ───────────────────────────────────────────
    elif intencion == 'crear_ausencia':
        adata = cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)) or {}
        plazas_aus = adata.get('plazas', [])

        # Extraer persona mencionada
        _kw_aus = {'registra', 'registrar', 'crea', 'crear', 'ausencia', 'ausencias', 'añade',
                    'añadir', 'pon', 'poner', 'nueva', 'nuevo', 'anotar', 'meter', 'de', 'a',
                    'el', 'la', 'los', 'las', 'del', 'al', 'para', 'que', 'desde', 'hasta',
                    'plaza', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
                    'octubre', 'noviembre', 'diciembre', 'enero', 'febrero', 'falta', 'ausente'}
        _pals_aus = [w for w in re.split(r'[\s,;.?!]+', pregunta) if w]
        _cands_aus = [w for w in _pals_aus if _sin_acentos(w.lower()) not in _kw_aus and len(w) > 2]

        # Extraer dos fechas (inicio y fin)
        fecha_inicio_aus = fecha_str
        fecha_fin_aus = None
        # Buscar "del X al Y" o "desde X hasta Y"
        m_rango = re.search(
            r'(?:del?\s+)?(\d{1,2})\s*(?:de\s+)?(?:' + '|'.join(_MESES_ES) + r')?\s*'
            r'(?:al?|hasta)\s+(\d{1,2})\s*(?:de\s+)?(' + '|'.join(_MESES_ES) + r')',
            pregunta.lower())
        if m_rango:
            d1, d2, mes_txt = int(m_rango.group(1)), int(m_rango.group(2)), m_rango.group(3)
            mes_n = _MESES_ES.get(mes_txt, hoy.month)
            year_a = hoy.year
            try:
                fecha_inicio_aus = date(year_a, mes_n, d1).isoformat()
                fecha_fin_aus = date(year_a, mes_n, d2).isoformat()
            except ValueError:
                pass
        elif fecha_str:
            # Si solo hay una fecha, asumir 1 día
            fecha_fin_aus = fecha_str

        # Intentar detectar plaza
        plaza_aus = _extraer_plaza(pregunta, [p.get('nombre', '') for p in plazas_aus])

        # Detectar motivo
        motivo_aus = ''
        for _mot_pat, _mot_txt in [
            (r'\bvacaciones?\b', 'Vacaciones'), (r'\bbaja\b|\bi\.?t\.?\b|\bincapacidad\b', 'IT/Baja'),
            (r'\bpermiso\b|\basuntos propios\b', 'Permiso/Asuntos propios'),
            (r'\bformaci[oó]n\b|\bcurso\b', 'Formación'), (r'\bcomisi[oó]n\b', 'Comisión de servicio'),
        ]:
            if re.search(_mot_pat, pregunta.lower()):
                motivo_aus = _mot_txt
                break

        nombre_persona = ' '.join(_cands_aus) if _cands_aus else ''

        if not nombre_persona and not plaza_aus:
            respuesta = (
                "Para registrar una ausencia necesito al menos:\n"
                "  • Nombre de la persona\n"
                "  • Fechas (del X al Y de mes)\n\n"
                "Ejemplo: «registra ausencia de Pedro García del 20 al 24 de marzo por vacaciones»"
            )
        elif not fecha_inicio_aus:
            respuesta = (
                f"¿Desde cuándo hasta cuándo es la ausencia de {nombre_persona}?\n"
                f"Ejemplo: «del 20 al 24 de marzo»"
            )
        else:
            # Buscar plaza y cargo que coincidan con el nombre
            plaza_match = None
            cargo_match = None
            if nombre_persona:
                np_norm = _sin_acentos(nombre_persona.upper())
                np_words = set(np_norm.split())
                for p in plazas_aus:
                    for c in p.get('cargos', []):
                        titular_norm = _sin_acentos((c.get('titular', '') or p.get('nombre', '')).upper())
                        t_words = set(titular_norm.replace(',', '').split())
                        common = np_words & t_words
                        if common and len(common) >= 1:
                            plaza_match = p
                            cargo_match = c
                            break
                    if cargo_match:
                        break

            # Crear la ausencia
            nueva_aus = {
                'id': int(datetime.now().timestamp() * 1000),
                'plazaId': plaza_match['id'] if plaza_match else '',
                'cargoId': cargo_match['id'] if cargo_match else '',
                'titular': nombre_persona,
                'fechaInicio': fecha_inicio_aus,
                'fechaFin': fecha_fin_aus or fecha_inicio_aus,
                'motivo': motivo_aus,
                'sustituto': '',
                'registradoPor': uid or '',
                'fechaRegistro': datetime.now().isoformat(),
            }
            ruta_aus = _resolver_fichero_modulo('ausencias', F_AUSENCIAS)
            with editar_json(ruta_aus) as datos_aus:
                datos_aus.setdefault('ausencias', []).append(nueva_aus)
                hacer_backup('ausencias', datos_aus)

            fi = _fmt_fecha(fecha_inicio_aus)
            ff = _fmt_fecha(fecha_fin_aus) if fecha_fin_aus and fecha_fin_aus != fecha_inicio_aus else ''
            rango_txt = f"{fi} — {ff}" if ff else fi
            plaza_txt = f" ({plaza_match['nombre']})" if plaza_match else ''
            mot_txt = f"\n  Motivo: {motivo_aus}" if motivo_aus else ''
            respuesta = (
                f"✅ Ausencia registrada:\n"
                f"  Persona: **{nombre_persona}**{plaza_txt}\n"
                f"  Periodo: {rango_txt}{mot_txt}"
            )
        accion = {'tipo': 'navegar_modulo', 'modulo': 'ausencias'}
        contexto_groq = respuesta

    # ── CANCELAR / QUITAR AUSENCIA ───────────────────────────────────────────
    elif intencion == 'cancelar_ausencia':
        adata_c = cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)) or {}
        todas_aus_c = adata_c.get('ausencias', [])
        hoy_str_c = hoy.isoformat()

        # Buscar nombre de persona
        _kw_canc = {'cancela', 'cancelar', 'quita', 'quitar', 'elimina', 'eliminar', 'borra',
                     'borrar', 'anula', 'anular', 'ausencia', 'ausencias', 'de', 'a', 'el', 'la',
                     'los', 'las', 'del', 'al', 'para'}
        _pals_canc = [w for w in re.split(r'[\s,;.?!]+', pregunta) if w]
        _cands_canc = [w for w in _pals_canc if _sin_acentos(w.lower()) not in _kw_canc and len(w) > 2]
        nombre_canc = ' '.join(_cands_canc) if _cands_canc else ''

        # Buscar ausencias activas que coincidan
        candidatas = []
        if nombre_canc:
            nc_norm = _sin_acentos(nombre_canc.upper())
            nc_words = set(nc_norm.split())
            for a in todas_aus_c:
                if a.get('fechaFin', '') >= hoy_str_c:
                    t_norm = _sin_acentos(a.get('titular', '').upper())
                    t_words = set(t_norm.replace(',', '').split())
                    if nc_words & t_words:
                        candidatas.append(a)
        else:
            # Sin nombre: mostrar activas
            candidatas = [a for a in todas_aus_c if a.get('fechaFin', '') >= hoy_str_c]

        if not candidatas:
            respuesta = f"No encontré ausencias activas{' de ' + nombre_canc if nombre_canc else ''}."
        elif len(candidatas) == 1:
            aus_del = candidatas[0]
            ruta_aus_c = _resolver_fichero_modulo('ausencias', F_AUSENCIAS)
            with editar_json(ruta_aus_c) as datos_aus_c:
                datos_aus_c['ausencias'] = [a for a in datos_aus_c.get('ausencias', [])
                                            if a.get('id') != aus_del.get('id')]
                hacer_backup('ausencias', datos_aus_c)
            respuesta = (
                f"✅ Ausencia cancelada:\n"
                f"  {aus_del.get('titular', '?')} — "
                f"{aus_del.get('fechaInicio', '')} a {aus_del.get('fechaFin', '')}"
            )
        else:
            lineas_c = [f"Hay {len(candidatas)} ausencias que coinciden:"]
            for i, a in enumerate(candidatas[:5], 1):
                lineas_c.append(f"  {i}. {a.get('titular', '?')} — {a.get('fechaInicio', '')} a {a.get('fechaFin', '')}")
            lineas_c.append("\nSé más específico indicando nombre y fecha.")
            respuesta = '\n'.join(lineas_c)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'ausencias'}
        contexto_groq = respuesta

    # ── HISTORIAL DE AUSENCIAS ───────────────────────────────────────────────
    elif intencion == 'historial_ausencias':
        adata_h = cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)) or {}
        todas_aus_h = adata_h.get('ausencias', [])
        plazas_h = adata_h.get('plazas', [])
        plazas_map_h = {p['id']: p.get('nombre', '?') for p in plazas_h}

        # Filtrar por persona o plaza
        _kw_hist = {'historial', 'historico', 'histórico', 'ausencia', 'ausencias', 'pasadas',
                     'anteriores', 'todas', 'de', 'el', 'la', 'los', 'las', 'del', 'al'}
        _pals_h = [w for w in re.split(r'[\s,;.?!]+', pregunta) if w]
        _cands_h = [w for w in _pals_h if _sin_acentos(w.lower()) not in _kw_hist and len(w) > 2]
        nombre_h = ' '.join(_cands_h) if _cands_h else ''

        filtro_h = todas_aus_h
        if nombre_h:
            nh_norm = _sin_acentos(nombre_h.upper())
            nh_words = set(nh_norm.split())
            filtro_h = []
            for a in todas_aus_h:
                t_norm = _sin_acentos(a.get('titular', '').upper())
                t_words = set(t_norm.replace(',', '').split())
                if nh_words & t_words:
                    filtro_h.append(a)
        # Filtrar por año si se menciona
        year_h = None
        m_year = re.search(r'\b(20\d{2})\b', pregunta)
        if m_year:
            year_h = m_year.group(1)
            filtro_h = [a for a in filtro_h if a.get('fechaInicio', '').startswith(year_h)]

        filtro_h = sorted(filtro_h, key=lambda a: a.get('fechaInicio', ''), reverse=True)

        if not filtro_h:
            etiq_h = f" de {nombre_h}" if nombre_h else ''
            etiq_h += f" en {year_h}" if year_h else ''
            respuesta = f"No encontré ausencias{etiq_h}."
        else:
            etiq_h = f" de {nombre_h}" if nombre_h else ''
            etiq_h += f" en {year_h}" if year_h else ''
            lineas_h = [f"📋 Historial de ausencias{etiq_h} ({len(filtro_h)}):"]
            for a in filtro_h[:15]:
                titular_h = a.get('titular', '?')
                fi_h = a.get('fechaInicio', '?')
                ff_h = a.get('fechaFin', '?')
                motivo_h = a.get('motivo', '')
                plaza_n_h = plazas_map_h.get(a.get('plazaId'), '')
                txt_h = f"  • {titular_h} — {fi_h} a {ff_h}"
                if motivo_h: txt_h += f" ({motivo_h})"
                if plaza_n_h: txt_h += f" [{plaza_n_h}]"
                lineas_h.append(txt_h)
            if len(filtro_h) > 15:
                lineas_h.append(f"  … y {len(filtro_h) - 15} más")
            respuesta = '\n'.join(lineas_h)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'ausencias'}
        contexto_groq = respuesta

    # ── E4: PUBLICAR EN TABLÓN ──────────────────────────────────────────────
    elif intencion == 'publicar_tablon':
        # Extraer título y cuerpo del texto del usuario
        # Patrón: "publica en el tablón: TÍTULO" o "publica en el tablón que TÍTULO"
        txt_pub = re.sub(
            r'^.*?(publica[r]?|pon[er]?|colga[r]?|escrib[eir]*)\s*(en\s+)?(el\s+)?tabl[oó]n\s*(que\s*|:\s*)?',
            '', pregunta, flags=re.IGNORECASE).strip()
        if not txt_pub:
            txt_pub = re.sub(
                r'^.*?(nuevo aviso|poner aviso|publicar aviso)\s*(:\s*)?',
                '', pregunta, flags=re.IGNORECASE).strip()
        if not txt_pub or len(txt_pub) < 3:
            respuesta = "📌 Para publicar en el tablón, dime el contenido. Ejemplo:\n" \
                       "«Publica en el tablón: Mañana no hay atención al público por la tarde»"
        else:
            # Detectar categoría
            cat = 'informativo'
            if re.search(r'\burgente\b|\bimportante\b|\bcr[ií]tic', _sin_acentos(txt_pub.lower())):
                cat = 'urgente'
            elif re.search(r'\brecordatorio\b|\brecuerda\b|\bno olvidar\b', _sin_acentos(txt_pub.lower())):
                cat = 'recordatorio'
            # Título = primera línea o primeros 80 chars
            lineas = txt_pub.split('\n', 1)
            titulo = lineas[0][:80]
            cuerpo = lineas[1].strip() if len(lineas) > 1 else ''
            uid_pub = _uid_activo_actual()
            u_pub = _usuario_por_id(uid_pub) if uid_pub else {}
            nuevo_anuncio = {
                'id':        str(_uuid.uuid4()),
                'autor':     uid_pub or 'asistente',
                'autor_nombre': u_pub.get('nombre', 'Asistente IA'),
                'autor_avatar': u_pub.get('avatar', '🤖'),
                'fecha':     datetime.now().strftime('%Y-%m-%dT%H:%M'),
                'titulo':    titulo,
                'cuerpo':    cuerpo,
                'categoria': cat,
                'fijado':    False,
                'caduca':    None,
                'leido_por': [uid_pub] if uid_pub else [],
                'activo':    True
            }
            with editar_json(F_TABLON) as datos_tb:
                datos_tb.setdefault('anuncios', [])
                datos_tb['anuncios'].append(nuevo_anuncio)
            # Notificar a todos
            todos_usr = _listar_usuarios()
            for usr in todos_usr:
                if usr.get('id') != uid_pub and usr.get('rol') != 'superadmin':
                    _crear_notificacion(usr['id'], 'tablon',
                        f"📌 Nuevo aviso: {titulo[:50]}", enlace='tablon')
            emoji_cat = {'urgente': '🔴', 'informativo': 'ℹ️', 'recordatorio': '⏰'}.get(cat, 'ℹ️')
            respuesta = f"✅ Publicado en el tablón:\n\n{emoji_cat} **{titulo}**"
            if cuerpo:
                respuesta += f"\n{cuerpo[:100]}"
            respuesta += f"\n\nCategoría: {cat} · Visible para todos los usuarios."
        contexto_groq = respuesta

    # ── E4: CONSULTAR TABLÓN ────────────────────────────────────────────────
    elif intencion == 'consultar_tablon':
        datos_tb = _cargar_tablon()
        hoy_tb = datetime.now().strftime('%Y-%m-%d')
        anuncios = [a for a in datos_tb.get('anuncios', [])
                    if a.get('activo', True) and (not a.get('caduca') or a['caduca'] >= hoy_tb)]
        # Ordenar: fijados primero, luego recientes
        fijados = [a for a in anuncios if a.get('fijado')]
        no_fijados = [a for a in anuncios if not a.get('fijado')]
        fijados.sort(key=lambda a: a.get('fecha', ''), reverse=True)
        no_fijados.sort(key=lambda a: a.get('fecha', ''), reverse=True)
        todos_tb = fijados + no_fijados
        if not todos_tb:
            respuesta = "📌 El tablón está vacío. No hay avisos publicados actualmente."
        else:
            uid_tb = _uid_activo_actual()
            emoji_cat = {'urgente': '🔴', 'informativo': 'ℹ️', 'recordatorio': '⏰'}
            lineas_tb = [f"📌 **Tablón de anuncios** ({len(todos_tb)} aviso{'s' if len(todos_tb)>1 else ''}):\n"]
            for i, a in enumerate(todos_tb[:10]):
                pin = '📌 ' if a.get('fijado') else ''
                cat_e = emoji_cat.get(a.get('categoria', ''), 'ℹ️')
                leido = '✓' if uid_tb in a.get('leido_por', []) else '🆕'
                fecha_a = a.get('fecha', '')[:10]
                lineas_tb.append(f"{i+1}. {pin}{cat_e} **{a.get('titulo', '')}** — {a.get('autor_nombre', '')} ({fecha_a}) {leido}")
                if a.get('cuerpo'):
                    lineas_tb.append(f"   _{a['cuerpo'][:80]}{'…' if len(a.get('cuerpo',''))>80 else ''}_")
            if len(todos_tb) > 10:
                lineas_tb.append(f"\n… y {len(todos_tb)-10} aviso(s) más. Abre la pestaña 📌 Tablón para verlos todos.")
            respuesta = '\n'.join(lineas_tb)
        contexto_groq = respuesta

    # ── E4: BUSCAR EN TABLÓN ────────────────────────────────────────────────
    elif intencion == 'buscar_tablon':
        q_tb = re.sub(
            r'\b(busca[r]?|en\s+el|tabl[oó]n|aviso[s]?|anuncio[s]?|de[l]?|el|la|los|las)\b',
            '', pregunta, flags=re.IGNORECASE).strip()
        q_tb = re.sub(r'\s+', ' ', q_tb).strip()
        if len(q_tb) < 2:
            respuesta = "🔍 Dime qué quieres buscar en el tablón. Ejemplo: «Busca en el tablón vacaciones»"
        else:
            datos_tb = _cargar_tablon()
            q_tb_low = _sin_acentos(q_tb.lower())
            resultados_tb = []
            for a in datos_tb.get('anuncios', []):
                if not a.get('activo', True):
                    continue
                texto_a = _sin_acentos(f"{a.get('titulo','')} {a.get('cuerpo','')}".lower())
                if q_tb_low in texto_a:
                    resultados_tb.append(a)
            if not resultados_tb:
                respuesta = f"🔍 No encontré avisos en el tablón que contengan «{q_tb}»."
            else:
                emoji_cat = {'urgente': '🔴', 'informativo': 'ℹ️', 'recordatorio': '⏰'}
                lineas_tb = [f"🔍 Encontré {len(resultados_tb)} aviso(s) con «{q_tb}»:\n"]
                for i, a in enumerate(resultados_tb[:8]):
                    cat_e = emoji_cat.get(a.get('categoria', ''), 'ℹ️')
                    lineas_tb.append(f"{i+1}. {cat_e} **{a.get('titulo', '')}** — {a.get('autor_nombre', '')} ({a.get('fecha','')[:10]})")
                respuesta = '\n'.join(lineas_tb)
        contexto_groq = respuesta

    # ── E4: VER NOTIFICACIONES ──────────────────────────────────────────────
    elif intencion == 'ver_notificaciones':
        uid_n = _uid_activo_actual()
        if not uid_n:
            respuesta = "⚠️ No hay usuario activo para consultar notificaciones."
        else:
            datos_n = _cargar_notificaciones()
            mis_n = datos_n.get(uid_n, [])
            sin_leer_n = [n for n in mis_n if not n.get('leida')]
            if not sin_leer_n:
                respuesta = "🔔 No tienes notificaciones pendientes. ¡Todo al día! ✨"
            else:
                emoji_tipo = {'chat': '💬', 'minuta': '📄', 'tablon': '📌', 'vencimiento': '⏰', 'guardia': '🛡️'}
                lineas_n = [f"🔔 Tienes **{len(sin_leer_n)} notificación(es)** sin leer:\n"]
                for i, n in enumerate(sin_leer_n[:10]):
                    e = emoji_tipo.get(n.get('tipo', ''), '🔔')
                    lineas_n.append(f"{i+1}. {e} {n.get('texto', '')} — _{n.get('fecha','')[:16]}_")
                if len(sin_leer_n) > 10:
                    lineas_n.append(f"\n… y {len(sin_leer_n)-10} más.")
                lineas_n.append("\nPulsa la 🔔 campanita en la barra para verlas todas y marcarlas como leídas.")
                respuesta = '\n'.join(lineas_n)
        contexto_groq = respuesta

    # ── BUSCAR DIR3 ──────────────────────────────────────────────────────────
    elif intencion == 'buscar_dir3':
        # Extraer query: quitar keywords de dir3
        q_dir3 = re.sub(
            r'\b(busca[r]?|dir3|c[oó]digo|organismo|directorio|com[uú]n|unidad|oficina|'
            r'registro|dame|dime|cu[aá]l\s+es|de[l]?|el|la|los|las|buscar)\b',
            '', pregunta, flags=re.IGNORECASE).strip()
        q_dir3 = re.sub(r'\s+', ' ', q_dir3).strip()

        if len(q_dir3) < 2:
            respuesta = "¿Qué organismo buscas? Ejemplo: «DIR3 Ayuntamiento de Vilagarcía»"
        else:
            data_dir3 = _cargar_dir3()
            if not data_dir3 or 'registros' not in data_dir3:
                respuesta = "No hay datos DIR3 cargados. Verifica que el fichero dir3.json existe."
            else:
                palabras_d = _sin_acentos(q_dir3.lower()).split()
                resultados_d = []
                for r in data_dir3['registros']:
                    texto_d = _sin_acentos(' '.join([
                        r.get('co', ''), r.get('cu', ''), r.get('no', ''),
                        r.get('nr', ''), r.get('cm', ''), r.get('pr', ''),
                        ' '.join(r.get('tg', []))
                    ]).lower())
                    if all(p in texto_d for p in palabras_d):
                        resultados_d.append(r)
                    if len(resultados_d) >= 10:
                        break

                if not resultados_d:
                    respuesta = f"🔍 No encontré organismos DIR3 para «{q_dir3}»."
                else:
                    lineas_d = [f"🏢 DIR3 — {len(resultados_d)} resultado(s) para «{q_dir3}»:"]
                    codigos_copiar = []
                    for r in resultados_d[:8]:
                        codigo = r.get('cu') or r.get('co', '')
                        nombre_d = r.get('no', '?')
                        nivel_d = r.get('nv', '')
                        org_d = r.get('nr', '')
                        lineas_d.append(f"\n  📌 **{codigo}** — {nombre_d}")
                        if org_d:
                            lineas_d.append(f"     {org_d}")
                        if nivel_d:
                            lineas_d.append(f"     Nivel: {nivel_d}")
                        codigos_copiar.append(codigo)
                    if len(resultados_d) > 8:
                        lineas_d.append(f"\n  … y {len(resultados_d) - 8} más")
                    lineas_d.append("\n💡 Abre el módulo DIR3 para más detalles y favoritos.")
                    respuesta = '\n'.join(lineas_d)
                    accion = {'tipo': 'navegar_modulo', 'modulo': 'dir3',
                              'copiar': codigos_copiar[0] if codigos_copiar else ''}
        if not accion:
            accion = {'tipo': 'navegar_modulo', 'modulo': 'dir3'}
        contexto_groq = respuesta

    # ── RESUMEN SEMANAL ──────────────────────────────────────────────────────
    elif intencion == 'resumen_semanal':
        # Determinar semana
        if re.search(r'\bpr[oó]xima\b', pregunta.lower()):
            lunes_rs = hoy - timedelta(hoy.weekday()) + timedelta(7)
        else:
            lunes_rs = hoy - timedelta(hoy.weekday())
        viernes_rs = lunes_rs + timedelta(4)
        domingo_rs = lunes_rs + timedelta(6)
        dias_sem = [(lunes_rs + timedelta(i)).isoformat() for i in range(7)]
        rango_rs = f"{lunes_rs.strftime('%d/%m')} — {domingo_rs.strftime('%d/%m/%Y')}"
        es_prox = 'próxima ' if lunes_rs > hoy else ''

        lineas_rs = [f"📋 **Resumen {es_prox}semana {rango_rs}**\n"]

        # 1. Señalamientos
        sen_sem = [s for s in senalamientos
                   if s.get('fecha', '') in dias_sem and not s.get('anulado')]
        celebrados_rs = len([s for s in sen_sem if s.get('celebrado')])
        suspendidos_rs = len([s for s in sen_sem if s.get('suspendido')])
        activos_rs = len(sen_sem) - celebrados_rs - suspendidos_rs
        lineas_rs.append(f"📅 **Señalamientos:** {len(sen_sem)}")
        if sen_sem:
            if activos_rs: lineas_rs.append(f"  • Pendientes: {activos_rs}")
            if celebrados_rs: lineas_rs.append(f"  • Celebrados: {celebrados_rs}")
            if suspendidos_rs: lineas_rs.append(f"  • Suspendidos: {suspendidos_rs}")
            # Desglose por día
            for d in dias_sem[:5]:  # lunes a viernes
                dd = date.fromisoformat(d)
                _dias_es = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']
                sd = [s for s in sen_sem if s.get('fecha') == d]
                if sd:
                    lineas_rs.append(f"  {_dias_es[dd.weekday()]} {dd.strftime('%d/%m')}: {len(sd)} señalamiento(s)")
        else:
            lineas_rs.append("  Sin señalamientos esta semana.")

        # 2. Guardias
        try:
            g_datos_rs = _consultar_guardias()
            funcionarios_rs = g_datos_rs.get('funcionarios', [])
            guardias_sem_rs = g_datos_rs.get('guardias', {})
            martes_rs = lunes_rs + timedelta(1)
            wk_rs = martes_rs.isoformat()
            gs_rs = guardias_sem_rs.get(wk_rs, {})

            def _nf_rs(fid):
                f = next((x for x in funcionarios_rs if x.get('id') == fid), None)
                if not f: return '—'
                p = f['nombre'].split(',')
                return f"{p[1].strip()} {p[0].strip()}" if len(p) > 1 else f['nombre']

            if gs_rs:
                lineas_rs.append(f"\n🛡️ **Guardia:**")
                if gs_rs.get('gestorId'):     lineas_rs.append(f"  • Gestión: {_nf_rs(gs_rs['gestorId'])}")
                if gs_rs.get('tramitadorId'): lineas_rs.append(f"  • Tramitación: {_nf_rs(gs_rs['tramitadorId'])}")
                if gs_rs.get('auxilioId'):    lineas_rs.append(f"  • Auxilio: {_nf_rs(gs_rs['auxilioId'])}")
        except Exception:
            pass

        # 3. Ausencias activas en la semana
        try:
            adata_rs = cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)) or {}
            todas_aus_rs = adata_rs.get('ausencias', [])
            plazas_map_rs = {p['id']: p.get('nombre', '?') for p in adata_rs.get('plazas', [])}
            aus_sem = []
            for a in todas_aus_rs:
                fi = a.get('fechaInicio', '')
                ff = a.get('fechaFin', '9')
                if fi <= domingo_rs.isoformat() and ff >= lunes_rs.isoformat():
                    aus_sem.append(a)
            if aus_sem:
                lineas_rs.append(f"\n🏛️ **Ausencias:** {len(aus_sem)}")
                for a in aus_sem[:5]:
                    pl = plazas_map_rs.get(a.get('plazaId'), '')
                    lineas_rs.append(f"  • {a.get('titular', '?')}{' — ' + pl if pl else ''}")
                if len(aus_sem) > 5:
                    lineas_rs.append(f"  … y {len(aus_sem) - 5} más")
        except Exception:
            pass

        # 4. Vencimientos de la semana
        try:
            v_datos_rs = _consultar_vencimientos(uid, equipo)
            avisos_rs = v_datos_rs.get('avisos', [])
            venc_sem = [a for a in avisos_rs
                        if a.get('estado') != 'vencido' and not a.get('anulado')
                        and lunes_rs.isoformat() <= a.get('ultimoDia', '') <= domingo_rs.isoformat()]
            if venc_sem:
                lineas_rs.append(f"\n⏰ **Vencimientos:** {len(venc_sem)}")
                for v in sorted(venc_sem, key=lambda x: x.get('ultimoDia', ''))[:5]:
                    lineas_rs.append(f"  • {v.get('procedimiento', '—')} — vence {_fmt_fecha(v['ultimoDia'])}")
                if len(venc_sem) > 5:
                    lineas_rs.append(f"  … y {len(venc_sem) - 5} más")
        except Exception:
            pass

        # 5. Comparativa con semana anterior
        lunes_ant = lunes_rs - timedelta(7)
        dias_ant = [(lunes_ant + timedelta(i)).isoformat() for i in range(7)]
        sen_ant = [s for s in senalamientos
                   if s.get('fecha', '') in dias_ant and not s.get('anulado')]
        diff = len(sen_sem) - len(sen_ant)
        if diff > 0:
            lineas_rs.append(f"\n📊 **vs semana anterior:** +{diff} señalamientos ({len(sen_ant)} → {len(sen_sem)})")
        elif diff < 0:
            lineas_rs.append(f"\n📊 **vs semana anterior:** {diff} señalamientos ({len(sen_ant)} → {len(sen_sem)})")
        else:
            lineas_rs.append(f"\n📊 **vs semana anterior:** igual ({len(sen_sem)} señalamientos)")

        respuesta = '\n'.join(lineas_rs)
        accion = {'tipo': 'navegar_agenda', 'fecha': lunes_rs.isoformat()}
        contexto_groq = respuesta

    # ── VENCIMIENTOS ─────────────────────────────────────────────────────────
    elif intencion == 'vencimientos':
        v_datos = _consultar_vencimientos(uid, equipo)
        avisos  = v_datos.get('avisos', [])
        festivos = set(v_datos.get('festivos', []))
        pendientes = [a for a in avisos if a.get('estado') != 'vencido' and not a.get('anulado')]
        if mes_info:
            year, mes = mes_info
            pendientes = [a for a in pendientes if a.get('ultimoDia','')[:7] == f"{year}-{mes:02d}"]
            etiq = f"en {list(_MESES_ES.keys())[mes-1]} de {year}"
        elif fecha_str:
            pendientes = [a for a in pendientes if a.get('ultimoDia','') >= fecha_str]
            etiq = f"desde el {_fmt_fecha(fecha_str)}"
        else:
            etiq = "próximamente"
            pendientes = sorted(pendientes, key=lambda x: x.get('ultimoDia',''))[:10]
        if pendientes:
            lineas = [f"⏰ Vencimientos {etiq}:"]
            for a in sorted(pendientes, key=lambda x: x.get('ultimoDia',''))[:15]:
                proc = a.get('procedimiento') or '—'
                ult  = _fmt_fecha(a['ultimoDia']) if a.get('ultimoDia') else '?'
                lineas.append(f"  • {proc} — vence el {ult}")
            respuesta = '\n'.join(lineas)
            # Contexto para Groq: procedimiento completo + plazo + fechas
            contexto_groq = (
                f"Vencimientos {etiq}: {len(pendientes)} pendientes\n"
                + '\n'.join(
                    f"{a.get('procedimiento') or a.get('tipo','?')} — "
                    f"plazo {a.get('plazoDias','?')} días hábiles — "
                    f"vence {a.get('ultimoDia','?')}"
                    + (f" (alerta 15 días: {a.get('limite15','')})" if a.get('limite15') else '')
                    for a in sorted(pendientes, key=lambda x: x.get('ultimoDia',''))[:10]
                )
            )
        else:
            respuesta = f"No hay vencimientos pendientes {etiq}."
            contexto_groq = f"Sin vencimientos pendientes {etiq}."
        accion = {'tipo': 'navegar_modulo', 'modulo': 'vencimientos'}

    # ── BUSCAR EXPEDIENTE ────────────────────────────────────────────────────
    elif intencion == 'buscar_expediente':
        encontrados = [s for s in senalamientos if s.get('expediente','').strip() == expediente]
        if encontrados:
            lineas = [f"🔍 Expediente {expediente}:"]
            for s in sorted(encontrados, key=lambda x: x.get('fecha','')):
                lineas.append(f"  • {_fmt_fecha(s['fecha'])} — {s.get('hora','')} — {s.get('plaza','')} — {s.get('tipo','')}")
            respuesta = '\n'.join(lineas)
            accion = {'tipo': 'navegar_agenda', 'fecha': encontrados[0]['fecha'],
                      'filtro': expediente}
        else:
            respuesta = f"No encontré el expediente {expediente} en la agenda."

    # ── ESTADÍSTICAS ─────────────────────────────────────────────────────────
    elif intencion == 'estadisticas':
        if mes_info:
            year, mes = mes_info
            filtro = [s for s in senalamientos
                      if s.get('fecha','')[:7] == f"{year}-{mes:02d}"
                      and (not plaza_str or s.get('plaza','') == plaza_str)]
            etiq = f"{list(_MESES_ES.keys())[mes-1]} {year}"
        elif fecha_str:
            filtro = [s for s in senalamientos
                      if s.get('fecha','') == fecha_str
                      and (not plaza_str or s.get('plaza','') == plaza_str)]
            etiq = _fmt_fecha(fecha_str)
        else:
            filtro = [s for s in senalamientos
                      if (not plaza_str or s.get('plaza','') == plaza_str)]
            etiq = "total"
        por_tipo = {}
        for s in filtro:
            tipo = s.get('tipo') or 'Sin tipo'
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        p_txt = f" en {plaza_str}" if plaza_str else ""
        lineas = [f"📊 Señalamientos{p_txt} ({etiq}): {len(filtro)} en total"]
        for tipo, cnt in sorted(por_tipo.items(), key=lambda x: -x[1])[:8]:
            lineas.append(f"  • {tipo}: {cnt}")
        respuesta = '\n'.join(lineas)

    # ── CONFLICTOS ───────────────────────────────────────────────────────────
    elif intencion == 'conflictos':
        if not fecha_str:
            fecha_str = hoy.isoformat()
        filtro = [s for s in senalamientos
                  if s.get('fecha','') == fecha_str and not s.get('anulado')]
        vistos = {}
        conflictos = []
        for s in filtro:
            clave = (s.get('plaza',''), s.get('hora',''))
            if clave in vistos:
                conflictos.append((clave, vistos[clave], s))
            else:
                vistos[clave] = s
        if conflictos:
            lineas = [f"⚠️ Conflictos detectados el {_fmt_fecha(fecha_str)}:"]
            for (plaza, hora), s1, s2 in conflictos:
                lineas.append(f"  • {plaza} a las {hora}: {s1.get('expediente','')} y {s2.get('expediente','')}")
            respuesta = '\n'.join(lineas)
        else:
            respuesta = f"No hay conflictos de horario el {_fmt_fecha(fecha_str)}."
        accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str}

    # ── HUECOS LIBRES ────────────────────────────────────────────────────────
    elif intencion == 'huecos_libres':
        if not fecha_str:
            fecha_str = hoy.isoformat()
        if not plaza_str and plazas_disp:
            plaza_str = plazas_disp[0]
        intervalo = int(agenda_datos.get('intervaloHuecos', 30))
        ocupadas = {s['hora'] for s in senalamientos
                    if s.get('fecha') == fecha_str
                    and s.get('plaza','') == plaza_str
                    and not s.get('anulado')}
        # Generar horas de 8:00 a 15:00
        horas_dia = []
        t = 8 * 60
        while t <= 15 * 60:
            hh, mm = divmod(t, 60)
            horas_dia.append(f"{hh:02d}:{mm:02d}")
            t += intervalo
        libres = [h for h in horas_dia if h not in ocupadas]
        p_txt = f" en {plaza_str}" if plaza_str else ''
        if libres:
            respuesta = (f"🕐 Huecos libres el {_fmt_fecha(fecha_str)}{p_txt}:\n" +
                         '  ' + ', '.join(libres[:20]))
        else:
            respuesta = f"No hay huecos libres el {_fmt_fecha(fecha_str)}{p_txt}."
        accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str}

    # ── CREAR SEÑALAMIENTO ───────────────────────────────────────────────────
    elif intencion == 'crear_senalamiento':
        # hora_str ya extraído en la sección común
        fecha_final = fecha_str or hoy.isoformat()
        plaza_final = plaza_str or ''

        if tipo_str and hora_str:
            # Datos suficientes → ofrecer creación directa con confirmación
            exp_txt = f" — exp. {expediente}" if expediente else ""
            p_txt = f"  🏛️ {plaza_final}\n" if plaza_final else ""
            respuesta = (
                f"📋 Señalamiento a crear:\n"
                f"  📅 {_fmt_fecha(fecha_final)} a las {hora_str}\n"
                f"{p_txt}"
                f"  ⚖️ {tipo_str}{exp_txt}\n\n"
                f"¿Confirmo la creación?"
            )
            accion = {
                'tipo': 'confirmar_senalamiento',
                'fecha': fecha_final,
                'hora': hora_str,
                'plaza': plaza_final,
                'tipo_proc': tipo_str,
                'expediente': expediente or '---'
            }
        else:
            # Faltan datos → abrir formulario pre-rellenado
            faltantes = []
            if not tipo_str: faltantes.append('tipo de procedimiento')
            if not hora_str: faltantes.append('hora')
            p_txt = f" en {plaza_final}" if plaza_final else ''
            f_txt = f" el {_fmt_fecha(fecha_final)}" if fecha_str else ''
            h_txt = f" a las {hora_str}" if hora_str else ''
            t_txt = f" tipo {tipo_str}" if tipo_str else ''
            respuesta = f"✏️ Abriendo formulario de señalamiento{p_txt}{f_txt}{h_txt}{t_txt}.\nFalta: {', '.join(faltantes)}."
            accion = {
                'tipo': 'crear_senalamiento',
                'fecha': fecha_final,
                'plaza': plaza_final,
                'hora': hora_str or '',
                'tipo_proc': tipo_str or ''
            }

    # ── ANULAR / SUSPENDER SEÑALAMIENTO ─────────────────────────────────────
    elif intencion == 'anular_senalamiento':
        t_low = pregunta.lower()
        if re.search(r'\bsuspende[r]?\b', t_low):
            accion_tipo = 'suspender'
        elif re.search(r'\bborra[r]?\b|\belimina[r]?\b|\bquita[r]?\b', t_low):
            accion_tipo = 'borrar'
        else:
            accion_tipo = 'anular'
        if accion_tipo == 'borrar':
            # Borrar puede actuar sobre cualquier señalamiento (incluso anulados/suspendidos)
            candidatos = list(senalamientos)
        else:
            candidatos = [s for s in senalamientos if not s.get('anulado') and not s.get('suspendido')]

        if expediente:
            candidatos = [s for s in candidatos if s.get('expediente', '').strip() == expediente]
        if tipo_str:
            candidatos = [s for s in candidatos if s.get('tipo', '').upper() == tipo_str.upper()]
        if fecha_str:
            candidatos = [s for s in candidatos if s.get('fecha') == fecha_str]
        if hora_str:
            candidatos = [s for s in candidatos if s.get('hora', '').startswith(hora_str)]
        if plaza_str:
            candidatos = [s for s in candidatos if plaza_str.lower() in s.get('plaza', '').lower()]

        if not candidatos:
            respuesta = "No encontré ningún señalamiento con esos criterios."
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str or hoy.isoformat()}
        elif len(candidatos) == 1:
            target = candidatos[0]
            verbo = {'suspender': 'Suspender', 'borrar': 'Borrar', 'anular': 'Anular'}.get(accion_tipo, 'Anular')
            respuesta = (
                f"🔍 Encontrado:\n"
                f"{_fmt_senalamiento(target)}\n"
                f"  📅 {_fmt_fecha(target['fecha'])}\n\n"
                f"¿{verbo} este señalamiento?"
            )
            accion = {
                'tipo': 'confirmar_anulacion',
                'id': target.get('id'),
                'accion': accion_tipo
            }
        else:
            lineas = [f"⚠️ Encontré {len(candidatos)} señalamientos. Sé más específico:"]
            for s in candidatos[:8]:
                lineas.append(f"  {_fmt_fecha(s['fecha'])} — {_fmt_senalamiento(s)}")
            respuesta = '\n'.join(lineas)
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str or hoy.isoformat()}

    # ── MARCAR CELEBRADO ───────────────────────────────────────────────────
    elif intencion == 'marcar_celebrado':
        candidatos = [s for s in senalamientos
                      if not s.get('anulado') and not s.get('suspendido') and not s.get('celebrado')]

        if expediente:
            candidatos = [s for s in candidatos if s.get('expediente', '').strip() == expediente]
        if tipo_str:
            candidatos = [s for s in candidatos if s.get('tipo', '').upper() == tipo_str.upper()]
        if fecha_str:
            candidatos = [s for s in candidatos if s.get('fecha') == fecha_str]
        if hora_str:
            candidatos = [s for s in candidatos if s.get('hora', '').startswith(hora_str)]
        if plaza_str:
            candidatos = [s for s in candidatos if plaza_str.lower() in s.get('plaza', '').lower()]

        if not candidatos:
            respuesta = "No encontré ningún señalamiento pendiente con esos criterios."
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str or hoy.isoformat()}
        elif len(candidatos) == 1:
            target = candidatos[0]
            respuesta = (
                f"🔍 Encontrado:\n"
                f"{_fmt_senalamiento(target)}\n"
                f"  📅 {_fmt_fecha(target['fecha'])}\n\n"
                f"¿Marcar como celebrado?"
            )
            accion = {
                'tipo': 'confirmar_celebrado',
                'id': target.get('id')
            }
        else:
            lineas = [f"⚠️ Encontré {len(candidatos)} señalamientos. Sé más específico:"]
            for s in candidatos[:8]:
                lineas.append(f"  {_fmt_fecha(s['fecha'])} — {_fmt_senalamiento(s)}")
            respuesta = '\n'.join(lineas)
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str or hoy.isoformat()}

    # ── MODIFICAR SEÑALAMIENTO ─────────────────────────────────────────────
    elif intencion == 'modificar_senalamiento':
        candidatos = [s for s in senalamientos if not s.get('anulado') and not s.get('suspendido')]

        if expediente:
            candidatos = [s for s in candidatos if s.get('expediente', '').strip() == expediente]
        if tipo_str:
            candidatos = [s for s in candidatos if s.get('tipo', '').upper() == tipo_str.upper()]
        if fecha_str:
            candidatos = [s for s in candidatos if s.get('fecha') == fecha_str]
        if plaza_str:
            candidatos = [s for s in candidatos if plaza_str.lower() in s.get('plaza', '').lower()]

        hora_nueva = _extraer_hora(pregunta)

        # Intentar extraer una segunda fecha del texto (la nueva fecha destino)
        # Si el usuario dice "cambia el señalamiento del 15/03 al 20/03", fecha_str=15/03, nueva_fecha=20/03
        nueva_fecha = None
        m_al = re.search(r'\bal\s+(\d{1,2})[/\.](\d{1,2})(?:[/\.](\d{2,4}))?\b', pregunta.lower())
        if m_al:
            d2, m2 = int(m_al.group(1)), int(m_al.group(2))
            y2 = int(m_al.group(3)) if m_al.group(3) else hoy.year
            if y2 < 100:
                y2 += 2000
            try:
                nueva_fecha = date(y2, m2, d2).isoformat()
            except ValueError:
                pass

        # Extraer nueva plaza del texto: "a la plaza 2", "a plaza 1"
        nueva_plaza = None
        m_pl = re.search(r'\ba\s+(?:la\s+)?plaza\s+(\d+|[a-záéíóúñ\s]+)', pregunta.lower())
        if m_pl:
            nueva_plaza = 'Plaza ' + m_pl.group(1).strip().title()

        if not candidatos:
            respuesta = "No encontré ningún señalamiento activo con esos criterios."
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str or hoy.isoformat()}
        elif len(candidatos) == 1:
            target = candidatos[0]
            cambios = {}
            detalle = []
            if hora_nueva and hora_nueva != target.get('hora'):
                cambios['hora'] = hora_nueva
                detalle.append(f"  ⏰ Hora: {target.get('hora','')} → {hora_nueva}")
            if nueva_fecha and nueva_fecha != target.get('fecha'):
                cambios['fecha'] = nueva_fecha
                detalle.append(f"  📅 Fecha: {_fmt_fecha(target['fecha'])} → {_fmt_fecha(nueva_fecha)}")
            if nueva_plaza and nueva_plaza.lower() != target.get('plaza', '').lower():
                cambios['plaza'] = nueva_plaza
                detalle.append(f"  🏛️ Plaza: {target.get('plaza','')} → {nueva_plaza}")

            if cambios:
                respuesta = (
                    f"🔍 Señalamiento encontrado:\n"
                    f"{_fmt_senalamiento(target)}\n"
                    f"  📅 {_fmt_fecha(target['fecha'])}\n\n"
                    f"📝 Cambios propuestos:\n" + '\n'.join(detalle) + "\n\n"
                    f"¿Confirmar la modificación?"
                )
                accion = {
                    'tipo': 'confirmar_modificacion',
                    'id': target.get('id'),
                    'cambios': cambios
                }
            else:
                respuesta = (
                    f"Encontré el señalamiento pero no pude identificar qué cambiar.\n"
                    f"{_fmt_senalamiento(target)}\n"
                    f"  📅 {_fmt_fecha(target['fecha'])}\n\n"
                    f"Indica qué quieres modificar: hora, fecha o plaza."
                )
                accion = {'tipo': 'navegar_agenda', 'fecha': target.get('fecha', hoy.isoformat())}
        else:
            lineas = [f"⚠️ Encontré {len(candidatos)} señalamientos. Sé más específico:"]
            for s in candidatos[:8]:
                lineas.append(f"  {_fmt_fecha(s['fecha'])} — {_fmt_senalamiento(s)}")
            respuesta = '\n'.join(lineas)
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str or hoy.isoformat()}

    # ── INSTRUCCIÓN PENAL / PRÓRROGAS ────────────────────────────────────────
    elif intencion == 'instruccion_penal':
        inst_data   = cargar_json(_resolver_fichero_modulo('instruccion_penal', F_INSTRUCCION)) or {}
        procs       = inst_data if isinstance(inst_data, list) else inst_data.get('procedimientos', [])
        abiertos    = [p for p in procs if not p.get('cerrado')]
        cerrados    = [p for p in procs if p.get('cerrado')]
        # Filtrar por plaza si se mencionó
        if plaza_str:
            abiertos = [p for p in abiertos if plaza_str.lower() in p.get('plaza','').lower()]
        # Ordenar por fecha de vencimiento más próxima
        abiertos_ord = sorted(abiertos, key=lambda x: x.get('fechaVencimiento','9999'))
        # Formatear ref del procedimiento
        def _ref_inst(p):
            return f"{p.get('tipo','?')} {p.get('numero','?')}/{p.get('anyo','?')}"
        if abiertos_ord:
            lineas = [f"⚖️ Instrucción Penal — plazos abiertos: {len(abiertos_ord)}"]
            for p in abiertos_ord[:10]:
                ref  = _ref_inst(p)
                pl   = p.get('plaza','?')
                auto = _fmt_fecha(p['fechaAuto']) if p.get('fechaAuto') else '?'
                meses= p.get('meses', '?')
                venc = _fmt_fecha(p['fechaVencimiento']) if p.get('fechaVencimiento') else '?'
                alerta = p.get('alertaDias', 15)
                lineas.append(f"  • {ref} — {pl} — auto: {auto} — {meses} mes(es) — vence: {venc} (alerta {alerta}d)")
            if len(abiertos) > 10:
                lineas.append(f"  … y {len(abiertos)-10} más en el módulo.")
            if cerrados:
                lineas.append(f"\nCerrados: {len(cerrados)}")
            respuesta = '\n'.join(lineas)
        else:
            p_txt = f" en {plaza_str}" if plaza_str else ''
            respuesta = f"No hay plazos de instrucción abiertos{p_txt}."
        accion = {'tipo': 'navegar_modulo', 'modulo': 'instruccion_penal'}
        contexto_groq = (
            f"Instrucción Penal — {len(abiertos_ord)} plazos abiertos:\n"
            + '\n'.join(
                f"{_ref_inst(p)} — {p.get('meses','?')} mes(es) — vence {p.get('fechaVencimiento','?')}"
                for p in abiertos_ord[:8]
            )
        ) if abiertos_ord else f"Sin plazos de instrucción abiertos{' en '+plaza_str if plaza_str else ''}."

    # ── CORREOS / ENVÍOS POSTALES ────────────────────────────────────────────
    elif intencion == 'correos':
        correos_data = cargar_json(_resolver_fichero_modulo('correos', F_CORREOS)) or {}
        envios = correos_data.get('envios', [])
        pendientes_c = [e for e in envios if not e.get('enviado')]
        enviados_c   = [e for e in envios if e.get('enviado')]
        respuesta = (
            f"📬 Módulo de Correos/Envíos Postales:\n"
            f"  • Registros totales: {len(envios)}\n"
            f"  • Pendientes de envío: {len(pendientes_c)}\n"
            f"  • Enviados: {len(enviados_c)}\n"
            f"Allí puedes registrar destinatarios y generar el fichero TXT para lotes de 10."
        )
        accion = {'tipo': 'navegar_modulo', 'modulo': 'correos'}
        contexto_groq = (
            f"Correos: {len(envios)} registros totales, "
            f"{len(pendientes_c)} pendientes, {len(enviados_c)} enviados."
        )

    # ── MODELOS IA CONFIGURADOS ──────────────────────────────────────────────
    elif intencion == 'modelos_ia':
        prov_id_m, prov_m, key_m, modelo_m = _llm_cfg()
        cfg_raw_m = cargar_json(F_CONFIG_LLM) or {}
        claves_m  = [pid for pid, pdata in PROVEEDORES_LLM.items()
                     if cfg_raw_m.get(pdata['key_field'], '').strip()]
        lineas_m  = [f"🤖 Configuración IA actual del portal:"]
        if prov_m:
            lineas_m.append(f"  • Proveedor activo: **{prov_m['nombre']}**")
            lineas_m.append(f"  • Modelo activo:    `{modelo_m}`")
        else:
            lineas_m.append("  • Sin proveedor configurado (motor de reglas)")
        lineas_m.append(f"\nProveedores con clave guardada: {', '.join(claves_m) if claves_m else 'ninguno'}")
        lineas_m.append("\nCambia el proveedor/modelo en ⚙️ → 🔑 Configurar IA.")
        respuesta = '\n'.join(lineas_m)
        accion    = None
        contexto_groq = f"Proveedor activo: {prov_m['nombre'] if prov_m else 'ninguno'}, modelo: {modelo_m or 'ninguno'}"

    # ── BÚSQUEDA GLOBAL CROSS-MÓDULO ─────────────────────────────────────────
    elif intencion == 'busqueda_global':
        q_busq = re.sub(
            r'^(busca[r]?|encuentra[r]?|localiza[r]?|d[oó]nde\s+est[aá]|'
            r'qu[eé]\s+hay\s+de|b[uú]squeda[:]?)\s*',
            '', pregunta.strip(), flags=re.IGNORECASE).strip()
        resultados_b = _busqueda_global_data(q_busq) if len(q_busq) >= 2 else []
        if len(q_busq) < 2:
            respuesta = ("¿Qué quieres buscar? Escribe un término más específico "
                         "(expediente, nombre, procedimiento, fecha…).")
            accion = None
        elif not resultados_b:
            respuesta = (f"🔍 No encontré nada para **{q_busq}** "
                         "en ningún módulo del portal.")
            accion = None
        else:
            _MODS_NOM = {
                'agenda':       ('📅', 'Agenda'),
                'vencimientos': ('⏱️', 'Vencimientos'),
                'peritos':      ('🔬', 'Peritos'),
                'instruccion':  ('⚖️', 'Instrucción Penal'),
                'clipbox':      ('📋', 'Modelos'),
                'auxilios':     ('🔗', 'Auxilios'),
                'presos':       ('🔒', 'Presos'),
                'archivo':      ('🗄️', 'Archivo'),
                'notificajud':  ('🔔', 'Notifica/Turnos'),
            }
            grupos_r = {}
            for r in resultados_b[:30]:
                grupos_r.setdefault(r['modulo'], []).append(r)
            lineas = [f"🔍 **{q_busq}** — {len(resultados_b)} resultado(s):"]
            for mod, resl in grupos_r.items():
                ico, nom = _MODS_NOM.get(mod, ('📋', mod))
                lineas.append(f"\n{ico} {nom} ({len(resl)}):")
                for r in resl[:5]:
                    lineas.append(f"  • {r['titulo']}")
                    if r.get('detalle'):
                        lineas.append(f"    {r['detalle']}")
                if len(resl) > 5:
                    lineas.append(f"    … y {len(resl)-5} más")
            respuesta = '\n'.join(lineas)
            mod_top = max(grupos_r, key=lambda m: len(grupos_r[m]))
            accion = {'tipo': 'navegar_modulo', 'modulo': mod_top, 'filtro': q_busq}
        contexto_groq = (
            f"Búsqueda: '{q_busq}' → {len(resultados_b)} resultado(s)\n"
            + '\n'.join(f"{r['modulo']}: {r['titulo']}" for r in resultados_b[:8])
        )

    # ── AYUDA ─────────────────────────────────────────────────────────────────
    elif intencion == 'ayuda':
        respuesta = (
            "🤖 **Asistente Judicial — Guía rápida**\n\n"
            "Puedes preguntarme sobre cualquier módulo del portal. "
            "Aquí tienes ejemplos de lo que puedo hacer:\n\n"
            "☀️ **Resumen del día**\n"
            "   • «Buenos días» / «resumen de hoy» / «¿qué tengo hoy?»\n\n"
            "📅 **Agenda / Señalamientos**\n"
            "   • «¿Qué señalamientos hay hoy?» / «señalamientos del 15 de marzo»\n"
            "   • «¿Qué hay esta semana?» / «señalamientos de abril»\n"
            "   • «¿Hay huecos libres mañana?» / «conflictos de agenda»\n"
            "   • «Próximos señalamientos» / «¿qué viene?»\n"
            "   • «Crear señalamiento JVB 123/24 el 20/03 a las 10:00»\n"
            "   • «Anular señalamiento» / «marcar celebrado»\n\n"
            "⏱️ **Vencimientos / Plazos**\n"
            "   • «¿Qué plazos vencen pronto?» / «vencimientos pendientes»\n"
            "   • «Crear vencimiento JVB 123/2024 plazo 20 días»\n\n"
            "🏖️ **Vacaciones / Permisos**\n"
            "   • «¿Quién está de vacaciones?» / «ausencias esta semana»\n\n"
            "🔔 **Notifica/Turnos / Diligencias**\n"
            "   • «¿Quién está de turno hoy?» / «turnos de esta semana»\n"
            "   • «Anotar notificación positiva» / «registrar diligencia»\n"
            "   • «Diligencias pendientes» / «estado de las diligencias»\n\n"
            "🛡️ **Guardias**\n"
            "   • «¿Quién lleva la guardia?» / «guardia de esta semana»\n"
            "   • «¿Cuándo me toca guardia?» / «mi guardia»\n"
            "   • «Asigna guardia de gestión a Ferreiros esta semana»\n"
            "   • «Quita guardia de tramitación de esta semana»\n"
            "   • «Intercambia guardia de gestión esta semana con la próxima»\n\n"
            "🏛️ **Ausencias de Plazas**\n"
            "   • «¿Qué plazas tienen ausencias hoy?»\n"
            "   • «Registra ausencia de Pedro del 20 al 24 de marzo»\n"
            "   • «Cancela ausencia de Pedro»\n"
            "   • «Historial de ausencias de Plaza 1»\n\n"
            "🏢 **DIR3 — Directorio Común**\n"
            "   • «DIR3 Ayuntamiento de Vilagarcía» / «código DIR3 del juzgado de Cambados»\n\n"
            "📋 **Resumen semanal**\n"
            "   • «Resumen de la semana» / «cómo viene la semana»\n"
            "   • «Resumen de la próxima semana»\n\n"
            "🔬 **Peritos**\n"
            "   • «Buscar perito forense» / «tasadores disponibles»\n"
            "   • «Seleccionar perito psicólogo» (insaculación)\n\n"
            "🔒 **Control de Presos**\n"
            "   • «¿Cuántos presos hay?» / «internos preventivos»\n\n"
            "📹 **Auxilios Judiciales**\n"
            "   • «Auxilios pendientes» / «videoconferencias»\n"
            "   • «Crear videoconferencia el 20/03 a las 10:00»\n\n"
            "⚖️ **Instrucción Penal**\n"
            "   • «Plazos de instrucción» / «prórrogas pendientes»\n\n"
            "📮 **Correos / Envíos Postales**\n"
            "   • «Correos pendientes» / «envíos postales de hoy»\n\n"
            "📋 **ClipBox / Modelos**\n"
            "   • «¿Qué plantillas hay?» / «modelos de texto disponibles»\n\n"
            "📨 **Minutas**\n"
            "   • «Minutas registradas» / «última minuta»\n\n"
            "📊 **Boletín Trimestral**\n"
            "   • «Datos del boletín» / «boletín trimestral»\n\n"
            "🔄 **Sincronizar nombre**\n"
            "   • «Cambiar nombre Juan Pérez por Juan García»\n\n"
            "📌 **Tablón de Anuncios**\n"
            "   • «¿Qué hay en el tablón?» / «avisos de hoy»\n"
            "   • «Publica en el tablón: mañana no hay audiencia por la tarde»\n"
            "   • «Busca en el tablón vacaciones»\n\n"
            "🔔 **Notificaciones**\n"
            "   • «¿Tengo notificaciones?» / «notificaciones pendientes»\n\n"
            "🔍 **Búsqueda global**\n"
            "   • «Buscar 123/2024» / «¿dónde está el expediente X?»\n\n"
            "💡 *Escribe tu pregunta con naturalidad, yo detecto el módulo automáticamente.*"
        )
        accion = None
        contexto_groq = "El usuario pidió ayuda. Se mostró la guía completa."

    # ── CLIPBOX / MODELOS ────────────────────────────────────────────────────
    elif intencion == 'clipbox':
        datos_clip = cargar_json(_resolver_fichero_modulo('clipbox', F_CLIPBOX)) or {}
        categorias_c = datos_clip.get('categorias', [])
        items_c = datos_clip.get('items', [])
        total_items = len(items_c)
        cats_nombres = [c.get('nombre', '?') for c in categorias_c] if categorias_c else []
        lineas_clip = [f"📋 **ClipBox — Modelos de texto**"]
        lineas_clip.append(f"Total de plantillas: **{total_items}**")
        if cats_nombres:
            lineas_clip.append(f"Categorías: {', '.join(cats_nombres[:15])}")
        if items_c:
            lineas_clip.append("\nÚltimas plantillas:")
            for it in items_c[:5]:
                nombre_it = it.get('titulo', it.get('nombre', '?'))
                cat_it = it.get('categoria', '')
                lineas_clip.append(f"  • {nombre_it}" + (f" ({cat_it})" if cat_it else ''))
        lineas_clip.append("\n💡 Abre el módulo **📋 Modelos** para copiar o editar plantillas.")
        respuesta = '\n'.join(lineas_clip)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'clipbox'}
        contexto_groq = f"ClipBox: {total_items} plantillas, {len(cats_nombres)} categorías."

    # ── MINUTAS ──────────────────────────────────────────────────────────────
    elif intencion == 'minutas':
        datos_min = cargar_json(_resolver_fichero_modulo('minutas', F_MINUTAS)) or {}
        minutas_lista = datos_min.get('minutas', datos_min.get('registros', []))
        if isinstance(datos_min, list):
            minutas_lista = datos_min
        total_min = len(minutas_lista) if isinstance(minutas_lista, list) else 0
        lineas_min = [f"📨 **Minutas judiciales**"]
        lineas_min.append(f"Total registradas: **{total_min}**")
        if isinstance(minutas_lista, list) and minutas_lista:
            lineas_min.append("\nÚltimas minutas:")
            for m in minutas_lista[-5:]:
                if isinstance(m, dict):
                    desc = m.get('descripcion', m.get('titulo', m.get('asunto', '?')))
                    fecha_m = m.get('fecha', '')
                    lineas_min.append(f"  • {desc}" + (f" ({fecha_m})" if fecha_m else ''))
        lineas_min.append("\n💡 Abre el módulo **📨 Minutas** para gestionar las minutas.")
        respuesta = '\n'.join(lineas_min)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'minutas'}
        contexto_groq = f"Minutas: {total_min} registros."

    # ── RESUMEN DEL DÍA (briefing matinal) ──────────────────────────────────
    elif intencion == 'resumen_dia':
        lineas_r = [f"📋 **Resumen del día — {_fmt_fecha(hoy.isoformat())}**\n"]
        # 1. Señalamientos de hoy
        hoy_str = hoy.isoformat()
        sen_hoy = [s for s in senalamientos
                   if s.get('fecha') == hoy_str and not s.get('anulado')]
        celebrados_hoy = [s for s in sen_hoy if s.get('celebrado')]
        suspendidos_hoy = [s for s in sen_hoy if s.get('suspendido')]
        activos_hoy = [s for s in sen_hoy if not s.get('celebrado') and not s.get('suspendido')]
        if sen_hoy:
            lineas_r.append(f"📅 **Señalamientos hoy:** {len(sen_hoy)}")
            if activos_hoy:
                lineas_r.append(f"  • Pendientes: {len(activos_hoy)}")
            if celebrados_hoy:
                lineas_r.append(f"  • Celebrados: {len(celebrados_hoy)}")
            if suspendidos_hoy:
                lineas_r.append(f"  • Suspendidos: {len(suspendidos_hoy)}")
            for s in sorted(activos_hoy, key=lambda x: x.get('hora', ''))[:5]:
                lineas_r.append(f"    {s.get('hora','')} — {s.get('tipo','?')} {s.get('expediente','')}")
            if len(activos_hoy) > 5:
                lineas_r.append(f"    … y {len(activos_hoy)-5} más")
        else:
            lineas_r.append("📅 **Señalamientos hoy:** ninguno")
        # 2. Guardia de esta semana
        try:
            g_datos_r = _consultar_guardias()
            funcionarios_r = g_datos_r.get('funcionarios', [])
            guardias_sem_r = g_datos_r.get('guardias', {})
            dow_r = hoy.weekday()
            martes_r = hoy - timedelta((dow_r - 1) % 7)
            g_sem_r = guardias_sem_r.get(martes_r.isoformat(), {})
            if g_sem_r:
                def _nf_r(fid):
                    f = next((x for x in funcionarios_r if x.get('id') == fid), None)
                    if not f: return '—'
                    p = f['nombre'].split(',')
                    return f"{p[1].strip()} {p[0].strip()}" if len(p) > 1 else f['nombre']
                partes_g = []
                if g_sem_r.get('gestorId'):     partes_g.append(f"Gestión: {_nf_r(g_sem_r['gestorId'])}")
                if g_sem_r.get('tramitadorId'): partes_g.append(f"Tramitación: {_nf_r(g_sem_r['tramitadorId'])}")
                if g_sem_r.get('auxilioId'):    partes_g.append(f"Auxilio: {_nf_r(g_sem_r['auxilioId'])}")
                if partes_g:
                    lineas_r.append(f"\n🛡️ **Guardia:** {' · '.join(partes_g)}")
        except Exception:
            pass
        # 3. Vencimientos próximos (7 días)
        try:
            v_datos_r = _consultar_vencimientos(uid, equipo)
            avisos_r = v_datos_r.get('avisos', [])
            limite_r = (hoy + timedelta(7)).isoformat()
            prox_venc = [a for a in avisos_r
                         if a.get('estado') != 'vencido' and not a.get('anulado')
                         and a.get('ultimoDia', '') <= limite_r
                         and a.get('ultimoDia', '') >= hoy_str]
            if prox_venc:
                lineas_r.append(f"\n⏰ **Vencimientos (7 días):** {len(prox_venc)}")
                for a in sorted(prox_venc, key=lambda x: x.get('ultimoDia', ''))[:3]:
                    lineas_r.append(f"  • {a.get('procedimiento', '—')} — vence {_fmt_fecha(a['ultimoDia'])}")
                if len(prox_venc) > 3:
                    lineas_r.append(f"  … y {len(prox_venc)-3} más")
        except Exception:
            pass
        # 4. Ausencias activas hoy
        try:
            adata_r = cargar_json(_resolver_fichero_modulo('ausencias', F_AUSENCIAS)) or {}
            todas_aus_r = adata_r.get('ausencias', [])
            plazas_map_r = {p['id']: p for p in adata_r.get('plazas', [])}
            activas_r = [a for a in todas_aus_r
                         if a.get('fechaInicio', '') <= hoy_str <= a.get('fechaFin', '9')]
            if activas_r:
                lineas_r.append(f"\n🏛️ **Ausencias de plazas hoy:** {len(activas_r)}")
                for a in activas_r[:3]:
                    pl_r = plazas_map_r.get(a.get('plazaId'), {}).get('nombre', '?')
                    lineas_r.append(f"  • {pl_r}: {a.get('titular', '?')}")
        except Exception:
            pass
        # 5. Auxilios pendientes hoy
        try:
            aux_datos_r = cargar_json(F_AUXILIOS) or {}
            aux_hoy = [a for a in aux_datos_r.get('auxilios', [])
                       if a.get('fecha') == hoy_str and a.get('estado', '').lower() == 'pendiente']
            if aux_hoy:
                lineas_r.append(f"\n📹 **Auxilios hoy:** {len(aux_hoy)} pendiente(s)")
                for a in aux_hoy[:3]:
                    tipo_a_r = a.get('tipo_nombre') or a.get('tipo', '?')
                    lineas_r.append(f"  • {a.get('hora','')} — {tipo_a_r}")
        except Exception:
            pass
        lineas_r.append("\n💡 Pregunta por cualquier módulo para más detalle.")
        respuesta = '\n'.join(lineas_r)
        accion = {'tipo': 'navegar_agenda', 'fecha': hoy_str}
        contexto_groq = respuesta

    # ── BOLETÍN TRIMESTRAL ────────────────────────────────────────────────────
    elif intencion == 'boletin':
        bol_data = cargar_json(_resolver_fichero_modulo('boletin', F_BOLETIN)) or {}
        bol_plazas = bol_data.get('plazas', {})
        bol_datos  = bol_data.get('datos', {})
        total_trim = len(bol_datos)
        # Extraer trimestres únicos
        trimestres_uniq = set()
        for clave in bol_datos.keys():
            partes = clave.rsplit('_', 2)
            if len(partes) >= 2:
                try:
                    trimestres_uniq.add((int(partes[-2]), int(partes[-1])))
                except ValueError:
                    pass
        lineas_b = [f"📊 **Boletín Trimestral**"]
        if isinstance(bol_plazas, dict) and bol_plazas:
            plazas_names = list(bol_plazas.values()) if all(isinstance(v, str) for v in bol_plazas.values()) else list(bol_plazas.keys())
            lineas_b.append(f"Plazas configuradas: {', '.join(str(p) for p in plazas_names[:8])}")
        lineas_b.append(f"Trimestres con datos: **{total_trim}**")
        if trimestres_uniq:
            sorted_t = sorted(trimestres_uniq)
            for anyo, trim in sorted_t[-6:]:
                clave_prefix = f"_{anyo}_{trim}"
                datos_t = {k: v for k, v in bol_datos.items() if k.endswith(clave_prefix)}
                if datos_t:
                    nom_trim = f"{anyo} T{trim}"
                    # Contar asuntos si hay campo estándar
                    total_asuntos = 0
                    for v in datos_t.values():
                        if isinstance(v, dict):
                            total_asuntos += v.get('ingresados', 0) + v.get('resueltos', 0)
                    extra = f" ({total_asuntos} asuntos)" if total_asuntos else ""
                    lineas_b.append(f"  • {nom_trim}{extra}")
        lineas_b.append(f"\n💡 Abre el módulo **📊 Boletín** para editar los datos trimestrales.")
        respuesta = '\n'.join(lineas_b)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'boletin'}
        contexto_groq = f"Boletín: {total_trim} trimestres con datos."

    # ── REGISTRO DE DILIGENCIAS ───────────────────────────────────────────────
    elif intencion == 'registro_diligencias':
        reg_dil = _consultar_registro_diligencias()
        pendientes_d = [r for r in reg_dil if r.get('estado') == 'Pendiente']
        planificados_d = [r for r in reg_dil if r.get('estado') == 'Planificado']
        realizados_d = [r for r in reg_dil if r.get('estado') == 'Realizado']
        # Filtrar por fecha si se indicó
        if fecha_str:
            pendientes_d = [r for r in pendientes_d if r.get('fecha', '') == fecha_str]
            planificados_d = [r for r in planificados_d if r.get('fecha', '') == fecha_str]
            realizados_d = [r for r in realizados_d if r.get('fecha', '') == fecha_str]
            f_txt = f" del {_fmt_fecha(fecha_str)}"
        else:
            f_txt = ""
        lineas_d = [f"📋 **Registro de Diligencias{f_txt}**"]
        lineas_d.append(f"  • Pendientes: **{len(pendientes_d)}**")
        lineas_d.append(f"  • Planificadas: **{len(planificados_d)}**")
        lineas_d.append(f"  • Realizadas: **{len(realizados_d)}**")
        if pendientes_d:
            lineas_d.append("\nDiligencias pendientes:")
            for r in pendientes_d[:8]:
                exp_d = r.get('expediente', '')
                dest  = r.get('destinatario', '')
                tipo_d = r.get('tipo', '?')
                lineas_d.append(f"  • {tipo_d}" + (f" — {exp_d}" if exp_d else "") + (f" — {dest}" if dest else ""))
            if len(pendientes_d) > 8:
                lineas_d.append(f"  … y {len(pendientes_d)-8} más")
        lineas_d.append("\n💡 Gestiona las diligencias desde el módulo **🔔 Notificajud**.")
        respuesta = '\n'.join(lineas_d)
        accion = {'tipo': 'navegar_modulo', 'modulo': 'notificajud'}
        contexto_groq = (
            f"Registro diligencias{f_txt}: "
            f"{len(pendientes_d)} pendientes, {len(planificados_d)} planificadas, "
            f"{len(realizados_d)} realizadas."
        )

    # ── PRÓXIMOS SEÑALAMIENTOS ────────────────────────────────────────────────
    elif intencion == 'proximos_senalamientos':
        hoy_str = hoy.isoformat()
        futuros = [s for s in senalamientos
                   if s.get('fecha', '') >= hoy_str
                   and not s.get('anulado') and not s.get('suspendido')
                   and not s.get('celebrado')]
        if plaza_str:
            futuros = [s for s in futuros if plaza_str.lower() in s.get('plaza', '').lower()]
        if tipo_str:
            futuros = [s for s in futuros if tipo_str.lower() in s.get('tipo', '').lower()]
        futuros = sorted(futuros, key=lambda x: (x.get('fecha', ''), x.get('hora', '')))
        p_txt = f" en {plaza_str}" if plaza_str else ''
        t_txt = f" tipo {tipo_str}" if tipo_str else ''
        if futuros:
            # Agrupar por día
            por_dia_f = {}
            for s in futuros[:30]:
                por_dia_f.setdefault(s['fecha'], []).append(s)
            dias_mostrar = sorted(por_dia_f.keys())[:5]
            total_f = len(futuros)
            lineas_f = [f"📅 **Próximos señalamientos{p_txt}{t_txt}:** {total_f} pendientes"]
            for dia in dias_mostrar:
                ss = por_dia_f[dia]
                lineas_f.append(f"\n  📅 {_fmt_fecha(dia)} ({len(ss)}):")
                for s in ss[:4]:
                    lineas_f.append(_fmt_senalamiento(s))
                if len(ss) > 4:
                    lineas_f.append(f"    … y {len(ss)-4} más ese día")
            dias_no_mostrados = len(por_dia_f) - len(dias_mostrar)
            if dias_no_mostrados > 0:
                lineas_f.append(f"\n  … y {dias_no_mostrados} día(s) más con señalamientos")
            respuesta = '\n'.join(lineas_f)
            accion = {'tipo': 'navegar_agenda', 'fecha': futuros[0]['fecha']}
        else:
            respuesta = f"No hay señalamientos futuros{p_txt}{t_txt}."
            accion = {'tipo': 'navegar_agenda', 'fecha': hoy_str}
        contexto_groq = (
            f"Próximos señalamientos{p_txt}: {len(futuros)} pendientes\n"
            + '\n'.join(str(_anonimizar_senalamiento(s)) for s in futuros[:15])
        ) if futuros else f"Sin señalamientos futuros{p_txt}."

    # ── SINCRONIZAR NOMBRE ────────────────────────────────────────────────────
    elif intencion == 'sincronizar_nombre':
        # Extraer nombres del texto (viejo → nuevo)
        t_raw = pregunta.strip()
        # Patrones: "cambia nombre X por Y", "renombra X a Y"
        m_sync = re.search(
            r'(?:cambi(?:ar?|o)\s+(?:el\s+)?nombre\s+(?:de\s+)?)'
            r'["\']?(.+?)["\']?\s+(?:por|a)\s+["\']?(.+?)["\']?\s*$',
            t_raw, re.IGNORECASE)
        if not m_sync:
            m_sync = re.search(
                r'(?:renombr(?:ar?|a)\s+)'
                r'["\']?(.+?)["\']?\s+(?:por|a|→)\s+["\']?(.+?)["\']?\s*$',
                t_raw, re.IGNORECASE)
        if m_sync:
            nombre_viejo = m_sync.group(1).strip()
            nombre_nuevo = m_sync.group(2).strip()
            respuesta = (
                f"🔄 **Sincronización de nombre**\n\n"
                f"  Nombre actual:  **{nombre_viejo}**\n"
                f"  Nombre nuevo:   **{nombre_nuevo}**\n\n"
                f"Esto buscará y reemplazará el nombre en todos los módulos del portal "
                f"(agenda, guardias, vacaciones, vencimientos, minutas, correos, auxilios).\n\n"
                f"¿Confirmar la sincronización?"
            )
            accion = {
                'tipo': 'confirmar_sincronizar_nombre',
                'nombre_viejo': nombre_viejo,
                'nombre_nuevo': nombre_nuevo
            }
        else:
            respuesta = (
                "🔄 **Sincronizar nombre**\n\n"
                "Para cambiar un nombre en todos los módulos, escríbelo así:\n"
                "  «cambiar nombre Juan Pérez por Juan García Pérez»\n"
                "  «renombrar PEREZ, JUAN a GARCIA PEREZ, JUAN»\n\n"
                "Esto actualizará el nombre en todos los ficheros del portal."
            )
            accion = None
        contexto_groq = "Sincronización de nombres en módulos del portal."

    # ── CREAR VENCIMIENTO ─────────────────────────────────────────────────────
    elif intencion == 'crear_vencimiento':
        fecha_final_v = fecha_str or ''
        # Extraer días de plazo: "plazo de 10 días", "10 días hábiles"
        m_dias = re.search(r'(\d+)\s*d[ií]as?\b', pregunta)
        dias_plazo = int(m_dias.group(1)) if m_dias else None
        # Extraer procedimiento/expediente
        proc_txt = ''
        if expediente:
            proc_txt = ((tipo_str + ' ') if tipo_str else '') + expediente
        elif tipo_str:
            proc_txt = tipo_str
        partes_v = []
        if fecha_final_v:
            partes_v.append(f"📅 Fecha inicio: {_fmt_fecha(fecha_final_v)}")
        if dias_plazo:
            partes_v.append(f"⏱️ Plazo: {dias_plazo} días")
        if proc_txt:
            partes_v.append(f"📁 Procedimiento: {proc_txt}")
        faltantes_v = []
        if not proc_txt:
            faltantes_v.append('procedimiento/expediente')
        if not dias_plazo:
            faltantes_v.append('días de plazo')
        if proc_txt and dias_plazo:
            # Datos suficientes → ofrecer creación con confirmación
            respuesta = (
                f"⏰ **Nuevo vencimiento a crear:**\n"
                + '\n'.join(f"  {p}" for p in partes_v)
                + "\n\n¿Confirmar la creación?"
            )
            accion = {
                'tipo': 'confirmar_vencimiento',
                'procedimiento': proc_txt,
                'plazoDias': dias_plazo,
                'fechaInicio': fecha_final_v or hoy.isoformat()
            }
        else:
            respuesta = (
                f"⏰ Para crear un vencimiento necesito:\n"
                + ('\n'.join(f"  {p}" for p in partes_v) + '\n' if partes_v else '')
                + f"  ⚠️ Falta: {', '.join(faltantes_v)}\n\n"
                f"Ejemplo: «crear vencimiento JVB 123/2024 plazo 20 días»"
            )
            accion = {'tipo': 'navegar_modulo', 'modulo': 'vencimientos'}
        contexto_groq = f"Crear vencimiento: proc={proc_txt}, plazo={dias_plazo}, fecha={fecha_final_v}"

    # ── CREAR AUXILIO / VIDEOCONFERENCIA ──────────────────────────────────────
    elif intencion == 'crear_auxilio':
        fecha_final_a = fecha_str or ''
        # Detectar tipo de auxilio
        t_low_a = pregunta.lower()
        tipo_aux_c = 'otro'
        tipo_nom_c = 'Otro'
        if re.search(r'\bvideoconferencia[s]?\b|\bvc\b', t_low_a):
            tipo_aux_c = 'videoconferencia'
            tipo_nom_c = 'Videoconferencia'
        elif re.search(r'\bexhorto[s]?\b', t_low_a):
            tipo_aux_c = 'exhorto'
            tipo_nom_c = 'Exhorto'
        elif re.search(r'\bcomisi[oó]n rogatoria\b', t_low_a):
            tipo_aux_c = 'comision_rogatoria'
            tipo_nom_c = 'Comisión Rogatoria'
        # Extraer tribunal/juzgado
        tribunal_c = ''
        m_trib = re.search(r'(?:con|del?|al?)\s+(?:el\s+)?(?:juzgado|tribunal|audiencia)\s+(.+?)(?:\s+(?:el|para|sobre|fecha)|$)', pregunta, re.IGNORECASE)
        if m_trib:
            tribunal_c = m_trib.group(1).strip()
        proc_aux = ''
        if expediente:
            proc_aux = ((tipo_str + ' ') if tipo_str else '') + expediente
        elif tipo_str and tipo_str.lower() not in ('videoconferencia', 'exhorto'):
            proc_aux = tipo_str
        partes_a = []
        partes_a.append(f"📹 Tipo: {tipo_nom_c}")
        if fecha_final_a:
            partes_a.append(f"📅 Fecha: {_fmt_fecha(fecha_final_a)}")
        if hora_str:
            partes_a.append(f"⏰ Hora: {hora_str}")
        if tribunal_c:
            partes_a.append(f"🏛️ Tribunal: {tribunal_c}")
        if proc_aux:
            partes_a.append(f"📁 Procedimiento: {proc_aux}")
        if plaza_str:
            partes_a.append(f"🏛️ Plaza: {plaza_str}")
        if fecha_final_a and hora_str:
            respuesta = (
                f"📹 **Nuevo auxilio a crear:**\n"
                + '\n'.join(f"  {p}" for p in partes_a)
                + "\n\n¿Confirmar la creación?"
            )
            accion = {
                'tipo': 'confirmar_auxilio',
                'fecha': fecha_final_a,
                'hora': hora_str,
                'tipo_auxilio': tipo_aux_c,
                'tipo_nombre': tipo_nom_c,
                'tribunal': tribunal_c,
                'procedimiento': proc_aux,
                'plaza': plaza_str or ''
            }
        else:
            faltantes_a = []
            if not fecha_final_a: faltantes_a.append('fecha')
            if not hora_str: faltantes_a.append('hora')
            respuesta = (
                f"📹 Para crear un auxilio necesito:\n"
                + '\n'.join(f"  {p}" for p in partes_a) + '\n'
                + f"  ⚠️ Falta: {', '.join(faltantes_a)}\n\n"
                f"Ejemplo: «crear videoconferencia el 20/03 a las 10:00 con el Juzgado de Pontevedra»"
            )
            accion = {'tipo': 'navegar_modulo', 'modulo': 'auxilios'}
        contexto_groq = (
            f"Crear auxilio: tipo={tipo_nom_c}, fecha={fecha_final_a}, "
            f"hora={hora_str}, tribunal={tribunal_c}"
        )

    # ── NAVEGAR ──────────────────────────────────────────────────────────────
    elif intencion == 'navegar':
        if fecha_str:
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str}
            respuesta = f"📅 Navegando a {_fmt_fecha(fecha_str)} en la agenda."
        else:
            respuesta = "¿A qué fecha quieres ir? Por ejemplo: «ir al 15 de marzo»."

    # ── SEMANA ───────────────────────────────────────────────────────────────
    elif intencion == 'semana':
        if semana:
            ini, fin = semana
        else:
            lunes = hoy - timedelta(hoy.weekday())
            ini, fin = lunes, lunes + timedelta(6)
        dias_rango = [(ini + timedelta(i)).isoformat() for i in range(7)]
        filtro = [s for s in senalamientos
                  if s.get('fecha','') in dias_rango
                  and not s.get('anulado')
                  and (not plaza_str or s.get('plaza','') == plaza_str)]
        por_dia = {}
        for s in filtro:
            por_dia.setdefault(s['fecha'], []).append(s)
        p_txt = f" en {plaza_str}" if plaza_str else ''
        lineas = [f"📅 Semana del {ini.strftime('%d/%m')} al {fin.strftime('%d/%m')}{p_txt}:"]
        if por_dia:
            for d in dias_rango:
                if d in por_dia:
                    lineas.append(f"  {_fmt_fecha(d)} ({len(por_dia[d])} señalamientos)")
        else:
            lineas.append("  Sin señalamientos esta semana.")
        respuesta = '\n'.join(lineas)
        accion = {'tipo': 'navegar_agenda', 'fecha': ini.isoformat()}
        # Contexto anonimizado para Groq (sin partes ni expediente)
        if filtro:
            contexto_groq = (f"Semana del {ini.strftime('%d/%m')} al {fin.strftime('%d/%m')}:\n"
                             + '\n'.join(str(_anonimizar_senalamiento(s)) for s in filtro[:30]))
        else:
            contexto_groq = f"Sin señalamientos la semana del {ini.strftime('%d/%m')} al {fin.strftime('%d/%m')}."

    # ── MES COMPLETO ──────────────────────────────────────────────────────────
    elif intencion == 'mes':
        if mes_info:
            year, mes = mes_info
        else:
            year, mes = hoy.year, hoy.month
        mes_nombre = list(_MESES_ES.keys())[mes - 1]
        prefijo_mes = f"{year}-{mes:02d}"
        filtro = [s for s in senalamientos
                  if s.get('fecha', '')[:7] == prefijo_mes
                  and not s.get('anulado')
                  and (not plaza_str or s.get('plaza', '') == plaza_str)
                  and (not tipo_str or tipo_str.lower() in s.get('tipo', '').lower())]
        filtro = sorted(filtro, key=lambda x: (x.get('fecha', ''), x.get('plaza', ''), x.get('hora', '')))
        p_txt = f" — {plaza_str}" if plaza_str else ''
        t_txt = f" — tipo {tipo_str}" if tipo_str else ''
        if filtro:
            por_dia = {}
            for s in filtro:
                por_dia.setdefault(s['fecha'], []).append(s)
            lineas = [f"📋 {mes_nombre.capitalize()} {year}{p_txt}{t_txt}: {len(filtro)} señalamientos"]
            for dia in sorted(por_dia.keys()):
                ss = por_dia[dia]
                lineas.append(f"\n  📅 {_fmt_fecha(dia)} ({len(ss)}):")
                for s in ss:
                    lineas.append(_fmt_senalamiento(s))
            respuesta = '\n'.join(lineas)
        else:
            p_txt2 = f" en {plaza_str}" if plaza_str else ''
            t_txt2 = f" de tipo {tipo_str}" if tipo_str else ''
            respuesta = f"No hay señalamientos en {mes_nombre} {year}{p_txt2}{t_txt2}."
        accion = {'tipo': 'navegar_agenda', 'fecha': f"{year}-{mes:02d}-01"}
        # Contexto anonimizado para Groq (sin partes ni expediente)
        if filtro:
            contexto_groq = (f"{mes_nombre.capitalize()} {year}:\n"
                             + '\n'.join(str(_anonimizar_senalamiento(s)) for s in filtro[:30]))
        else:
            contexto_groq = f"Sin señalamientos en {mes_nombre} {year}."

    # ── SEÑALAMIENTOS DEL DÍA (por defecto) ──────────────────────────────────
    else:  # senalamiento_dia
        # Si hay mes pero no día concreto, derivar al handler de mes
        if mes_info and not fecha_str:
            year, mes = mes_info
            mes_nombre = list(_MESES_ES.keys())[mes - 1]
            prefijo_mes = f"{year}-{mes:02d}"
            filtro = [s for s in senalamientos
                      if s.get('fecha', '')[:7] == prefijo_mes
                      and not s.get('anulado')
                      and (not plaza_str or s.get('plaza', '') == plaza_str)
                      and (not tipo_str or tipo_str.lower() in s.get('tipo', '').lower())]
            filtro = sorted(filtro, key=lambda x: (x.get('fecha', ''), x.get('plaza', ''), x.get('hora', '')))
            p_txt = f" — {plaza_str}" if plaza_str else ''
            t_txt = f" — tipo {tipo_str}" if tipo_str else ''
            if filtro:
                por_dia = {}
                for s in filtro:
                    por_dia.setdefault(s['fecha'], []).append(s)
                lineas = [f"📋 {mes_nombre.capitalize()} {year}{p_txt}{t_txt}: {len(filtro)} señalamientos"]
                for dia in sorted(por_dia.keys()):
                    ss = por_dia[dia]
                    lineas.append(f"\n  📅 {_fmt_fecha(dia)} ({len(ss)}):")
                    for s in ss:
                        lineas.append(_fmt_senalamiento(s))
                respuesta = '\n'.join(lineas)
            else:
                p_txt2 = f" en {plaza_str}" if plaza_str else ''
                t_txt2 = f" de tipo {tipo_str}" if tipo_str else ''
                respuesta = f"No hay señalamientos en {mes_nombre} {year}{p_txt2}{t_txt2}."
            accion = {'tipo': 'navegar_agenda', 'fecha': f"{year}-{mes:02d}-01"}
            # Contexto anonimizado para Groq (sin partes ni expediente)
            if filtro:
                contexto_groq = (f"{mes_nombre.capitalize()} {year}:\n"
                                 + '\n'.join(str(_anonimizar_senalamiento(s)) for s in filtro[:30]))
            else:
                contexto_groq = f"Sin señalamientos en {mes_nombre} {year}."
        else:
            if not fecha_str:
                fecha_str = hoy.isoformat()
            filtro = [s for s in senalamientos
                      if s.get('fecha', '') == fecha_str
                      and not s.get('anulado')
                      and (not plaza_str or s.get('plaza', '') == plaza_str)
                      and (not tipo_str or tipo_str.lower() in s.get('tipo', '').lower())]
            filtro = sorted(filtro, key=lambda x: (x.get('plaza', ''), x.get('hora', '')))
            p_txt = f" en {plaza_str}" if plaza_str else ''
            t_txt = f" — tipo {tipo_str}" if tipo_str else ''
            if filtro:
                lineas = [f"📋 Señalamientos el {_fmt_fecha(fecha_str)}{p_txt}{t_txt}: {len(filtro)}"]
                por_plaza = {}
                for s in filtro:
                    por_plaza.setdefault(s.get('plaza', 'Sin plaza'), []).append(s)
                for pl, ss in sorted(por_plaza.items()):
                    lineas.append(f"  🏛️ {pl}:")
                    for s in ss:
                        lineas.append(_fmt_senalamiento(s))
                respuesta = '\n'.join(lineas)
            else:
                p_txt2 = f" para {plaza_str}" if plaza_str else ''
                t_txt2 = f" de tipo {tipo_str}" if tipo_str else ''
                respuesta = f"No hay señalamientos el {_fmt_fecha(fecha_str)}{p_txt2}{t_txt2}."
            accion = {'tipo': 'navegar_agenda', 'fecha': fecha_str}
            # Contexto anonimizado para Groq (sin partes ni expediente)
            if filtro:
                contexto_groq = (f"Señalamientos el {_fmt_fecha(fecha_str)}:\n"
                                 + '\n'.join(str(_anonimizar_senalamiento(s)) for s in filtro[:20]))
            else:
                p_c = f" para {plaza_str}" if plaza_str else ''
                contexto_groq = f"Sin señalamientos el {_fmt_fecha(fecha_str)}{p_c}."

    # ── Mejorar respuesta con LLM (según modo configurado) ─────────────────────
    # Modos: 'reglas' (solo reglas), 'ia' (LLM reemplaza), 'combinado' (reglas + LLM enriquece)
    fuente        = 'reglas'
    fuente_nombre = 'Motor de reglas'
    llm_error     = None
    prov_id_act, prov_act, key_act, _ = _llm_cfg()
    cfg_modo = (cargar_json(F_CONFIG_LLM) or {}).get('modo', 'reglas')
    if respuesta and key_act and cfg_modo in ('ia', 'combinado'):
        if cfg_modo == 'combinado':
            llm_ctx = respuesta  # reglas ya formateadas como contexto
        else:
            llm_ctx = contexto_groq if contexto_groq else respuesta
        llm_txt, llm_error = _llamar_llm(llm_ctx, pregunta, intencion, modo_combinado=(cfg_modo == 'combinado'))
        if llm_txt:
            respuesta     = llm_txt
            fuente        = prov_id_act
            fuente_nombre = prov_act['nombre'] if prov_act else prov_id_act

    return jsonify({
        'respuesta':    respuesta or 'No encontré información para esa consulta.',
        'accion':       accion,
        'intencion':    intencion,
        'fuente':       fuente,
        'fuente_nombre':fuente_nombre,
        'groq_error':   llm_error,   # campo mantenido por compatibilidad con el cliente
        '_debug': {
            'fecha_str':   fecha_str,
            'plaza_str':   plaza_str,
            'tipo_str':    tipo_str,
            'ctx_preview': contexto_groq[:300] if contexto_groq else '(vacío)'
        }
    })


# ══════════════════════════════════════════════
# DIRECTORIO DIR3
# ══════════════════════════════════════════════
_dir3_cache = None
_dir3_cache_ts = 0

def _cargar_dir3():
    """Carga y cachea los datos DIR3 en memoria (~18 MB JSON).
    Busca primero en la carpeta local del servidor (más rápido),
    y si no existe, busca en DATOS_DIR (red)."""
    global _dir3_cache, _dir3_cache_ts
    # Prioridad: local (junto al servidor) > red (DATOS_DIR)
    ruta_local = os.path.join(BASE_DIR, 'datos', 'dir3.json')
    ruta = ruta_local if os.path.exists(ruta_local) else F_DIR3
    try:
        mtime = os.path.getmtime(ruta)
    except OSError:
        mtime = 0
    if _dir3_cache is not None and mtime == _dir3_cache_ts:
        return _dir3_cache
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log(f"Error cargando DIR3 desde {ruta}: {e}", 'ERROR')
        data = {}
    _dir3_cache = data
    _dir3_cache_ts = mtime
    return data

@app.route('/api/dir3/buscar')
def dir3_buscar():
    """Busca en el directorio DIR3. Params: q (texto), nivel, comunidad, provincia, limit."""
    data = _cargar_dir3()
    if not data or 'registros' not in data:
        return jsonify({'resultados': [], 'total': 0, 'filtros': {}})

    q = _sin_acentos((request.args.get('q') or '').strip().lower())
    nivel = (request.args.get('nivel') or '').strip()
    comunidad = (request.args.get('comunidad') or '').strip()
    provincia = (request.args.get('provincia') or '').strip()
    limite = min(int(request.args.get('limit') or 100), 500)

    # Si no hay query ni filtros, devolver solo los filtros disponibles
    if not q and not nivel and not comunidad and not provincia:
        return jsonify({'resultados': [], 'total': 0, 'filtros': data.get('filtros', {})})

    # Separar palabras de búsqueda
    palabras = q.split() if q else []

    resultados = []
    for r in data['registros']:
        # Filtros rápidos primero
        if nivel and r.get('nv', '') != nivel:
            continue
        if comunidad and r.get('cm', '') != comunidad:
            continue
        if provincia and r.get('pr', '') != provincia:
            continue
        # Búsqueda por texto: todas las palabras deben aparecer en algún campo
        if palabras:
            texto = _sin_acentos(' '.join([
                r.get('co',''), r.get('no',''),
                r.get('cu',''), r.get('nu',''),
                r.get('cr',''), r.get('nr',''),
                r.get('cm',''), r.get('pr','')
            ]).lower())
            if not all(p in texto for p in palabras):
                continue
        resultados.append(r)
        if len(resultados) >= limite:
            break

    total = len(resultados)
    return jsonify({'resultados': resultados, 'total': total, 'filtros': data.get('filtros', {})})

@app.route('/api/dir3/filtros')
def dir3_filtros():
    """Devuelve solo los filtros disponibles (niveles, comunidades, provincias)."""
    data = _cargar_dir3()
    if not data:
        return jsonify({'niveles': [], 'comunidades': [], 'provincias': []})
    return jsonify(data.get('filtros', {}))

@app.route('/api/dir3/debug')
def dir3_debug():
    """Diagnóstico temporal para verificar carga de DIR3."""
    ruta_local = os.path.join(BASE_DIR, 'datos', 'dir3.json')
    info = {
        'BASE_DIR': BASE_DIR,
        'DATOS_DIR': DATOS_DIR,
        'F_DIR3': F_DIR3,
        'ruta_local': ruta_local,
        'existe_local': os.path.exists(ruta_local),
        'existe_F_DIR3': os.path.exists(F_DIR3),
    }
    # Tamaño si existe
    for key in ['ruta_local', 'F_DIR3']:
        path = info[key] if key == 'F_DIR3' else ruta_local
        if os.path.exists(path):
            info[f'size_{key}_MB'] = round(os.path.getsize(path) / 1024 / 1024, 2)
    # Intentar cargar
    data = _cargar_dir3()
    info['cache_tiene_datos'] = bool(data)
    info['cache_tiene_registros'] = 'registros' in data if data else False
    info['num_registros'] = len(data.get('registros', [])) if data else 0
    return jsonify(info)


# ── Endpoint de sincronización de nombres ────────────────────────────────────

@app.route('/api/nombres/sincronizar', methods=['POST'])
def sincronizar_nombre():
    """Busca y opcionalmente reemplaza un nombre en todos los JSONs del portal."""
    datos_req   = request.get_json(force=True) or {}
    nombre_viejo = datos_req.get('nombre_viejo', '').strip()
    nombre_nuevo = datos_req.get('nombre_nuevo', '').strip()
    confirmar    = datos_req.get('confirmar', False)

    if not nombre_viejo:
        return jsonify({'success': False, 'error': 'nombre_viejo requerido'})

    # Ficheros donde buscar
    ficheros_buscar = [F_AGENDA, F_GUARDIAS, F_VENCIMIENTOS, F_VACACIONES,
                       F_MINUTAS, F_CORREOS, F_AUXILIOS]
    # Añadir ficheros de usuarios y grupos
    try:
        for uid_dir in (os.listdir(DATOS_USR_DIR) if os.path.isdir(DATOS_USR_DIR) else []):
            ud = os.path.join(DATOS_USR_DIR, uid_dir)
            if os.path.isdir(ud):
                for fj in os.listdir(ud):
                    if fj.endswith('.json'):
                        ficheros_buscar.append(os.path.join(ud, fj))
        for gid_dir in (os.listdir(GRUPOS_DIR) if os.path.isdir(GRUPOS_DIR) else []):
            gd = os.path.join(GRUPOS_DIR, gid_dir)
            if os.path.isdir(gd):
                for fj in os.listdir(gd):
                    if fj.endswith('.json'):
                        ficheros_buscar.append(os.path.join(gd, fj))
    except Exception:
        pass

    preview = {}
    errores = []

    for ruta in ficheros_buscar:
        if not ruta or not os.path.isfile(ruta):
            continue
        try:
            if confirmar and nombre_nuevo:
                # Lock transaccional: mantener lock durante lectura+escritura
                with editar_json(ruta) as datos:
                    contenido = json.dumps(datos, ensure_ascii=False, indent=2)
                    count = contenido.count(nombre_viejo)
                    if count == 0:
                        continue
                    nombre_corto = os.path.relpath(ruta, DATOS_DIR)
                    preview[nombre_corto] = count
                    nuevo_contenido = contenido.replace(nombre_viejo, nombre_nuevo)
                    nuevos_datos = json.loads(nuevo_contenido)
                    datos.clear()
                    datos.update(nuevos_datos)
                    log(f"Sincronizar nombre: {nombre_viejo}→{nombre_nuevo} en {nombre_corto} ({count} veces)")
            else:
                # Solo preview: lectura sin lock (no modifica)
                datos = cargar_json(ruta)
                if datos is None:
                    continue
                contenido = json.dumps(datos, ensure_ascii=False, indent=2)
                count = contenido.count(nombre_viejo)
                if count == 0:
                    continue
                nombre_corto = os.path.relpath(ruta, DATOS_DIR)
                preview[nombre_corto] = count
        except LockError as ex:
            errores.append(f"No se pudo bloquear {ruta}: {ex}")
        except Exception as ex:
            errores.append(str(ex))

    total = sum(preview.values())
    return jsonify({
        'success': True,
        'preview': preview,
        'total_ocurrencias': total,
        'aplicado': confirmar and bool(nombre_nuevo),
        'errores': errores
    })


if __name__ == '__main__':
    # ── Argumentos ──────────────────────────────────────────
    parser = argparse.ArgumentParser(description='Portal Judicial')
    parser.add_argument('--red', action='store_true',
                        help='Modo red: escucha en todas las interfaces (0.0.0.0)')
    parser.add_argument('--puerto', type=int, default=0,
                        help='Puerto fijo (0 = automático)')
    args, _ = parser.parse_known_args()

    modo_red = args.red or os.environ.get('PORTAL_RED', '') == '1'

    print("=" * 62)
    print("  PORTAL JUDICIAL UNIFICADO")
    print("  Tribunal de Instancia de Vilagarcía de Arousa")
    if modo_red:
        print("  MODO RED — accesible desde otros ordenadores")
    print("=" * 62)

    inicializar_datos()
    _generar_glosario_si_falta()   # genera glosario_ia.txt si no existe
    puerto = args.puerto if args.puerto else puerto_libre()

    # Arrancar scheduler de backup automático si está configurado
    _arrancar_scheduler_backup()

    host = '0.0.0.0' if modo_red else '127.0.0.1'
    ip_lan = _obtener_ip_lan() if modo_red else 'localhost'
    url_local  = f'http://localhost:{puerto}'
    url_red    = f'http://{ip_lan}:{puerto}'

    log(f"Servidor iniciado en {host}:{puerto}")
    print(f"\n  URL local:  {url_local}")
    if modo_red:
        print(f"  URL en red: {url_red}  ← comparte esta URL con los demás PCs")
        # Guardar URL en fichero compartido para que ACCEDER_PORTAL.bat la lea
        try:
            url_file = os.path.normpath(os.path.join(CONFIG_DIR, 'servidor_url.txt'))
            os.makedirs(os.path.dirname(url_file), exist_ok=True)
            with open(url_file, 'w', encoding='utf-8') as f:
                f.write(url_red)
        except Exception as e:
            print(f"  (no se pudo guardar URL en fichero: {e})")
    print("\n  Cierra esta ventana o pulsa Ctrl+C para detener\n")

    threading.Thread(target=abrir_navegador, args=(url_local,), daemon=True).start()

    try:
        app.run(host=host, port=puerto, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        log("Servidor detenido por el usuario")
        print("\n  Servidor cerrado correctamente.")
