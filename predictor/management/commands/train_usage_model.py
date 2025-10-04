# predictor/management/commands/train_usage_model.py
import os
import numpy as np
import pandas as pd
import joblib

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Sum

from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

from predictor.models import (
    PizzaSales, Ingredient, Holiday, Weather
)

class Command(BaseCommand):
    help = "Trains per-ingredient usage models by parsing PizzaSales.pizza_ingredients (no recipes, no history)."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting per-ingredient model training from pizza_ingredients…")

        # 1) Load minimal sales fields
        qs = (PizzaSales.objects
              .values("order_date", "pizza_ingredients")
              .annotate(qty=Sum("quantity"))
              .order_by("order_date"))
        if not qs:
            self.stdout.write(self.style.ERROR("No PizzaSales found; cannot train."))
            return
        df_sales = pd.DataFrame(list(qs))
        df_sales["order_date"] = pd.to_datetime(df_sales["order_date"]).dt.date

        # Ingredient lookup (case-insensitive)
        ing_qs = list(Ingredient.objects.all().values("id", "name"))
        if not ing_qs:
            self.stdout.write(self.style.ERROR("No Ingredient rows found; seed ingredients first."))
            return
        ing_by_lc = {row["name"].strip().lower(): row["id"] for row in ing_qs}
        ing_name_by_id = {row["id"]: row["name"] for row in ing_qs}

        # 2) Build daily usage by parsing pizza_ingredients
        #    Assumption: pizza_ingredients is a comma-separated list like "Mozzarella Cheese, Tomato Sauce, Pepperoni"
        #    We count 1 unit per listed ingredient per pizza, multiplied by the sales quantity.
        usage_rows = []
        unmatched_tokens = set()

        for _, r in df_sales.iterrows():
            qty = float(r["qty"] or 0.0)
            tokens = []
            raw = str(r["pizza_ingredients"] or "")
            # support commas or plus signs; keep it simple
            for part in raw.replace("+", ",").split(","):
                t = part.strip().lower()
                if t:
                    tokens.append(t)
            for tok in tokens:
                ing_id = ing_by_lc.get(tok)
                if ing_id is None:
                    unmatched_tokens.add(tok)
                    continue
                usage_rows.append({
                    "date": r["order_date"],
                    "ingredient_id": ing_id,
                    "usage": qty,  # 1 "unit" per ingredient per pizza × qty
                })

        if unmatched_tokens:
            self.stdout.write(self.style.WARNING(
                f"{len(unmatched_tokens)} ingredient tokens in sales did not match Ingredient.name (showing up to 15): "
                + ", ".join(list(unmatched_tokens)[:15])
            ))

        if not usage_rows:
            self.stdout.write(self.style.ERROR("No ingredient usage could be derived from pizza_ingredients."))
            return

        df = pd.DataFrame(usage_rows)
        df = df.groupby(["date", "ingredient_id"], as_index=False)["usage"].sum()

        # 3) Join simple features: weather + holiday + weekday one-hots
        w = Weather.objects.all().values(
            "datetime","tempmax","tempmin","temp","precip","snow",
            "windspeed","sealevelpressure","cloudcover","visibility","uvindex"
        )
        dfw = pd.DataFrame(list(w))
        if not dfw.empty:
            dfw = dfw.rename(columns={"datetime": "date"})
            dfw["date"] = pd.to_datetime(dfw["date"]).dt.date
            df = df.merge(dfw, on="date", how="left")

        holidays = set(Holiday.objects.values_list("date", flat=True))
        dts = pd.to_datetime(df["date"])
        df["is_holiday"] = df["date"].isin(holidays).astype(int)
        df["is_weekend"] = (dts.dt.weekday >= 5).astype(int)
        df["day_of_week"] = dts.dt.day_name()

        dummies = pd.get_dummies(df["day_of_week"], prefix="day_of_week", drop_first=True, dtype=int)
        wanted_wd = [
            "day_of_week_Monday","day_of_week_Saturday","day_of_week_Sunday",
            "day_of_week_Thursday","day_of_week_Tuesday","day_of_week_Wednesday"
        ]
        for c in wanted_wd:
            if c not in dummies.columns:
                dummies[c] = 0
        dummies = dummies[wanted_wd]
        df = pd.concat([df, dummies], axis=1)

        # Weather columns & fill (median)
        weather_cols = [
            "tempmax","tempmin","temp","precip","snow",
            "windspeed","sealevelpressure","cloudcover","visibility","uvindex"
        ]
        for c in weather_cols:
            if c not in df.columns:
                df[c] = np.nan
        df[weather_cols] = df[weather_cols].astype(float)
        df[weather_cols] = df[weather_cols].fillna(df[weather_cols].median(numeric_only=True))

        # Final features (NO history)
        feature_columns = weather_cols + [
            "is_weekend","is_holiday",
            "day_of_week_Monday","day_of_week_Saturday","day_of_week_Sunday",
            "day_of_week_Thursday","day_of_week_Tuesday","day_of_week_Wednesday",
        ]

        # 4) Train one simple model per ingredient (random split, like your train_model.py)
        models = {}
        metrics = {}
        for ing_id, g in df.groupby("ingredient_id"):
            if len(g) < 30:
                # keep it practical; skip tiny series
                continue

            X = g[feature_columns].astype(float)
            y = g["usage"].astype(float)

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            model = XGBRegressor(
                n_estimators=800,
                learning_rate=0.05,
                max_depth=5,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_lambda=1.0,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)

            preds = model.predict(X_test) if len(X_test) else np.array([])
            rmse = float(np.sqrt(mean_squared_error(y_test, preds))) if len(preds) else float("nan")

            models[ing_id] = model
            metrics[ing_name_by_id[ing_id]] = {"rmse": rmse, "n_test": int(len(X_test))}

        if not models:
            self.stdout.write(self.style.ERROR("No ingredient had enough rows to train."))
            return

        out_path = os.path.join(settings.BASE_DIR, "ingredient_usage_model.joblib")
        joblib.dump({"models": models, "feature_columns": feature_columns}, out_path)
        self.stdout.write(self.style.SUCCESS(
            f"Saved usage models to {out_path} ({len(models)} ingredients)."
        ))
