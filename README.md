# Programacion Energia Excel Cloud

App separada para publicar en Streamlit Community Cloud.

Esta version no usa Wrike. El flujo es:

1. Administrador carga un Excel del programa.
2. Contratistas/cuadrillas ingresan al link desde celular, tablet o PC.
3. Informan avances y comentarios.
4. Administrador exporta Excel con el log o el estado final.

## Archivos

- `app.py`: punto de entrada de Streamlit (arranca la app definida en `pe/`).
- `pe/`: codigo de la aplicacion, organizado en modulos:
  - `config.py`: constantes y secretos.
  - `textutils.py`: normalizacion de texto, areas, empresas y sectores.
  - `supabase_client.py`: llamadas HTTP a la API REST de Supabase.
  - `data.py`: mapeo del Excel y carga de programas/tareas.
  - `advances.py`: avances (altas, borrado, estado vigente por tarea).
  - `filters.py`: filtros del tablero (empresa, sector, cuadrilla, fechas, busqueda).
  - `export.py`: exportacion a Excel (log, estado final, Wrike, programa actualizado).
  - `timeutil.py`: fechas/horas en huso horario local.
  - `session_ui.py`: navegacion y estado pendiente de guardar.
  - `ui/`: pantallas (login, perfil, panel admin, resumen/dashboard, tablero de tareas).
- `requirements.txt`: dependencias para Streamlit Cloud.
- `supabase_schema.sql`: tablas para pegar en Supabase SQL Editor.
- `.streamlit/secrets.toml.example`: ejemplo de secretos.

## Resumen del programa

Arriba del tablero de tareas se muestra un panel "Resumen del programa" con
indicadores del programa activo (segun la empresa/sector del perfil que
entro): total de tareas, completadas, en curso, en espera/a replanificar,
tareas vencidas sin completar, un grafico de tareas por estado y una tabla de
avance por empresa/sector.

## Pasos

1. En Supabase abrir `SQL Editor`.
2. Crear `New query`.
3. Pegar el contenido de `supabase_schema.sql`.
4. Ejecutar `Run`.
5. Subir estos archivos al repositorio GitHub `programacion-energia-excel`.
6. En Streamlit Community Cloud crear una app desde ese repositorio.
7. Configurar Secrets:

```toml
SUPABASE_URL = "https://xxxxxxxxxxxxxxxxxxxx.supabase.co"
SUPABASE_KEY = "sb_publishable_xxxxxxxxxxxxxxxxxxxx"
ACCESS_PASSWORD = "CAMBIAR_ESTA_CLAVE"
ADMIN_PASSWORD = "CAMBIAR_ESTA_CLAVE_ADMIN"
```

## Excel

La app intenta reconocer columnas comunes:

- OT: `OT`, `Nro OT`, `Nro de OT`
- Trabajo: `Trabajo`, `Tarea`, `Descripcion`, `Nombre`
- Empresa
- Sector
- Cuadrilla
- Fecha inicio
- Fecha fin / vencimiento
- Estado
- Ubicacion tecnica
- KKS/TAG

Si el Excel tiene nombres distintos se puede ajustar el mapeo en `app.py`.
