"""Contenido de la documentación OpenAPI; no modifica el comportamiento de la API."""

from typing import Any

TAG_DESCRIPTIONS = [
    {
        "name": "Authentication",
        "description": "Inicio de sesión y gestión de la contraseña propia.",
    },
    {
        "name": "Users",
        "description": "Administración de usuarios y roles; acceso exclusivo de administrador.",
    },
    {
        "name": "Products",
        "description": "Catálogo de productos y carga de productos con recetas.",
    },
    {
        "name": "Ingredients",
        "description": "Ingredientes, unidades y niveles mínimos de inventario.",
    },
    {
        "name": "Recipes",
        "description": "Recetas por producto y cantidades de sus ingredientes.",
    },
    {
        "name": "Inventory",
        "description": "Consulta, establecimiento y ajuste del stock de ingredientes.",
    },
    {
        "name": "Sales",
        "description": "Ventas por producto, transacciones, importación y exportación.",
    },
    {
        "name": "Dashboard",
        "description": "Resumen y serie diaria de unidades vendidas.",
    },
    {
        "name": "Forecast",
        "description": "Contexto meteorológico, calendario y estimación de demanda.",
    },
    {"name": "Recommendations", "description": "Pronósticos revisados y guardados como recomendaciones."},
    {
        "name": "External Data",
        "description": "Datos normalizados de clima y calendario de Chile.",
    },
]

