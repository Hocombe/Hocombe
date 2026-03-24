# Archivos modificados - Sesiones recientes

## Fecha: 03/03/2026

---

## CARPETA `Portal_Judicial/` — 7 archivos

### 1. `portal.html`
- Glosario de ayuda con 15 módulos + tabla de palabras clave + consejos
- 3 módulos nuevos en ayuda: NotificaJud/SCACE, Guardias, Ausencias
- Tamaños de fuente de ayuda aumentados (accesibilidad)
- Eliminado localStorage (posiciones chat, globo IA, orden pestañas)
- Burbuja de chat reposicionada (no solapaba con asistente IA)
- Botones de navegación de pestañas: estilo circular flotante con chevrons
- Opción ausencias añadida al dropdown de restaurar backup
- Ventana horaria de backups (inputs hora inicio/fin en config)

### 2. `servidor.py`
- Keywords de clipbox, minutas y ayuda añadidos al glosario de intención
- Detección regex para clipbox, minutas y ayuda en el asistente IA
- Handlers del asistente IA para clipbox, minutas y ayuda
- Ventana horaria de backups (hora_inicio/hora_fin en config + lógica scheduler)
- Endpoints de ausencias (/api/ausencias, /api/ausencias/activas)

### 3. `notificajud.html`
- TipoActo se lleva al Historial desde la ejecución de diligencias
- Ejecución directa (sin modal) desde registro con estado Positivo/Negativo
- Fecha+hora en Historial (recoge del reloj del portal)
- Fix crash renderizarRegistro (accionesFinal undefined)
- Fix generarIdSACE contador por prefijo
- Eliminada stat "Recicladas" e icono reciclaje

### 4. `instruccion_penal.html`
- Eliminado localStorage (fallback datos y listas)

### 5. `guardias.html`
- Eliminado localStorage (backup de cuadrante)

### 6. `boletin.html`
- Eliminado localStorage (filtros de vista)

### 7. `correos.html`
- Eliminado localStorage (tema oscuro/claro y ancho panel)

---

## CARPETA `modulos/Ausencias/` — 1 archivo (MÓDULO NUEVO)

### 8. `modulos/Ausencias/index.html`
- Módulo completo de ausencias de plazas (magistrados, letrados, fiscales...)
- Banner automático en cabecera del portal con ausencias activas
- Registro de motivos, sustitutos y fechas

---

## Resumen: qué copiar

```
DESDE TU PC LOCAL                          →  DESTINO EN Z:
─────────────────────────────────────────────────────────────
Portal_Judicial/portal.html                →  Z:\...\Portal_Judicial\
Portal_Judicial/servidor.py                →  Z:\...\Portal_Judicial\
Portal_Judicial/notificajud.html           →  Z:\...\Portal_Judicial\
Portal_Judicial/instruccion_penal.html     →  Z:\...\Portal_Judicial\
Portal_Judicial/guardias.html              →  Z:\...\Portal_Judicial\
Portal_Judicial/boletin.html               →  Z:\...\Portal_Judicial\
Portal_Judicial/correos.html               →  Z:\...\Portal_Judicial\
modulos/Ausencias/index.html               →  Z:\...\modulos\Ausencias\
```

**Total: 8 archivos** en vez de copiar toda la carpeta.

---

## Después de copiar

1. Los usuarios que tengan el portal abierto deben refrescar con F5
2. Si alguien tiene el servidor Python corriendo, debe reiniciarlo
   (para que coja los cambios de servidor.py)
