# Documentación de la API

La documentación interactiva está en `http://localhost:8001/docs` cuando el backend está iniciado. El esquema OpenAPI está en `http://localhost:8001/openapi.json`. Consulta el README principal para instalar y ejecutar el proyecto.

## Autenticación

1. Ejecuta `POST /api/auth/login` con `email` y `password`.
2. Copia el `access_token` de la respuesta.
3. En Swagger, pulsa **Authorize** e introduce el token. En otras herramientas, envía `Authorization: Bearer <token>`.

El token identifica al usuario; el backend también comprueba su rol y si está activo. Cambiar la contraseña invalida los tokens anteriores. El login y `/api/health` son públicos.

Los roles son `ADMIN`, `PRODUCTION_MANAGER` e `INVENTORY_MANAGER`. Swagger indica los roles permitidos en cada operación.

## Grupos de endpoints

| Grupo | Operaciones principales |
|---|---|
| Authentication | Iniciar sesión, consultar el usuario actual y cambiar la contraseña. |
| Users | Crear, consultar, actualizar, activar y cambiar roles de usuarios. |
| Products | Gestionar productos e importar productos y recetas. |
| Ingredients | Gestionar ingredientes, unidades y stock mínimo. |
| Recipes | Consultar y gestionar recetas y cantidades. |
| Inventory | Consultar, establecer y ajustar stock; detectar stock bajo. |
| Sales | Registrar o importar ventas, consultar transacciones y anular ventas completas. |
| Dashboard | Consultar resumen y unidades vendidas por día. |
| Forecast | Consultar contexto, calendario mensual y estimación de demanda. |
| External Data | Consultar datos normalizados de clima y calendario. |
| System | Verificar conexión con la base de datos. |

## Ejemplo: registrar una venta

`POST /api/sale-transactions` requiere un token de administrador o jefe de producción. `sold_at` incluye zona horaria y cada producto debe existir y estar activo:

```json
{
  "sold_at": "2026-11-10T15:30:00-03:00",
  "source": "MANUAL",
  "items": [
    {"product_id": 1, "quantity": 2},
    {"product_id": 2, "quantity": 1}
  ]
}
```

La respuesta identifica la transacción y sus detalles. Para origen `EXTERNAL`, envía además un `external_id` único para ese origen. Una venta anulada se conserva, pero sus cantidades no se suman en el dashboard.

## Importación

Los endpoints de importación reciben `multipart/form-data` con el campo `file`; Swagger permite seleccionar el archivo. Se aceptan CSV UTF-8 y Excel `.xlsx`, hasta 5 MiB.

- Ventas: `fecha,producto,cantidad`. Opcionalmente agrega `hora` e `id_venta` juntos para agrupar productos por venta y detectar IDs ya importados. También se aceptan encabezados equivalentes en inglés. Los archivos sin ID pueden duplicarse al importarlos nuevamente.
- Productos y recetas: `producto,ingrediente,cantidad,unidad` y `stock_minimo` opcional. Si el producto ya tiene receta, no se reemplaza.

Las respuestas incluyen filas importadas, rechazadas y errores. Solo un administrador puede crear productos nuevos durante una importación de ventas o importar productos y recetas.

## Respuestas y fechas

Las fechas usan `AAAA-MM-DD`; las transacciones con hora usan ISO 8601 con zona horaria. Las cantidades de ingredientes se expresan en la unidad registrada. Los errores de negocio suelen devolverse como `{"detail": "..."}`; los errores de validación 422 pueden contener una lista de detalles.

Los códigos principales son 200/201 para operaciones correctas, 204 para respuestas sin contenido, 400 para reglas de negocio, 401 para autenticación, 403 para permisos, 404 para recursos inexistentes, 409 para conflictos, 422 para validación o datos insuficientes y 503 cuando falla una dependencia. Cada operación documenta los códigos que le corresponden.

La operación de demanda usa el modelo Ridge implementado en el backend y requiere historial suficiente. Su respuesta indica las fuentes y si los datos usados son sintéticos; una respuesta exitosa no representa una garantía de precisión ni una orden de producción.