# Method/path -> summary, description, roles, extra HTTP error codes.
ALL = "ADMIN, PRODUCTION_MANAGER e INVENTORY_MANAGER"
ADMIN = "ADMIN"
MANAGERS = "ADMIN y PRODUCTION_MANAGER"
INVENTORY = "ADMIN e INVENTORY_MANAGER"
DOCS: dict[tuple[str, str], tuple[str, str, str | None, tuple[int, ...]]] = {
    ("get", "/api/health"): (
        "Comprobar estado", "Verifica el estado de la aplicación.", None, (503,)
    ),
    ("post", "/api/inventory/stock/bulk"): (
        "Actualizar stock de ingredientes", "Actualiza los ingredientes indicados en una transacción y rechaza cambios concurrentes.", INVENTORY, (400, 404, 409, 422)
    ),
    ("post", "/api/products/stock/bulk"): (
        "Actualizar stock de productos", "Actualiza todos los productos indicados en una transacción y rechaza cambios concurrentes.", ALL, (400, 404, 409, 422)
    ),
    ("put", "/api/products/{product_id}/stock"): (
        "Actualizar stock de producto", "Establece las unidades disponibles de un producto activo.", ALL, (400, 404, 422)
    ),
    ("get", "/api/recommendations/{recommendation_id}/ingredients"): (
        "Calcular ingredientes de una recomendación", "Calcula ingredientes y faltantes para una recomendación guardada usando el stock actual.", ALL, (404,)
    ),
    ("get", "/api/recommendations/ingredients"): (
        "Calcular ingredientes", "Calcula ingredientes y stock para la última recomendación de cada día del rango.", ALL, (400,)
    ),
    ("put", "/api/recommendations/{recommendation_id}"): (
        "Editar recomendación", "Permite al administrador y al jefe de producción cambiar cantidades y registrar el motivo.", MANAGERS, (400, 404, 422)
    ),
    ("get", "/api/recommendations"): (
        "Listar recomendaciones", "Devuelve los pronósticos revisados guardados y sus ajustes.", ALL, ()
    ),
    ("post", "/api/recommendations"): (
        "Guardar recomendación", "Guarda el pronóstico revisado con cantidades finales y motivos de ajuste.", MANAGERS, (400, 422)
    ),
    ("post", "/api/auth/login"): (
        "Iniciar sesión",
        "Autentica un correo y contraseña y devuelve un token Bearer y el usuario. Un usuario inactivo no puede iniciar sesión.",
        None,
        (401,),
    ),
    ("get", "/api/auth/me"): (
        "Consultar mi usuario",
        "Devuelve los datos del usuario autenticado, sin contraseña.",
        ALL,
        (),
    ),
    ("post", "/api/auth/change-password"): (
        "Cambiar mi contraseña",
        "Comprueba la contraseña actual y guarda la nueva. El cambio invalida los tokens anteriores; vuelve a iniciar sesión.",
        ALL,
        (400,),
    ),
    ("get", "/api/users"): (
        "Listar usuarios",
        "Devuelve los usuarios registrados, incluidos los inactivos.",
        ADMIN,
        (),
    ),
    ("get", "/api/users/{user_id}"): (
        "Consultar usuario",
        "Busca un usuario por su identificador.",
        ADMIN,
        (404,),
    ),
    ("post", "/api/users"): (
        "Crear usuario",
        "Crea un usuario con nombre, correo, contraseña y uno de los tres roles. El correo debe ser único.",
        ADMIN,
        (409,),
    ),
    ("post", "/api/users/generated"): (
        "Crear usuario con contraseña generada",
        "Genera una contraseña inicial y la devuelve en la respuesta de creación. Solo se almacena su hash; la respuesta usa Cache-Control: no-store.",
        ADMIN,
        (409,),
    ),
    ("put", "/api/users/{user_id}"): (
        "Actualizar usuario",
        "Actualiza nombre y correo; puede incluir una contraseña nueva.",
        ADMIN,
        (404, 409),
    ),
    ("patch", "/api/users/{user_id}/role"): (
        "Cambiar rol",
        "Asigna ADMIN, PRODUCTION_MANAGER o INVENTORY_MANAGER.",
        ADMIN,
        (404,),
    ),
    ("patch", "/api/users/{user_id}/status"): (
        "Activar o desactivar usuario",
        "Cambia el estado activo sin eliminar físicamente el usuario.",
        ADMIN,
        (404,),
    ),
    ("get", "/api/products"): (
        "Listar productos",
        "Devuelve el catálogo. Usa `active=true` o `active=false` para filtrar por estado.",
        ALL,
        (),
    ),
    ("get", "/api/products/{product_id}"): (
        "Consultar producto",
        "Busca un producto por su identificador.",
        ALL,
        (404,),
    ),
    ("post", "/api/products"): (
        "Crear producto",
        "Registra un producto con nombre único y código externo opcional único.",
        ADMIN,
        (409,),
    ),
    ("put", "/api/products/{product_id}"): (
        "Actualizar producto",
        "Actualiza los datos del producto indicado.",
        ADMIN,
        (404, 409),
    ),
    ("patch", "/api/products/{product_id}/status"): (
        "Activar o desactivar producto",
        "Cambia el estado sin borrar el producto ni su historial.",
        ADMIN,
        (404,),
    ),
    ("post", "/api/products/import"): (
        "Importar productos y recetas",
        "Recibe un archivo CSV UTF-8 o Excel .xlsx de hasta 5 MiB. Columnas: `producto`, `ingrediente`, `cantidad`, `unidad` y `stock_minimo` opcional. Se valida cada producto como grupo; una receta existente no se reemplaza.",
        ADMIN,
        (400,),
    ),
    ("get", "/api/ingredients"): (
        "Listar ingredientes",
        "Devuelve los ingredientes registrados con unidad y stock mínimo.",
        ALL,
        (),
    ),
    ("get", "/api/ingredients/{ingredient_id}"): (
        "Consultar ingrediente",
        "Busca un ingrediente por su identificador.",
        ALL,
        (404,),
    ),
    ("post", "/api/ingredients"): (
        "Crear ingrediente",
        "Crea un ingrediente y su registro de inventario con stock inicial cero. Unidades: g, kg, ml, l o unidad.",
        INVENTORY,
        (409,),
    ),
    ("put", "/api/ingredients/{ingredient_id}"): (
        "Actualizar ingrediente",
        "Actualiza nombre, unidad, stock mínimo y estado del ingrediente.",
        INVENTORY,
        (404, 409),
    ),
    ("patch", "/api/ingredients/{ingredient_id}/status"): (
        "Activar o desactivar ingrediente",
        "Cambia el estado sin eliminar el ingrediente.",
        INVENTORY,
        (404,),
    ),
    ("get", "/api/recipes"): (
        "Listar recetas",
        "Devuelve las recetas y sus ingredientes por producto.",
        ALL,
        (),
    ),
    ("get", "/api/recipes/{recipe_id}"): (
        "Consultar receta",
        "Busca una receta por su identificador.",
        ALL,
        (404,),
    ),
    ("get", "/api/products/{product_id}/recipe"): (
        "Consultar receta por producto",
        "Devuelve la receta asociada al producto.",
        ALL,
        (404,),
    ),
    ("post", "/api/recipes"): (
        "Crear receta",
        "Asocia una receta a un producto. Las cantidades deben ser positivas y no se permiten ingredientes repetidos ni una segunda receta para el producto.",
        ADMIN,
        (404, 409),
    ),
    ("put", "/api/recipes/{recipe_id}"): (
        "Reemplazar receta",
        "Actualiza el producto y reemplaza la lista completa de ingredientes.",
        ADMIN,
        (404, 409),
    ),
    ("patch", "/api/recipes/{recipe_id}/ingredients/{ingredient_id}"): (
        "Cambiar cantidad de ingrediente",
        "Actualiza la cantidad por unidad de un ingrediente ya incluido en la receta.",
        MANAGERS,
        (404,),
    ),
    ("get", "/api/inventory"): (
        "Listar inventario",
        "Devuelve el stock actual de los ingredientes.",
        ALL,
        (),
    ),
    ("get", "/api/inventory/low-stock"): (
        "Consultar stock bajo",
        "Devuelve los ingredientes cuyo stock actual es menor o igual que su mínimo.",
        ALL,
        (),
    ),
    ("get", "/api/inventory/{ingredient_id}"): (
        "Consultar stock de ingrediente",
        "Busca el registro de inventario por identificador de ingrediente.",
        ALL,
        (404,),
    ),
    ("put", "/api/inventory/{ingredient_id}"): (
        "Establecer stock",
        "Reemplaza el stock actual. La cantidad no puede ser negativa.",
        INVENTORY,
        (404,),
    ),
    ("post", "/api/inventory/{ingredient_id}/adjust"): (
        "Ajustar stock",
        "Suma un valor positivo o negativo al stock actual; rechaza un resultado menor que cero.",
        INVENTORY,
        (400, 404),
    ),
    ("get", "/api/sales"): (
        "Listar detalles de ventas",
        "Devuelve las líneas de ventas completadas. Se pueden combinar los filtros de producto, fecha inicial y fecha final.",
        MANAGERS,
        (400,),
    ),
    ("get", "/api/sales/{sale_id}"): (
        "Consultar detalle de venta",
        "Busca una línea de venta por su identificador.",
        MANAGERS,
        (404,),
    ),
    ("post", "/api/sales"): (
        "Registrar venta por producto",
        "Registra una línea de producto y fecha. Para ventas con varios productos y fecha y hora usa `/api/sale-transactions`.",
        MANAGERS,
        (400, 404),
    ),
    ("post", "/api/sales/import"): (
        "Importar ventas",
        "Carga CSV UTF-8 o Excel .xlsx, máximo 5 MiB. Acepta `fecha,producto,cantidad` y opcionalmente `hora,id_venta` juntos. Con ID, las filas se agrupan y los ID ya importados se rechazan. Los archivos sin ID pueden duplicarse al reimportarlos. Solo ADMIN puede crear productos nuevos durante la importación.",
        MANAGERS,
        (400,),
    ),
    ("get", "/api/sales/export"): (
        "Exportar ventas a CSV",
        "Descarga las líneas de ventas completadas en CSV UTF-8, con filtros opcionales de producto y fecha.",
        MANAGERS,
        (400,),
    ),
    ("get", "/api/sale-transactions"): (
        "Listar transacciones",
        "Devuelve transacciones y sus productos, incluidas las anuladas. El filtro de producto devuelve la transacción completa.",
        MANAGERS,
        (400,),
    ),
    ("get", "/api/sale-transactions/{ident}"): (
        "Consultar transacción",
        "Devuelve una transacción y sus detalles.",
        MANAGERS,
        (404,),
    ),
    ("post", "/api/sale-transactions"): (
        "Registrar transacción",
        "Registra uno o más productos activos. `sold_at` requiere zona horaria. Para origen EXTERNAL se exige un ID externo único; MANUAL no admite ID externo.",
        MANAGERS,
        (400, 404, 409),
    ),
    ("patch", "/api/sale-transactions/{ident}/cancel"): (
        "Anular transacción",
        "Anula la transacción completa y registra el usuario y la fecha. Los registros LEGACY no se anulan como transacciones.",
        MANAGERS,
        (404, 409),
    ),
    ("get", "/api/dashboard"): (
        "Consultar resumen",
        "Devuelve conteos y unidades vendidas hoy y en los últimos siete días, excluyendo transacciones anuladas.",
        ALL,
        (),
    ),
    ("get", "/api/dashboard/sales-trend"): (
        "Consultar ventas diarias",
        "Devuelve unidades por fecha, incluyendo días sin registros. `days` admite 7 o 30 y el período incluye hoy.",
        ALL,
        (),
    ),
    ("get", "/api/forecast/context"): (
        "Consultar contexto por fecha",
        "Consulta clima y calendario para una fecha desde hoy hasta 15 días posteriores. Cada proveedor informa su estado de forma independiente.",
        MANAGERS,
        (400,),
    ),
    ("get", "/api/forecast/demand"): (
        "Estimar demanda diaria",
        "Calcula una estimación mediante regresión lineal Ridge a partir de ventas y clima históricos. Exige al menos 30 días de clima histórico y 30 días con ventas por producto; informa las fuentes y si se usaron datos sintéticos. La fecha debe estar entre hoy y 15 días posteriores.",
        MANAGERS,
        (400, 404, 422, 503),
    ),
    ("get", "/api/calendar/month"): (
        "Consultar calendario mensual",
        "Devuelve feriados y conmemoraciones de Chile por mes. `region` selecciona la región para eventos regionales; por defecto CL-RM.",
        MANAGERS,
        (),
    ),
    ("get", "/api/external/weather"): (
        "Consultar clima normalizado",
        "Devuelve temperatura media diaria en °C y precipitación en mm. Si se indica ubicación, latitude y longitude deben enviarse juntos. La API real admite fechas dentro de los últimos 92 días y los próximos 15 días, sujeto a disponibilidad.",
        ALL,
        (503,),
    ),
    ("get", "/api/external/calendar"): (
        "Consultar calendario por fecha",
        "Devuelve día de semana (lunes=0), fin de semana, feriado y festividad para Chile.",
        ALL,
        (503,),
    ),
    ("get", "/api/external/context"): (
        "Consultar clima y calendario",
        "Consulta ambos servicios concurrentemente. Si alguno falla, se devuelve un error controlado.",
        ALL,
        (503,),
    ),
}

