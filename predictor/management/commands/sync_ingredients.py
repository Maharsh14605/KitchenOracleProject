# predictor/management/commands/sync_ingredients.py
from __future__ import annotations

import re
from typing import Iterable, Set, Dict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from predictor.models import PizzaSales, Ingredient


SEP_RE = re.compile(r"[+,\n]")  # split on +, comma, or newlines


def tokenize(ingredients_field: str) -> Iterable[str]:
    """
    Split a pizza_ingredients string into individual tokens.
    Example: "Mozzarella Cheese, Tomato Sauce + Pepperoni" -> ["Mozzarella Cheese", "Tomato Sauce", "Pepperoni"]
    """
    if not ingredients_field:
        return []
    for raw in SEP_RE.split(str(ingredients_field)):
        tok = raw.strip()
        if tok:
            yield tok


def title_case_safe(s: str) -> str:
    """Simple title-case that preserves acronyms reasonably well."""
    return " ".join(w.capitalize() if w.islower() else w for w in s.split())


class Command(BaseCommand):
    help = "Scan PizzaSales.pizza_ingredients and create any missing Ingredients with default fields."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without writing to the database.",
        )
        parser.add_argument(
            "--unit",
            default="units",
            help="Default unit for new ingredients (default: units). Choices: lbs, balls, cans, units",
        )
        parser.add_argument(
            "--unit-cost",
            type=float,
            default=0.0,
            help="Default unit_cost for new ingredients (default: 0.0)",
        )
        parser.add_argument(
            "--reorder-level",
            type=float,
            default=10.0,
            help="Default reorder_level for new ingredients (default: 10.0)",
        )
        parser.add_argument(
            "--min-frequency",
            type=int,
            default=1,
            help="Only create ingredients that appear at least this many times across sales (default: 1).",
        )

    def handle(self, *args, **opts):
        dry_run: bool = opts["dry_run"]
        default_unit: str = opts["unit"]
        default_cost: float = opts["unit_cost"]
        default_reorder: float = opts["reorder_level"]
        min_freq: int = opts["min_frequency"]

        self.stdout.write(self.style.WARNING("Scanning pizza_ingredients to sync missing Ingredients…"))

        # 1) Gather all tokens with rough frequency (weighted by qty to prioritize impactful items)
        freq: Dict[str, float] = {}
        qs = (
            PizzaSales.objects
            .values("pizza_ingredients")
            .annotate(qty=Sum("quantity"))
        )

        for row in qs:
            qty = float(row.get("qty") or 0.0)
            for tok in tokenize(row.get("pizza_ingredients") or ""):
                key = tok.strip()
                if not key:
                    continue
                freq[key] = freq.get(key, 0.0) + max(qty, 1.0)  # count at least 1 per occurrence

        if not freq:
            self.stdout.write(self.style.ERROR("No pizza_ingredients found in PizzaSales. Nothing to do."))
            return

        # 2) Build case-insensitive lookup of existing Ingredient names
        existing_lc: Set[str] = {ing.name.strip().lower() for ing in Ingredient.objects.all()}

        # 3) Decide which tokens are missing & meet frequency threshold
        missing = []
        for token, f in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])):
            if f < min_freq:
                continue
            if token.strip().lower() not in existing_lc:
                missing.append((token, f))

        if not missing:
            self.stdout.write(self.style.SUCCESS("All tokens already exist as Ingredients. Nothing to create."))
            return

        self.stdout.write(f"Found {len(missing)} missing ingredients (min_frequency={min_freq}).")

        # Preview what will be created
        preview = "\n".join(
            f"  • {token}  (freq≈{int(f)}) → name='{title_case_safe(token)}', unit='{default_unit}', unit_cost={default_cost}, reorder_level={default_reorder}"
            for token, f in missing[:25]
        )
        if preview:
            self.stdout.write("Examples (up to 25):\n" + preview)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run mode enabled. No changes were made."))
            return

        # 4) Create the new Ingredients
        created_count = 0
        with transaction.atomic():
            for token, _ in missing:
                name = title_case_safe(token)
                # Recheck to avoid race/duplicates (case-insensitive)
                if Ingredient.objects.filter(name__iexact=name).exists():
                    continue
                Ingredient.objects.create(
                    name=name,
                    unit=default_unit,
                    unit_cost=default_cost,
                    reorder_level=default_reorder,
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_count} new Ingredient(s)."))
        self.stdout.write(self.style.SUCCESS("Sync complete."))
