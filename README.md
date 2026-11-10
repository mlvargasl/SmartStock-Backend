# SmartStock — backend, primera etapa

API REST para una sucursal. Incluye autenticación JWT, roles, usuarios, catálogo, recetas, inventario y ventas manuales o CSV. El frontend existente no está conectado automáticamente.

## Estructura

- `app/api`: rutas y dependencias de autenticación y autorización.
- `app/core`: configuración, sesión PostgreSQL y seguridad.
- `app/models`, `app/schemas`: entidades y contratos.
- `app/repositories`, `app/services`: acceso a datos y reglas de negocio.
- `app/seed.py`: datos de ejemplo para desarrollo.
- `alembic/versions`: migración versionada; `tests`: pruebas de integración.

## Requisitos e instalación

Python 3.12 o superior y PostgreSQL 14 o superior. Desde la carpeta `SmartStock-Backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Crea el usuario y la base en PostgreSQL (los siguientes comandos son ejemplos locales):

```bash
psql -U postgres -c "CREATE USER smartstock WITH PASSWORD 'smartstock';"
psql -U postgres -c "CREATE DATABASE smartstock OWNER smartstock;"
```

Edita `.env`: configura `DATABASE_URL` con tus credenciales y define un `JWT_SECRET_KEY` largo y aleatorio, por ejemplo con `python -c 'import secrets; print(secrets.token_urlsafe(48))'`. Para ejecutar el seed, completa también todas las variables `SEED_*` indicadas en `.env.example`. `CORS_ORIGINS` admite orígenes separados por comas. El ejemplo de contraseña de PostgreSQL es solo para desarrollo. No compartas `.env` ni uses el seed en producción.

```bash
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Abre http://127.0.0.1:8000/docs. `POST /api/auth/login` recibe JSON y devuelve un bearer token; pulsa **Authorize** para probar rutas protegidas. Antes de ejecutar el seed, configura en `.env` los nombres, correos y contraseñas `SEED_ADMIN_*`, `SEED_PRODUCTION_*` y `SEED_INVENTORY_*`, según `.env.example`. Cada contraseña debe tener al menos ocho caracteres y los correos deben ser distintos. Las variables solo son necesarias para ejecutar el seed, no para iniciar la API. El seed no cambia las contraseñas ni los datos de usuarios existentes; modificar `.env` tampoco cambia sus credenciales. Los productos e ingredientes de ejemplo se definen en `app/seed.py`.

## Pruebas aisladas

Crea una base PostgreSQL dedicada cuyo nombre contenga `test`; el usuario debe poder crear y eliminar esquemas en ella. No apuntes `TEST_DATABASE_URL` a una base de producción. Las pruebas crean un esquema temporal único, aplican Alembic, revierten cada caso y eliminan el esquema al terminar.

```bash
psql -U postgres -c "CREATE DATABASE smartstock_test OWNER smartstock;"
export TEST_DATABASE_URL='postgresql+psycopg://smartstock:smartstock@localhost:5432/smartstock_test'
export JWT_SECRET_KEY='test-only-secret-key-at-least-32-characters'
python -m pytest -q
```

Para importar ventas usa multipart `file` con extensión `.csv`, codificación UTF-8 y columnas `fecha,producto,cantidad` (también se acepta `date,product,quantity`); el nombre del producto debe coincidir exactamente y estar activo. Se importan las filas válidas y se informan las rechazadas con su número de fila. El límite de archivo es 5 MiB. Los nombres de productos son únicos para resolver cada fila sin ambigüedad. Las cantidades de ingredientes se expresan en la unidad registrada; no se realizan conversiones automáticas. El resumen de ventas cuenta unidades y sus últimos siete días incluyen hoy, según la fecha local del servidor.

## Importación Excel y exportación

Se aceptan archivos `.csv` UTF-8 o `.xlsx` (máximo 5 MiB), con encabezados `fecha,producto,cantidad` o `date,product,quantity`. Se utiliza la primera hoja de Excel; las fechas pueden ser celdas de fecha o texto `AAAA-MM-DD`. Las filas inválidas se indican en la respuesta y las válidas se guardan. No se admiten fórmulas en las columnas de importación ni archivos `.xls`.

