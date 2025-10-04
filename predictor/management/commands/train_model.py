import os
import pandas as pd
import numpy as np
import joblib
from django.core.management.base import BaseCommand
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class Command(BaseCommand):
    help = "Trains and saves the sales prediction model (no leakage features)."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting model training...")

        # Locate processed CSV
        base_dir = os.path.dirname(os.path.abspath(__file__))
        processed_data_path = os.path.join(base_dir, "..", "..", "..", "processed_sales_data.csv")

        try:
            df = pd.read_csv(processed_data_path)
            self.stdout.write(self.style.SUCCESS("Processed data loaded successfully."))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"processed_sales_data.csv not found at {processed_data_path}"))
            self.stdout.write("Run `python manage.py process_data` first.")
            return

        # --- Normalize column names we rely on ---
        # Expect a date column and total_sales
        date_col = 'date' if 'date' in df.columns else ('order_date' if 'order_date' in df.columns else None)
        if not date_col or 'total_sales' not in df.columns:
            self.stdout.write(self.style.ERROR("CSV must include a date/order_date and total_sales columns."))
            return

        df[date_col] = pd.to_datetime(df[date_col]).dt.date

        # Fill holiday gap
        if 'days_until_holiday' in df.columns:
            df['days_until_holiday'] = df['days_until_holiday'].fillna(365)
        else:
            df['days_until_holiday'] = 365

        # Derive weekday if not there
        if 'day_of_week' not in df.columns:
            df['day_of_week'] = pd.to_datetime(df[date_col]).dt.day_name()

        # Weekend flag & holiday flag if not present
        if 'is_weekend' not in df.columns:
            df['is_weekend'] = pd.to_datetime(df[date_col]).dt.weekday >= 5
        df['is_weekend'] = df['is_weekend'].astype(int)

        if 'is_holiday' not in df.columns:
            df['is_holiday'] = 0

        # ---- History-based features (no leakage) ----
        # Sort by date
        df = df.sort_values(by=date_col)

        # Rolling means up to D-1
        df['hist_7d_avg']  = (df['total_sales']
                              .shift(1)
                              .rolling(window=7, min_periods=3)
                              .mean())
        df['hist_28d_avg'] = (df['total_sales']
                              .shift(1)
                              .rolling(window=28, min_periods=7)
                              .mean())

        # Same-weekday mean computed only from past (expanding)
        # Build weekday cumulative mean up to previous occurrence
        df['weekday_idx'] = pd.to_datetime(df[date_col]).dt.weekday  # 0=Mon
        df['dow_mean'] = (df.groupby('weekday_idx')['total_sales']
                            .apply(lambda s: s.shift(1).expanding(min_periods=3).mean())
                            .reset_index(level=0, drop=True))

        # One-hot for day_of_week
        df = pd.get_dummies(df, columns=['day_of_week'], drop_first=True, dtype=int)

        # Weather columns (make sure these exist; fill if missing)
        weather_cols = [
            'tempmax','tempmin','temp','precip','snow',
            'windspeed','sealevelpressure','cloudcover','visibility','uvindex'
        ]
        for c in weather_cols:
            if c not in df.columns:
                df[c] = np.nan
        df[weather_cols] = df[weather_cols].astype(float).fillna(df[weather_cols].median(numeric_only=True))

        # Final feature list (NO total_orders/total_quantity)
        feature_columns = [
            'tempmax','tempmin','temp','precip','snow',
            'windspeed','sealevelpressure','cloudcover','visibility','uvindex',
            'is_weekend','is_holiday','days_until_holiday',
            'hist_7d_avg','hist_28d_avg','dow_mean',
            'day_of_week_Monday','day_of_week_Saturday','day_of_week_Sunday',
            'day_of_week_Thursday','day_of_week_Tuesday','day_of_week_Wednesday'
        ]
        # Create any missing one-hot columns
        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0

        # Drop rows without minimal history
        df = df.dropna(subset=['hist_7d_avg','hist_28d_avg','dow_mean'])

        X = df[feature_columns]
        y = df['total_sales'].astype(float)

        self.stdout.write("Splitting data (time-independent split is OK here, but avoid leakage via history features).")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.stdout.write("Training XGBRegressor (tuned defaults)...")
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

        preds = model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        self.stdout.write(self.style.SUCCESS(f"RMSE: {rmse:.2f}"))

        # Save both model and the feature list (so views can load the same)
        out_path = os.path.join(os.getcwd(), 'sales_predictor_model.joblib')
        joblib.dump({"model": model, "feature_columns": feature_columns}, out_path)
        self.stdout.write(self.style.SUCCESS(f"Saved model to {out_path}"))
