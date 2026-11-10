"""Import product recipes atomically per product."""

from collections import defaultdict
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.models import Ingredient, Recipe, RecipeIngredient
from app.schemas import IngredientIn, ProductIn, RecipeItem
from app.utils.product_files import read_product_file


def import_products(repo, filename: str, content: bytes):
    rows = read_product_file(filename, content)
    groups = defaultdict(list)
    errors = []
    for number, values, file_error in rows:
        try:
            product_name = ProductIn(name=values.get("producto")).name
            groups[product_name].append((number, values, file_error))
        except ValidationError:
            errors.append(
                {"row": number, "detail": "Nombre de producto vacío o inválido."}
            )
    imported_rows = 0
    imported_products = []
    for product_name, entries in groups.items():
        try:
            prepared = []
            seen = set()
            for number, values, file_error in entries:
                if file_error:
                    raise ValueError(f"Fila {number}: {file_error}")
                try:
                    stock = values.get("stock_minimo")
                    ingredient = IngredientIn(
                        name=values.get("ingrediente"),
                        unit=values.get("unidad"),
                        minimum_stock=0 if stock is None or stock == "" else stock,
                    )
                    quantity = RecipeItem(
                        ingredient_id=1, quantity_per_unit=values.get("cantidad")
                    ).quantity_per_unit
                except ValidationError:
                    raise ValueError(
                        f"Fila {number}: ingrediente, unidad, cantidad o stock mínimo inválidos."
                    )
                if ingredient.name in seen:
                    raise ValueError(
                        f"Fila {number}: el ingrediente {ingredient.name} está repetido en la receta."
                    )
                seen.add(ingredient.name)
                prepared.append((number, ingredient, quantity))
            with repo.db.begin_nested():
                product, _ = repo.get_or_create_product(product_name)
                # Serialize imports and edits that also lock this row.
                product = repo.get(type(product), product.id, lock=True)
                if not product.active:
                    raise ValueError("El producto está inactivo.")
                if repo.recipe_by_product(product.id):
                    raise ValueError("El producto ya tiene receta; no se reemplazó.")
                items = []
                for number, definition, quantity in sorted(
                    prepared, key=lambda item: item[1].name
                ):
                    ingredient, _ = repo.get_or_create_ingredient(
                        definition.name, definition.unit, definition.minimum_stock
                    )
                    if not ingredient.active:
                        raise ValueError(
                            f"Fila {number}: el ingrediente {definition.name} está inactivo."
                        )
                    if ingredient.unit != definition.unit:
                        raise ValueError(
                            f"Fila {number}: la unidad de {definition.name} no coincide con la registrada ({ingredient.unit})."
                        )
                    items.append(
                        RecipeIngredient(
                            ingredient_id=ingredient.id, quantity_per_unit=quantity
                        )
                    )
                recipe = Recipe(product_id=product.id, ingredients=items)
                repo.add(recipe)
            imported_rows += len(entries)
            imported_products.append({"id": product.id, "name": product.name})
        except ValueError as exc:
            for number, _, _ in entries:
                errors.append({"row": number, "detail": f"{product_name}: {exc}"})
        except IntegrityError:
            for number, _, _ in entries:
                errors.append(
                    {
                        "row": number,
                        "detail": f"{product_name}: conflicto con datos existentes; vuelve a intentar.",
                    }
                )
    repo.save()
    return {
        "total_rows": len(rows),
        "imported_rows": imported_rows,
        "rejected_rows": len(errors),
        "imported_products": imported_products,
        "errors": sorted(errors, key=lambda item: item["row"]),
    }
