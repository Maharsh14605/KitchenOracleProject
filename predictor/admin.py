# predictor/admin.py
from django.contrib import admin
from .models import (
    PizzaSales,
    Weather,
    Holiday,
    Ingredient,
    PizzaRecipe,
    RecipeItem,
    InventoryLevel,
)

# -----------------------
# Inline for PizzaRecipe
# -----------------------
class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1
    autocomplete_fields = ("ingredient",)
    fields = ("ingredient", "quantity")
    min_num = 0


@admin.register(PizzaRecipe)
class PizzaRecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "item_count")
    search_fields = ("name",)
    inlines = [RecipeItemInline]

    @admin.display(description="Ingredients")
    def item_count(self, obj):
        return obj.items.count()


# -----------------------
# Ingredient
# -----------------------
@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "unit_cost", "reorder_level")
    list_filter = ("unit",)
    search_fields = ("name",)
    ordering = ("name",)


# -----------------------
# InventoryLevel
# -----------------------
@admin.register(InventoryLevel)
class InventoryLevelAdmin(admin.ModelAdmin):
    list_display = ("date", "ingredient", "current_stock")
    list_filter = ("date", "ingredient")
    search_fields = ("ingredient__name",)
    date_hierarchy = "date"
    autocomplete_fields = ("ingredient",)
    ordering = ("-date", "ingredient__name")
    list_per_page = 50


# -----------------------
# PizzaSales
# -----------------------
@admin.register(PizzaSales)
class PizzaSalesAdmin(admin.ModelAdmin):
    list_display = (
        "order_details_id",
        "order_id",
        "order_date",
        "order_time",
        "pizza_name",
        "pizza_size",
        "quantity",
        "unit_price",
        "total_price",
    )
    list_filter = ("order_date", "pizza_size", "pizza_category")
    search_fields = (
        "order_details_id",
        "order_id",
        "pizza_id",
        "pizza_name",
        "pizza_category",
        "pizza_ingredients",
    )
    date_hierarchy = "order_date"
    ordering = ("-order_date", "-order_time")
    list_per_page = 50


# -----------------------
# Weather
# -----------------------
@admin.register(Weather)
class WeatherAdmin(admin.ModelAdmin):
    list_display = (
        "datetime",
        "tempmax",
        "tempmin",
        "temp",
        "precip",
        "snow",
        "windspeed",
        "sealevelpressure",
        "cloudcover",
        "visibility",
        "uvindex",
        "conditions",
        "icon",
    )
    list_filter = ("conditions", "icon")
    search_fields = ("conditions", "description", "icon")
    date_hierarchy = "datetime"
    ordering = ("-datetime",)
    list_per_page = 50


# -----------------------
# Holiday
# -----------------------
@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "holiday_name")
    search_fields = ("holiday_name",)
    date_hierarchy = "date"
    ordering = ("-date",)
