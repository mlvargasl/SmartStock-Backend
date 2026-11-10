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

## 6. Iniciar el backend

```bash
uvicorn app.main:app --reload --port 8001
```

La API estará disponible en `http://localhost:8001`. El frontend está configurado por defecto para conectarse al puerto `8001`.