El botón **Exportar CSV** descarga el historial usando los filtros aplicados; el endpoint `GET /api/sales/export` acepta `product_id`, `start_date` y `end_date` y requiere un usuario autorizado para ventas. La exportación es UTF-8 con BOM y usa encabezados en español. Se antepone un apóstrofo a nombres que podrían interpretarse como fórmulas en hojas de cálculo.

Cuando un administrador importa una venta válida de un producto que aún no existe, el producto se crea automáticamente y la respuesta incluye `created_products` con su identificador y nombre para configurar su receta. Las filas inválidas no crean productos; los inactivos se rechazan. El jefe de producción puede importar productos existentes, pero las filas con productos desconocidos se rechazan indicando que debe crearlos un administrador. Los ingredientes creados desde la configuración comienzan con stock cero.

## Importar productos y recetas

El administrador puede usar `POST /api/products/import` con multipart `file`, CSV UTF-8 o Excel `.xlsx` (primera hoja). Columnas obligatorias: `producto,ingrediente,cantidad,unidad`; `stock_minimo` es opcional y solo se usa al crear un ingrediente. Una fila representa la cantidad de un ingrediente por unidad de producto:

```csv
producto,ingrediente,cantidad,unidad,stock_minimo
Torta,Harina,150,g,1000
Torta,Azúcar,20,g,500
```

Un producto sin receta se crea si es necesario y se asocia a la receta completa; los ingredientes nuevos se crean con inventario inicial cero. Los ingredientes existentes deben estar activos y tener la misma unidad, y su stock mínimo no cambia. Se rechaza todo el grupo de filas de un producto si alguna fila es inválida, si repite un ingrediente, o si el producto ya tiene receta o está inactivo. Los demás productos válidos se procesan y la respuesta informa las filas rechazadas. La importación está disponible solo para administradores.

El administrador y el jefe de producción pueden modificar cantidades de ingredientes existentes mediante `PATCH /api/recipes/{recipe_id}/ingredients/{ingredient_id}`. Esta operación exige una cantidad positiva y no permite añadir ni eliminar ingredientes; esas acciones siguen reservadas al administrador.

## Gestión de cuentas

Un administrador puede crear usuarios desde `POST /api/users/generated` enviando `name`, `email` y `role`. El servidor genera una clave inicial aleatoria y la devuelve una sola vez con el usuario; solo se guarda su hash. La respuesta lleva `Cache-Control: no-store`. Todos los roles pueden usar `POST /api/auth/change-password` con `current_password` y `new_password` (mínimo ocho caracteres). Un cambio de contraseña invalida los tokens anteriores y exige volver a iniciar sesión. Los tokens emitidos antes de esta actualización también dejarán de funcionar y cada usuario deberá autenticarse de nuevo.

## Contexto para pronóstico: clima y calendario de Chile

La sección de Pronóstico consulta datos externos para apoyar la futura estimación de ventas; todavía no calcula demanda ni recomendaciones. Administradores y jefes de producción pueden acceder a:

- `GET /api/forecast/context?day=AAAA-MM-DD`: clima y feriados/conmemoraciones del día solicitado, desde hoy hasta 15 días más, según la zona horaria de la sucursal.
- `GET /api/calendar/month?year=2026&month=11`: días del mes con eventos chilenos del calendario, diferenciando feriados legales y conmemoraciones. Se excluyen feriados regionales ajenos a la Región Metropolitana.

