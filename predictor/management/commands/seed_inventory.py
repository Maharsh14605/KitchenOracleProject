from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps
from django.utils import timezone
from datetime import date

Ingredient = apps.get_model("predictor", "Ingredient")
PizzaRecipe = apps.get_model("predictor", "PizzaRecipe")
RecipeItem = apps.get_model("predictor", "RecipeItem")
InventoryLevel = apps.get_model("predictor", "InventoryLevel")

INGREDIENTS = [
    ("Mozzarella Cheese",  "lbs",  4.50, 25),
    ("Pizza Dough",        "balls",1.25, 20),
    ("Pepperoni",          "lbs",  8.75, 15),
    ("Tomato Sauce",       "cans", 2.30, 6),
    ("Bell Peppers",       "lbs",  3.20, 10),
    ("Mushrooms",          "lbs",  4.80, 8),
    ("Italian Sausage",    "lbs",  6.90, 12),
    ("Onions",             "lbs",  1.80, 10),
    ("Black Olives",       "cans", 3.50, 8),
    ("Parmesan Cheese",    "lbs", 12.50, 8),
]

RECIPES = {
    "Margherita": [
        ("Pizza Dough", 1.0),
        ("Tomato Sauce", 0.25),
        ("Mozzarella Cheese", 0.35),
        ("Parmesan Cheese", 0.05),
    ],
    "Pepperoni": [
        ("Pizza Dough", 1.0),
        ("Tomato Sauce", 0.25),
        ("Mozzarella Cheese", 0.35),
        ("Pepperoni", 0.30),
    ],
    "Supreme": [
        ("Pizza Dough", 1.0),
        ("Tomato Sauce", 0.25),
        ("Mozzarella Cheese", 0.35),
        ("Pepperoni", 0.20),
        ("Italian Sausage", 0.20),
        ("Bell Peppers", 0.10),
        ("Mushrooms", 0.10),
        ("Onions", 0.10),
        ("Black Olives", 0.10),
    ],
}

def _field_exists(model, field_name: str) -> bool:
    return field_name in {f.name for f in model._meta.get_fields()}

class Command(BaseCommand):
    help = "Seed baseline ingredients, recipes, and a dated inventory snapshot (schema-tolerant)."

    @transaction.atomic
    def handle(self, *args, **opts):
        self.stdout.write(self.style.WARNING("Seeding inventory/recipes…"))

        # Detect Ingredient fields
        has_unit          = _field_exists(Ingredient, "unit")
        has_cost          = _field_exists(Ingredient, "cost")
        has_unit_cost     = _field_exists(Ingredient, "unit_cost")
        has_price         = _field_exists(Ingredient, "price")
        has_reorder_level = _field_exists(Ingredient, "reorder_level")
        has_reorder_thr   = _field_exists(Ingredient, "reorder_threshold")

        # Detect InventoryLevel stock field
        stock_field = "current_stock" if _field_exists(InventoryLevel, "current_stock") else (
                      "quantity"      if _field_exists(InventoryLevel, "quantity")      else None)
        if stock_field is None:
            raise RuntimeError("InventoryLevel must have 'current_stock' or 'quantity'.")

        # Choose snapshot date (today by default). Change if you want a historical baseline.
        snapshot_date: date = timezone.localdate()  # e.g., date(2015, 1, 1)

        # Ingredients + initial inventory snapshot
        for name, unit, cost_val, reorder_val in INGREDIENTS:
            defaults = {}
            if has_unit:
                defaults["unit"] = unit
            if has_cost:
                defaults["cost"] = cost_val
            elif has_unit_cost:
                defaults["unit_cost"] = cost_val
            elif has_price:
                defaults["price"] = cost_val
            if has_reorder_level:
                defaults["reorder_level"] = reorder_val
            elif has_reorder_thr:
                defaults["reorder_threshold"] = reorder_val

            ing, _ = Ingredient.objects.get_or_create(name=name, defaults=defaults)

            inv_defaults = {stock_field: 50.0}
            # IMPORTANT: include date to satisfy NOT NULL and unique constraints
            InventoryLevel.objects.get_or_create(
                ingredient=ing,
                date=snapshot_date,
                defaults=inv_defaults
            )

        # Recipes
        for recipe_name, items in RECIPES.items():
            recipe, _ = PizzaRecipe.objects.get_or_create(name=recipe_name)
            RecipeItem.objects.filter(recipe=recipe).delete()
            for ing_name, qty in items:
                ing = Ingredient.objects.get(name=ing_name)
                RecipeItem.objects.create(recipe=recipe, ingredient=ing, quantity=qty)

        self.stdout.write(self.style.SUCCESS(f"Seeded ingredients, recipes, and inventory snapshot for {snapshot_date}."))
