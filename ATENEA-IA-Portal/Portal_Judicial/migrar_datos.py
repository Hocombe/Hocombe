#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrar_datos.py
---------------
Script de MIGRACIÓN única — ejecutar solo la primera vez.
Copia los datos existentes de cada aplicación al Portal Unificado.

Origen → Destino:
  AgendaJudicial/datos/datos_agenda.db  → datos/agenda.json
  GestionVacaciones/vacaciones_tribunal_data.json → datos/vacaciones.json
  peritos_portable/data/*.json → datos/peritos.json
  app-boletin/boletin.db → datos/boletin.json (best-effort)
  clipbox: IndexedDB → no migrable automáticamente (exportar manualmente)
  vencimientos: localStorage → exportar manualmente desde el navegador

INSTRUCCIONES:
  1. Cierra todas las aplicaciones antes de ejecutar.
  2. Ejecuta: python migrar_datos.py
  3. Revisa el informe al final.
  4. Arranca el Portal con Iniciar.vbs
"""

import os
import sys
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# ─── Rutas ─────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
APPS_DIR   = os.path.dirname(BASE)
DATOS_DIR  = os.path.join(BASE, 'datos')
BACKUP_DIR = os.path.join(BASE, 'backups', 'migracion_' + datetime.now().strftime('%Y%m%d_%H%M%S'))

os.makedirs(DATOS_DIR,  exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

informe = []

def ok(msg):  print(f'  ✅ {msg}'); informe.append(('OK',  msg))
def warn(msg):print(f'  ⚠️  {msg}'); informe.append(('WARN',msg))
def err(msg): print(f'  ❌ {msg}'); informe.append(('ERR', msg))

def guardar_json(ruta, datos):
    tmp = ruta + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)

def cargar_json_safe(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return None

# ═══════════════════════════════════════════════════════
# 1. AGENDA JUDICIAL — SQLite → JSON
# ═══════════════════════════════════════════════════════
print('\n📅  AGENDA JUDICIAL')
db_agenda = os.path.join(APPS_DIR, 'AgendaJudicial', 'datos', 'datos_agenda.db')
dest_agenda = os.path.join(DATOS_DIR, 'agenda.json')

if os.path.exists(db_agenda):
    try:
        conn = sqlite3.connect(db_agenda, timeout=10)
        conn.row_factory = sqlite3.Row

        senalamientos = [dict(r) for r in conn.execute('SELECT * FROM senalamientos').fetchall()]
        guardias      = [dict(r) for r in conn.execute('SELECT * FROM guardias').fetchall()]
        plazas_raw    = [dict(r) for r in conn.execute('SELECT * FROM plazas').fetchall()]
        letrados_raw  = [dict(r) for r in conn.execute('SELECT * FROM letrados').fetchall()]
        conn.close()

        plazas   = [p['nombre'] for p in plazas_raw] if plazas_raw else []
        letrados = [l['nombre'] for l in letrados_raw] if letrados_raw else []

        # Respetar datos actuales del portal si ya existe
        actual = cargar_json_safe(dest_agenda) or {}
        actual.update({
            'senalamientos': senalamientos,
            'guardias':      guardias,
            'plazas':        plazas   or actual.get('plazas', []),
            'letrados':      letrados or actual.get('letrados', []),
        })
        guardar_json(dest_agenda, actual)
        ok(f'{len(senalamientos)} señalamientos, {len(guardias)} guardias migrados')
    except Exception as e:
        err(f'Error leyendo SQLite de agenda: {e}')
else:
    warn(f'No encontrado: {db_agenda}')
    warn('La agenda empezará vacía (se creará al iniciar el portal)')

# ═══════════════════════════════════════════════════════
# 2. GESTIÓN DE VACACIONES — JSON → JSON
# ═══════════════════════════════════════════════════════
print('\n🏖️  GESTIÓN DE VACACIONES')
src_vac  = os.path.join(APPS_DIR, 'GestionVacaciones', 'vacaciones_tribunal_data.json')
dest_vac = os.path.join(DATOS_DIR, 'vacaciones.json')

if os.path.exists(src_vac):
    datos = cargar_json_safe(src_vac)
    if datos:
        shutil.copy2(src_vac, os.path.join(BACKUP_DIR, 'vacaciones_original.json'))
        guardar_json(dest_vac, datos)
        funcionarios = len(datos.get('funcionarios', []))
        ok(f'{funcionarios} funcionarios migrados')
    else:
        err('El archivo de vacaciones no es JSON válido')
else:
    warn(f'No encontrado: {src_vac}')
    warn('Las vacaciones empezarán vacías')

# ═══════════════════════════════════════════════════════
# 3. PERITOS JUDICIALES — JSON files → JSON unificado
# ═══════════════════════════════════════════════════════
print('\n🔬  PERITOS JUDICIALES')
data_dir_peritos = os.path.join(APPS_DIR, 'peritos_portable', 'data')
dest_peritos = os.path.join(DATOS_DIR, 'peritos.json')

if os.path.isdir(data_dir_peritos):
    esp = cargar_json_safe(os.path.join(data_dir_peritos, 'especialidades.json')) or []
    per = cargar_json_safe(os.path.join(data_dir_peritos, 'peritos.json')) or []
    sel = cargar_json_safe(os.path.join(data_dir_peritos, 'selecciones.json')) or []
    cfg = cargar_json_safe(os.path.join(data_dir_peritos, 'settings.json')) or {}

    datos_peritos = {
        'especialidades': esp,
        'peritos':        per,
        'selecciones':    sel,
        'settings':       cfg
    }
    guardar_json(dest_peritos, datos_peritos)
    ok(f'{len(esp)} especialidades, {len(per)} peritos, {len(sel)} selecciones migradas')
else:
    warn(f'No encontrada carpeta de datos de peritos: {data_dir_peritos}')
    warn('Peritos empezarán vacíos')

# ═══════════════════════════════════════════════════════
# 4. BOLETÍN — SQLite (Electron userData) → JSON
# ═══════════════════════════════════════════════════════
print('\n📰  BOLETÍN TRIMESTRAL')
# El .db de Electron está en AppData/Roaming/app-boletin/ (nombre exacto puede variar)
import glob as glob_mod
posibles_db = glob_mod.glob(
    os.path.join(os.environ.get('APPDATA', ''), '**', 'boletin.db'),
    recursive=True
)
dest_boletin = os.path.join(DATOS_DIR, 'boletin.json')

migrado_boletin = False
for db_path in posibles_db:
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        # Intentar leer tablas disponibles
        tablas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        datos_b = {'tablas': tablas, 'datos': {}, 'version': '1.0-migrado'}

        for tabla in tablas:
            try:
                filas = [dict(r) for r in conn.execute(f'SELECT * FROM {tabla}').fetchall()]
                datos_b['datos'][tabla] = filas
            except:
                pass
        conn.close()

        guardar_json(dest_boletin, datos_b)
        ok(f'Boletín migrado desde {db_path} — tablas: {", ".join(tablas)}')
        migrado_boletin = True
        break
    except Exception as e:
        warn(f'Error leyendo {db_path}: {e}')

if not migrado_boletin:
    warn('No se encontró boletin.db de la app Electron')
    warn('NOTA: El boletín usa una versión HTML reescrita.')
    warn('      Los datos anteriores NO se pueden migrar automáticamente.')
    warn('      Si tienes datos en la app Electron, exporta a PDF/CSV antes de usar el portal.')

# ═══════════════════════════════════════════════════════
# 5. CLIPBOX — IndexedDB (no migrable automáticamente)
# ═══════════════════════════════════════════════════════
print('\n📋  CLIPBOX — MODELOS DE RESOLUCIONES')
warn('ClipBox usa IndexedDB del navegador — no es accesible desde Python.')
warn('INSTRUCCIONES para migrar manualmente:')
warn('  1. Abre la app antigua: ClipBox (clipbox-app/index.html)')
warn('  2. Haz clic en "⬇️ JSON" (exportar JSON)')
warn('  3. Guarda el archivo como: clipbox_backup.json')
warn('  4. En el nuevo portal, ve a la pestaña Modelos')
warn('  5. Haz clic en "⬆️ JSON" (importar JSON)')
warn('  Los datos quedarán guardados en servidor, no en el navegador.')

# ═══════════════════════════════════════════════════════
# 6. CALCULADORA DE VENCIMIENTOS — localStorage
# ═══════════════════════════════════════════════════════
print('\n⏱️   CALCULADORA DE VENCIMIENTOS')
# Intentar encontrar vencimientos.json de la versión anterior
src_venc = os.path.join(APPS_DIR, 'Vencimiento_procesal', 'vencimientos.json')
src_venc2 = os.path.join(APPS_DIR, 'CalculadoraVencimientos_Portable_V3_FINAL', 'vencimientos.json')
dest_venc = os.path.join(DATOS_DIR, 'vencimientos.json')

migrado_venc = False
for src in [src_venc, src_venc2]:
    if os.path.exists(src):
        datos = cargar_json_safe(src)
        if datos:
            guardar_json(dest_venc, datos)
            ok(f'Vencimientos migrados desde {src}')
            migrado_venc = True
            break

if not migrado_venc:
    warn('No se encontró vencimientos.json')
    warn('INSTRUCCIONES para migrar manualmente:')
    warn('  1. Abre la calculadora antigua en el navegador')
    warn('  2. Haz clic en "Exportar JSON"')
    warn('  3. En el nuevo portal ve a Vencimientos → "Importar JSON"')
    warn('  4. Los datos quedarán en servidor, no en localStorage.')

# ═══════════════════════════════════════════════════════
# INFORME FINAL
# ═══════════════════════════════════════════════════════
print('\n' + '='*60)
print('  INFORME DE MIGRACIÓN')
print('='*60)
oks   = [m for t,m in informe if t=='OK']
warns = [m for t,m in informe if t=='WARN']
errs  = [m for t,m in informe if t=='ERR']
print(f'  ✅ Correctos: {len(oks)}')
print(f'  ⚠️  Advertencias: {len(warns)}')
print(f'  ❌ Errores: {len(errs)}')
print()
if errs:
    print('  ERRORES:')
    for m in errs: print(f'    • {m}')
    print()
print(f'  Backup de originales en: {BACKUP_DIR}')
print()
print('  PRÓXIMO PASO:')
print('  → Doble clic en Iniciar.vbs para arrancar el Portal')
print()
input('  Pulsa Enter para cerrar...')