EXAMPLES = {
    ("post", "/api/auth/login"): {
        "email": "usuario@example.cl",
        "password": "contraseña-de-ejemplo",
    },
    ("post", "/api/users/generated"): {
        "name": "Ana Pérez",
        "email": "ana@example.cl",
        "role": "INVENTORY_MANAGER",
    },
    ("post", "/api/products"): {
        "name": "Cheesecake",
        "description": "Porción individual",
        "external_code": "PAST-001",
        "active": True,
    },
    ("post", "/api/ingredients"): {
        "name": "Harina",
        "unit": "g",
        "minimum_stock": 1000,
        "active": True,
    },
    ("post", "/api/recipes"): {
        "product_id": 1,
        "ingredients": [
            {"ingredient_id": 1, "quantity_per_unit": 150},
            {"ingredient_id": 2, "quantity_per_unit": 20},
        ],
    },
    ("put", "/api/inventory/{ingredient_id}"): {"current_stock": 2500},
    ("post", "/api/inventory/{ingredient_id}/adjust"): {"quantity": -500},
    ("post", "/api/sales"): {"product_id": 1, "quantity": 5, "sale_date": "2026-11-10"},
    ("post", "/api/sale-transactions"): {
        "sold_at": "2026-11-10T15:30:00-03:00",
        "source": "MANUAL",
        "items": [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 1}],
    },
}