El clima proviene de [Open-Meteo](https://open-meteo.com/en/docs). Por defecto usa coordenadas referenciales del centro de Santiago y `America/Santiago`. Configura `WEATHER_LATITUDE`, `WEATHER_LONGITUDE`, `WEATHER_LOCATION_NAME` y `WEATHER_TIMEZONE` en `.env` si corresponde; la interfaz actualmente usa la zona horaria de Santiago para el selector de clima. El endpoint público de Open-Meteo es para evaluación y uso no comercial. Para uso comercial requiere una licencia/plan conforme a sus [términos](https://open-meteo.com/en/terms); configura `OPEN_METEO_API_KEY` para usar el endpoint comercial. El crédito a Open-Meteo aparece en la interfaz.

El calendario se obtiene de [api.restart.cl](https://api.restart.cl/calendario/), un proveedor independiente, no un organismo gubernamental. Se consultan eventos de Chile (no efemérides internacionales sin país) y se respeta el alcance regional. La información se entrega como contexto y depende de la cobertura y actualización del proveedor; no reemplaza la confirmación de una fuente oficial. Las respuestas indican por separado cuando alguno de los servicios no está disponible; la falta de datos nunca se presenta como ausencia de feriado. No se guardan respuestas externas en la base de datos.

## APIs externas para el backend

`WeatherService` y `CalendarService` ofrecen datos normalizados, sin depender de los JSON de terceros. El adaptador meteorológico usa [Open-Meteo](https://open-meteo.com/en/docs) y el de feriados y conmemoraciones usa [api.restart.cl](https://api.restart.cl/calendario/), filtrando Chile y los eventos regionales aplicables a Santiago. `day_of_week` usa 0 para lunes y 6 para domingo; el fin de semana se calcula localmente. Los proveedores reales no requieren clave para sus modalidades públicas. Las conmemoraciones informadas por api.restart.cl se devuelven como festividades; no son necesariamente feriados.

Configura en `.env` según `.env.example`:

- `WEATHER_API_URL` y `CALENDAR_API_URL`: URL base del proveedor o URL completa de su endpoint. Vacías utilizan los servicios públicos predeterminados.
- `WEATHER_API_KEY` y `CALENDAR_API_KEY`: opcionales; nunca deben versionarse. La clave de clima se envía a Open-Meteo como `apikey` y la de calendario en `x-api-key`. Si no se define `WEATHER_API_KEY`, se conserva la compatibilidad con `OPEN_METEO_API_KEY`.
- `SMARTSTOCK_LATITUDE` y `SMARTSTOCK_LONGITUDE`: coordenadas de la sucursal. Si quedan vacías, se usan los valores existentes `WEATHER_LATITUDE` y `WEATHER_LONGITUDE`; por defecto son coordenadas referenciales de Santiago. La zona horaria es `WEATHER_TIMEZONE`.
- `EXTERNAL_API_TIMEOUT_SECONDS`: tiempo máximo por operación HTTP; por defecto 5 segundos.
- `USE_MOCK_WEATHER` y `USE_MOCK_CALENDAR`: `true` activa el proveedor simulado correspondiente y `false` el real. Son independientes y el proveedor real nunca cae silenciosamente al mock.

Para probar sin conexión, configura `USE_MOCK_WEATHER=true` y `USE_MOCK_CALENDAR=true`, reinicia el backend, inicia sesión y usa el JWT recibido como Bearer token:

```bash
curl -H 'Authorization: Bearer <TOKEN>' 'http://localhost:8001/api/external/weather?date=2026-09-18'
curl -H 'Authorization: Bearer <TOKEN>' 'http://localhost:8001/api/external/calendar?date=2026-09-18'
curl -H 'Authorization: Bearer <TOKEN>' 'http://localhost:8001/api/external/context?date=2026-09-18'
```

Los tres roles autenticados pueden consultar estos endpoints. La fecha debe usar `AAAA-MM-DD`. El clima real usa temperatura **media diaria en °C**, precipitación acumulada **en mm**, probabilidad máxima **en porcentaje** y una condición normalizada; los campos opcionales pueden ser `null`. El proveedor meteorológico se consulta para un máximo de 15 días futuros y hasta 92 días pasados; fuera del rango se devuelve 422 y una fecha dentro del rango puede no estar disponible en el proveedor. En modo mock los datos son determinísticos y se identifican con `source`.

Errores de conexión, timeout, claves inválidas, respuestas HTTP fallidas o datos incompletos se devuelven como 503 con un detalle genérico. El endpoint combinado consulta los servicios en paralelo y devuelve error si uno falla. Los endpoints anteriores `/api/forecast/context` y `/api/calendar/month` mantienen su contrato de estados parciales para la interfaz existente. No se almacenan los resultados externos ni se realiza predicción de demanda.

La modalidad pública de Open-Meteo es para evaluación o uso no comercial; consulta sus [términos](https://open-meteo.com/en/terms) y configura un plan apropiado antes del uso comercial. El calendario es una fuente independiente y puede omitir eventos o cambiar; no reemplaza la confirmación oficial de los feriados.


La vista de recomendaciones muestra datos de demostración locales; no genera pronósticos ni confirma producción real. Las integraciones de clima y calendario continúan disponibles.

La migración `0006` elimina definitivamente las tablas y datos anteriores de pronósticos, recomendaciones y planificación. Las migraciones antiguas permanecen como historial para que las instalaciones existentes sigan siendo compatibles.

La vista de clima permite elegir entre 16 ciudades chilenas. `GET /api/external/weather` acepta opcionalmente `latitude` y `longitude` juntos y `time_zone` para consultar otra ubicación; si no se especifican, usa la ubicación configurada. `GET /api/calendar/month` acepta `region` (por defecto `CL-RM`) para incluir los feriados regionales correspondientes. Cambiar de ciudad en la vista no modifica la ubicación configurada de la sucursal.

## Ventas y preparación para integración

Las ventas nuevas se registran con una transacción y uno o más productos. La transacción guarda `sold_at` con zona horaria, el día local de la sucursal, origen (`MANUAL`, `IMPORT`, `EXTERNAL` o `LEGACY`), estado, e identificador externo opcional. Los productos pueden tener `external_code` único opcional. `POST /api/sale-transactions` recibe `sold_at` ISO 8601 con zona e `items` con `product_id` y `quantity`. Para `EXTERNAL`, `external_id` es obligatorio y único dentro de ese origen; un reintento duplicado devuelve 409. Los productos repetidos o inactivos se rechazan. `GET /api/sale-transactions` permite filtros de producto y fechas; `PATCH /api/sale-transactions/{id}/cancel` anula una transacción completa y registra quién y cuándo. El dashboard y la API anterior de ventas excluyen las anuladas.

La migración `0007` conserva cada fila anterior y su fecha sin inventar hora ni agrupar filas. Cada una se identifica como `LEGACY` y mantiene su ID; no se la trata como una compra comprobada. Los CSV/Excel anteriores siguen importándose por producto y fecha con origen `IMPORT`; no incorporan identificador, por lo cual **reimportar el mismo archivo puede duplicar datos**. No se conecta ninguna caja aún, no se procesan devoluciones parciales y no se descuentan ingredientes automáticamente. El origen externo representa un solo sistema lógico: antes de conectar varios proveedores se debe separar su identificador para evitar colisiones.

El frontend registra la hora en la zona del dispositivo y la envía con zona horaria; los días para filtros y resúmenes se calculan en la zona configurada de la sucursal. `sold_at` queda vacío para los registros históricos cuya hora se desconoce. Las migraciones de ventas no tienen downgrade automático para evitar pérdida de información al desagrupar transacciones.

La importación admite también ventas agrupadas con columnas `fecha;hora;id_venta;producto;cantidad` (separadas por punto y coma o coma), o en inglés `date,time,sale_id,product,quantity`. Cada fila representa un producto; las filas de una misma venta deben compartir ID, fecha y hora. La hora puede incluir desfase horario, por ejemplo `10:15-03:00`; sin desfase se interpreta en la zona de la sucursal y se rechazan horas ambiguas. Una venta se rechaza completa si alguna de sus filas es inválida. Los ID ya importados se rechazan para evitar duplicados. El formato anterior de tres columnas sigue funcionando, pero no permite detectar duplicados de forma fiable.
