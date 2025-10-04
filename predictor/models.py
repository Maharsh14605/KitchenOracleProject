from django.db import models


from django.db import models

# predictor/models.py
from django.db import models

class PizzaSales(models.Model):
    order_details_id = models.IntegerField(primary_key=True)
    order_id = models.IntegerField()
    pizza_id = models.CharField(max_length=255)
    quantity = models.IntegerField()
    order_date = models.DateField()
    order_time = models.TimeField()
    unit_price = models.FloatField()
    total_price = models.FloatField()
    pizza_size = models.CharField(max_length=5)
    pizza_category = models.CharField(max_length=255)
    pizza_ingredients = models.TextField()
    pizza_name = models.CharField(max_length=255)

class Weather(models.Model):
    datetime = models.DateField(primary_key=True)
    tempmax = models.FloatField()
    tempmin = models.FloatField()
    temp = models.FloatField()
    precip = models.FloatField()
    snow = models.FloatField()
    windspeed = models.FloatField()
    sealevelpressure = models.FloatField()
    cloudcover = models.FloatField()
    visibility = models.FloatField()
    uvindex = models.FloatField(null=True, blank=True)
    conditions = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    icon = models.CharField(max_length=255)

class Holiday(models.Model):
    date = models.DateField(primary_key=True)
    holiday_name = models.CharField(max_length=255)

# ==== INVENTORY ====

class Ingredient(models.Model):
    UNIT_CHOICES = [
        ("lbs", "lbs"),
        ("balls", "balls"),
        ("cans", "cans"),
        ("units", "units"),
    ]
    name = models.CharField(max_length=200, unique=True)
    unit = models.CharField(max_length=16, choices=UNIT_CHOICES, default="units")
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # dollars
    reorder_level = models.FloatField(default=0)  # when <= this, flag low

    def __str__(self):
        return self.name


class PizzaRecipe(models.Model):
    """One pizza type, e.g. Pepperoni."""
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class RecipeItem(models.Model):
    """Ingredient usage for one pizza (per pizza ordered)."""
    recipe = models.ForeignKey(PizzaRecipe, on_delete=models.CASCADE, related_name="items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="recipe_items")
    quantity = models.FloatField()  # in ingredient.unit per pizza

    class Meta:
        unique_together = ("recipe", "ingredient")

    def __str__(self):
        return f"{self.recipe} – {self.ingredient} ({self.quantity})"


class InventoryLevel(models.Model):
    """Snapshot of stock for an ingredient on a date."""
    date = models.DateField(db_index=True)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="levels")
    current_stock = models.FloatField(default=0)

    class Meta:
        unique_together = ("date", "ingredient")

    def __str__(self):
        return f"{self.date} – {self.ingredient} = {self.current_stock}"
