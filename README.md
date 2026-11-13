# SmartStock Backend
FastAPI y PostgreSQL.

## 1. Crear el entorno virtual e instalar dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

En Windows, activa el entorno con `.venv\Scripts\activate`.

## 2. Configurar PostgreSQL

Si ya tienes PostgreSQL y una base de datos para SmartStock, utiliza sus datos de conexión en el siguiente paso. Para crear una base local de desarrollo con Docker:

```bash
docker run --name smartstock-postgres \
  -e POSTGRES_USER=smartstock \
  -e POSTGRES_PASSWORD=smartstock \
  -e POSTGRES_DB=smartstock \
  -p 5432:5432 \
  -d postgres:16
```

Si ya creaste ese contenedor, inícialo con `docker start smartstock-postgres`. Las credenciales del ejemplo son solo para desarrollo.

## 3. Configurar las variables de entorno

Completa el archivo `.env`, copia el archivo de ejemplo `.env.example`


## 4. Migrar

Con PostgreSQL iniciado y el entorno virtual activado:

```bash
alembic upgrade head
```

## 5. Crear datos de desarrollo (opcional)

Completa en `.env` las variables `SEED_ADMIN_*`, `SEED_PRODUCTION_*` y `SEED_INVENTORY_*`. Los correos deben ser distintos y las contraseñas deben tener al menos ocho caracteres. Después ejecuta:

```bash
python -m app.seed
```

El seed crea cuentas y datos de ejemplo para desarrollo. No cambia las contraseñas de usuarios que ya existen.

Para tener historial de ventas de demostración, después de migrar y ejecutar el seed:

```bash
python -m app.generate_synthetic_sales --days 365
```

En Windows, desde la raíz del proyecto, ejecuta ` .\.venv\Scripts\python.exe -m app.generate_synthetic_sales --days 365`. Los registros quedan marcados con origen `SYNTHETIC` y se pueden volver a cargar; las cantidades y el clima sintético se actualizan de forma reproducible. Son datos artificiales para desarrollar y probar la interfaz; no representan la demanda real ni deben usarse para decisiones de producción.

## Pronóstico de demanda

Después de aplicar migraciones y generar el historial sintético, consulta `GET /api/forecast/demand?day=AAAA-MM-DD` (opcionalmente `&product_id=1`) con una fecha entre hoy y los próximos 15 días. El resultado incluye unidades estimadas por producto, clima consultado y las fuentes/fechas usadas para entrenar. El modelo inicial es una regresión lineal Ridge con día de semana, estacionalidad anual, temperatura y precipitación. Requiere al menos 30 días de historial y señala `data_quality: synthetic` mientras use datos sintéticos.

Para reemplazar el clima sintético por observaciones históricas reales de Open-Meteo: `python -m app.import_weather_history --days 365`. Luego configura `DEMAND_WEATHER_SOURCES=Open-Meteo`. Cuando importes ventas reales, configura `DEMAND_SALES_SOURCES` con sus orígenes (por ejemplo `IMPORT,MANUAL,EXTERNAL`) para entrenar solo con esas ventas. El modelo lee las transacciones desde la base; no depende de archivos sintéticos específicos.

## 6. Iniciar el backend

```bash
uvicorn app.main:app --reload --port 8001
```

La API estará disponible en `http://localhost:8001`. El frontend está configurado por defecto para conectarse al puerto `8001`.