ERRORS = {
    400: ("Solicitud rechazada por una regla de negocio.", None),
    401: (
        "Credenciales ausentes, inválidas o vencidas.",
        "Invalid or expired credentials",
    ),
    403: ("El rol no tiene permiso para esta operación.", "Insufficient permissions"),
    404: ("No se encontró el recurso solicitado.", None),
    409: (
        "Conflicto con un recurso o restricción existente.",
        "A record conflicts with an existing record or database constraint",
    ),
    422: (
        "Los parámetros o el cuerpo no cumplen la validación; algunas operaciones también informan datos insuficientes.",
        None,
    ),
    503: ("La base de datos o un proveedor externo no está disponible.", None),
}
PARAMETERS = {
    "user_id": "Identificador del usuario.",
    "product_id": "Identificador del producto.",
    "ingredient_id": "Identificador del ingrediente.",
    "recipe_id": "Identificador de la receta.",
    "sale_id": "Identificador del detalle de venta.",
    "ident": "Identificador de la transacción.",
    "active": "Filtra por estado activo o inactivo.",
    "start_date": "Fecha inicial inclusiva, en formato AAAA-MM-DD.",
    "end_date": "Fecha final inclusiva, en formato AAAA-MM-DD.",
    "day": "Fecha solicitada en formato AAAA-MM-DD.",
    "days": "Cantidad de días, incluidos hoy: 7 o 30.",
    "year": "Año del calendario (2000 a 2100).",
    "month": "Mes del calendario (1 a 12).",
    "region": "Código regional de Chile, por ejemplo CL-RM o CL-VS.",
    "latitude": "Latitud de consulta; requiere longitude.",
    "longitude": "Longitud de consulta; requiere latitude.",
    "time_zone": "Zona horaria para la ubicación consultada.",
}


def enrich_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Añade documentación sin alterar rutas, validaciones ni control de acceso."""
    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            key = (method, path)
            if key not in DOCS:
                continue
            summary, description, roles, errors = DOCS[key]
            operation["summary"] = summary
            operation["description"] = description + (
                f"\n\n**Roles permitidos:** {roles}."
                if roles
                else "\n\n**Acceso:** público."
            )
            for parameter in operation.get("parameters", []):
                if parameter.get("name") in PARAMETERS:
                    parameter.setdefault("description", PARAMETERS[parameter["name"]])
            content = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("application/json")
            )
            if content is not None and key in EXAMPLES:
                content["example"] = EXAMPLES[key]
            codes = set(errors)
            if roles:
                codes.add(401)
                if roles != ALL:
                    codes.add(403)
            for code in codes:
                if str(code) in operation["responses"]:
                    continue
                label, example = ERRORS[code]
                if key == ("post", "/api/auth/login") and code == 401:
                    example = "Invalid credentials"
                response: dict[str, Any] = {"description": label}
                if example is not None:
                    response["content"] = {
                        "application/json": {"example": {"detail": example}}
                    }
                operation["responses"][str(code)] = response
    return schema
