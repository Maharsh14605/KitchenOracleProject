import os
from datetime import datetime, date as Date, timedelta

import numpy as np
import pandas as pd

from django.db.models import Count, Sum, Avg
from django.utils.dateparse import parse_date

from rest_framework.views import APIView
from rest_framework.response import Response

import joblib

from .models import PizzaSales, Weather, Holiday
from .services.open_meteo import fetch_and_store

from .models import Ingredient, InventoryLevel

# ---------------------------
# Sales Model loader (singleton)
# ---------------------------
model = None
feature_columns = None

def load_model():
    """Load trained SALES model and its feature list."""
    global model, feature_columns
    if model is not None:
        return
    try:
        model_path = os.path.join(os.getcwd(), 'sales_predictor_model.joblib')
        payload = joblib.load(model_path)
        if isinstance(payload, dict) and "model" in payload:
            model = payload["model"]
            feature_columns = payload.get("feature_columns")
        else:
            # Back-compat: older artifact with only the estimator
            model = payload
            feature_columns = [
                'tempmax','tempmin','temp','precip','snow',
                'windspeed','sealevelpressure','cloudcover','visibility','uvindex',
                'is_weekend','is_holiday','days_until_holiday',
                'hist_7d_avg','hist_28d_avg','dow_mean',
                'day_of_week_Monday','day_of_week_Saturday','day_of_week_Sunday',
                'day_of_week_Thursday','day_of_week_Tuesday','day_of_week_Wednesday'
            ]
        print(f"[model] loaded; {len(feature_columns)} features")
    except Exception as e:
        print(f"[model] ERROR: {e}")
        model = None
        feature_columns = None

load_model()

# ---------------------------
# Ingredient usage model loader (singleton)
# ---------------------------
usage_model_payload = None  # {"models": {ingredient_id: model}, "feature_columns": [...]}

def load_usage_model():
    """Load trained per-ingredient USAGE models and their feature list."""
    global usage_model_payload
    if usage_model_payload is not None:
        return
    try:
        from django.conf import settings
        model_path = os.path.join(settings.BASE_DIR, "ingredient_usage_model.joblib")
        usage_model_payload = joblib.load(model_path)
        print(f"[usage-model] loaded; {len(usage_model_payload.get('models', {}))} per-ingredient models")
    except Exception as e:
        print(f"[usage-model] ERROR: {e}")
        usage_model_payload = None

load_usage_model()


# ---------------------------
# SALES Feature helpers (unchanged)
# ---------------------------
def _historical_sales_averages(up_to_date: Date):
    start_28 = up_to_date - timedelta(days=28)
    hist = (PizzaSales.objects
            .filter(order_date__lt=up_to_date, order_date__gte=start_28)
            .values('order_date')
            .annotate(sales=Sum('total_price'))
            .order_by('order_date'))

    series = {row['order_date']: float(row['sales'] or 0.0) for row in hist}

    last7, last28 = [], []
    for i in range(1, 29):
        d = up_to_date - timedelta(days=i)
        if d in series:
            last28.append(series[d])
            if i <= 7:
                last7.append(series[d])

    hist_7d_avg = sum(last7)/len(last7) if len(last7) >= 3 else None
    hist_28d_avg = sum(last28)/len(last28) if len(last28) >= 7 else None

    weekday = up_to_date.weekday()
    year_ago = up_to_date - timedelta(days=365)
    dow_qs = (PizzaSales.objects
                .filter(order_date__lt=up_to_date, order_date__gte=year_ago)
                .values('order_date')
                .annotate(sales=Sum('total_price'))
                .order_by('order_date'))

    dow_vals = [float(r['sales'] or 0.0)
                for r in dow_qs
                if r['order_date'].weekday() == weekday]

    dow_mean = sum(dow_vals)/len(dow_vals) if len(dow_vals) >= 3 else None

    return hist_7d_avg, hist_28d_avg, dow_mean


def create_features_from_date(date: Date, weather_data: dict):
    """Build features for the SALES model."""
    day_of_week = date.strftime('%A')
    is_weekend = 1 if day_of_week in ['Saturday', 'Sunday'] else 0
    is_holiday = 1 if Holiday.objects.filter(date=date).exists() else 0

    days_until_holiday = 365
    future_holidays = Holiday.objects.filter(date__gt=date).order_by('date')
    if future_holidays.exists():
        days_until_holiday = (future_holidays.first().date - date).days

    h7, h28, dow = _historical_sales_averages(date)
    if h7 is None or h28 is None or dow is None:
        prior_days = PizzaSales.objects.filter(order_date__lt=date).values('order_date').distinct().count()
        total_sales = PizzaSales.objects.filter(order_date__lt=date).aggregate(s=Sum('total_price'))['s'] or 0.0
        global_mean = float(total_sales) / max(1, prior_days)
        h7  = h7  if h7  is not None else global_mean
        h28 = h28 if h28 is not None else global_mean
        dow = dow if dow is not None else global_mean

    row = {
        'tempmax': weather_data.get('tempmax', 0.0),
        'tempmin': weather_data.get('tempmin', 0.0),
        'temp':    weather_data.get('temp', 0.0),
        'precip':  weather_data.get('precip', 0.0),
        'snow':    weather_data.get('snow', 0.0),
        'windspeed': weather_data.get('windspeed', 0.0),
        'sealevelpressure': weather_data.get('sealevelpressure', 0.0),
        'cloudcover': weather_data.get('cloudcover', 0.0),
        'visibility': weather_data.get('visibility', 0.0),
        'uvindex':    weather_data.get('uvindex', 0.0),

        'is_weekend': is_weekend,
        'is_holiday': is_holiday,
        'days_until_holiday': days_until_holiday,

        'hist_7d_avg': h7,
        'hist_28d_avg': h28,
        'dow_mean': dow,

        'day_of_week_Monday':    1 if day_of_week == 'Monday' else 0,
        'day_of_week_Saturday':  1 if day_of_week == 'Saturday' else 0,
        'day_of_week_Sunday':    1 if day_of_week == 'Sunday' else 0,
        'day_of_week_Thursday':  1 if day_of_week == 'Thursday' else 0,
        'day_of_week_Tuesday':   1 if day_of_week == 'Tuesday' else 0,
        'day_of_week_Wednesday': 1 if day_of_week == 'Wednesday' else 0,
    }
    return pd.DataFrame([row])


# ---------------------------
# WEATHER helpers (shared)
# ---------------------------
def _get_or_fetch_weather(d: Date) -> Weather | None:
    """Return Weather row for date d; fetch from Open-Meteo if missing."""
    try:
        return Weather.objects.get(datetime=d)
    except Weather.DoesNotExist:
        try:
            fetch_and_store(d, d)
        except Exception as e:
            print(f"[Weather fetch] {d} failed: {e}")
        return Weather.objects.filter(datetime=d).first()


def _weather_to_dict(w: Weather) -> dict:
    return {
        'tempmax': w.tempmax,
        'tempmin': w.tempmin,
        'temp': w.temp,
        'precip': w.precip,
        'snow': w.snow,
        'windspeed': w.windspeed,
        'sealevelpressure': w.sealevelpressure,
        'cloudcover': w.cloudcover,
        'visibility': w.visibility,
        'uvindex': w.uvindex if w.uvindex is not None else 0.0,
    }


# ---------------------------
# NEW: Simple usage features (match train_usage_model.py)
# ---------------------------
def create_simple_usage_features(date: Date, weather_data: dict, feature_columns: list[str]):
    """Build features for the USAGE models: weather + is_weekend + is_holiday + weekday one-hots."""
    day = date.strftime('%A')
    row = {
        'tempmax': weather_data.get('tempmax', 0.0),
        'tempmin': weather_data.get('tempmin', 0.0),
        'temp':    weather_data.get('temp', 0.0),
        'precip':  weather_data.get('precip', 0.0),
        'snow':    weather_data.get('snow', 0.0),
        'windspeed': weather_data.get('windspeed', 0.0),
        'sealevelpressure': weather_data.get('sealevelpressure', 0.0),
        'cloudcover': weather_data.get('cloudcover', 0.0),
        'visibility': weather_data.get('visibility', 0.0),
        'uvindex':  weather_data.get('uvindex', 0.0),
        'is_weekend': 1 if day in ['Saturday','Sunday'] else 0,
        'is_holiday': 1 if Holiday.objects.filter(date=date).exists() else 0,
        'day_of_week_Monday':    1 if day == 'Monday' else 0,
        'day_of_week_Saturday':  1 if day == 'Saturday' else 0,
        'day_of_week_Sunday':    1 if day == 'Sunday' else 0,
        'day_of_week_Thursday':  1 if day == 'Thursday' else 0,
        'day_of_week_Tuesday':   1 if day == 'Tuesday' else 0,
        'day_of_week_Wednesday': 1 if day == 'Wednesday' else 0,
    }
    X = pd.DataFrame([row])
    for c in feature_columns:
        if c not in X.columns:
            X[c] = 0
    return X[feature_columns]


def ingredient_usage_for_day(date: Date):
    """
    Predict per-ingredient 'usage units' for a given date using the trained USAGE models.
    Units here are simple counts derived at training time (ingredient occurrence per pizza × quantity).
    """
    load_usage_model()

    if not usage_model_payload or "models" not in usage_model_payload:
        return {}

    w = _get_or_fetch_weather(date)
    weather_dict = _weather_to_dict(w) if w else {}

    models = usage_model_payload["models"]
    feature_cols = usage_model_payload["feature_columns"]

    needs = {}
    for ing in Ingredient.objects.all().order_by("name"):
        mdl = models.get(ing.id)
        if mdl is None:
            continue
        try:
            X = create_simple_usage_features(date, weather_dict, feature_cols)
            yhat = float(mdl.predict(X)[0])
            needs[ing.name] = max(0.0, yhat)
        except Exception as e:
            print(f"[usage-predict] {ing.name}: {e}")
            needs[ing.name] = 0.0
    return needs


# ---------------------------
# APIs
# ---------------------------
class DashboardStatsAPI(APIView):
    def get(self, request):
        qs_start = request.GET.get("start_date") or request.GET.get("date")
        base_date = parse_date(qs_start) if qs_start else None
        if base_date is None:
            base_date = datetime.now().date()

        today = datetime.now().date()
        agg = PizzaSales.objects.filter(order_date=today).aggregate(
            total_sales=Sum('total_price'),
            total_orders=Count('order_id', distinct=True),
            avg_check=Avg('total_price'),
        )
        total_sales = float(agg['total_sales'] or 0.0)
        total_orders = int(agg['total_orders'] or 0)
        avg_check = round(total_sales / total_orders, 2) if total_orders > 0 else 0.0

        sales_trend = list(
            PizzaSales.objects
            .values('order_date')
            .annotate(sales=Sum('total_price'))
            .order_by('order_date')
        )

        weekly_forecast = []
        for i in range(7):
            d = base_date + timedelta(days=i)
            label = d.strftime('%a')

            entry = {'day': label, 'date': d.isoformat(), 'amount': 0.0, 'change': 0.0}
            errors = []

            w = _get_or_fetch_weather(d)
            if not w:
                errors.append('no_weather')
            if model is None:
                errors.append('no_model')

            if not errors:
                try:
                    X = create_features_from_date(d, _weather_to_dict(w))
                    yhat = float(model.predict(X[feature_columns])[0])
                    entry['amount'] = round(yhat, 2)
                except Exception as e:
                    errors.append(f'predict_error:{e}')

            prev_amount = weekly_forecast[-1]['amount'] if weekly_forecast else entry['amount']
            entry['change'] = round(entry['amount'] - prev_amount, 2)

            if errors:
                entry['error'] = ",".join(errors)
                print(f"[WeeklyForecast] {d} -> {entry['error']}")

            weekly_forecast.append(entry)

        day_of_week_data = [{'day': x['day'], 'sales': x['amount']} for x in weekly_forecast]

        return Response({
            'today_sales': round(total_sales, 2),
            'total_orders': total_orders,
            'avg_check': avg_check,
            'weekly_forecast': weekly_forecast,
            'sales_trend': sales_trend,
            'day_of_week_data': day_of_week_data
        })


class PredictSalesAPI(APIView):
    def post(self, request):
        date_str = request.data.get('prediction_date') or request.data.get('date')
        try:
            target = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        if model is None:
            return Response({'error': 'Model not loaded.'}, status=500)

        manual_weather = request.data.get('weather_data') or {}
        w = _get_or_fetch_weather(target)
        if not w and not manual_weather:
            return Response({'error': 'Weather data not available for this date.'}, status=404)

        weather_dict = _weather_to_dict(w) if w else {}
        weather_dict.update({k: manual_weather[k] for k in manual_weather})

        try:
            X = create_features_from_date(target, weather_dict)
            yhat = float(model.predict(X[feature_columns])[0])
        except Exception as e:
            return Response({'error': f'Prediction error: {e}'}, status=500)

        return Response({'date': date_str, 'predicted_sales': round(yhat, 2)})


class DashboardSalesForDateAPI(APIView):
    def get(self, request):
        d = parse_date(request.GET.get('date')) or datetime.now().date()
        qs = PizzaSales.objects.filter(order_date=d)
        agg = qs.aggregate(total_sales=Sum('total_price'),
                           total_orders=Count('order_id', distinct=True),
                           avg_check=Avg('total_price'))
        total_sales = float(agg['total_sales'] or 0.0)
        total_orders = int(agg['total_orders'] or 0)
        avg_check = float(agg['avg_check'] or 0.0)
        return Response({
            'today_sales': round(total_sales, 2),
            'total_orders': total_orders,
            'avg_check': round(avg_check, 2),
        })


class SalesDataAPI(APIView):
    def get(self, request):
        sales = (PizzaSales.objects
                 .values('order_date')
                 .annotate(
                    total_sales=Sum('total_price'),
                    total_orders=Count('order_id', distinct=True),
                    avg_check=Avg('total_price'))
                 .order_by('order_date'))

        out = []
        for row in sales:
            d = row['order_date']
            out.append({
                'date': d.strftime('%Y-%m-%d'),
                'totalSales': round(float(row['total_sales'] or 0.0), 2),
                'totalOrders': int(row['total_orders'] or 0),
                'avgCheck': round(float(row['avg_check'] or 0.0), 2),
                'dayOfWeek': d.strftime('%A')
            })
        return Response(out)


class DailySalesDetailAPI(APIView):
    def get(self, request, date_str):
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        qs = PizzaSales.objects.filter(order_date=d)
        if not qs.exists():
            return Response({'error': 'No sales data found for this date.'}, status=404)

        df = pd.DataFrame(list(qs.values()))
        if df.empty:
            return Response({'error': 'No sales data found for this date.'}, status=404)

        top = (df.groupby('pizza_name')
                 .agg(quantity=pd.NamedAgg(column='quantity', aggfunc='sum'),
                      revenue=pd.NamedAgg(column='total_price', aggfunc='sum'))
                 .reset_index()
                 .sort_values(by='quantity', ascending=False)
                 .head(5))

        avg_check = float(df['total_price'].mean() or 0.0)
        total_sales = float(df['total_price'].sum() or 0.0)
        total_orders = int(df['order_id'].nunique() if 'order_id' in df.columns else len(df))

        return Response({
            'topPizzas': top.to_dict('records'),
            'avg_check': round(avg_check, 2),
            'total_sales': round(total_sales, 2),
            'total_orders': total_orders,
        })


class InventoryAPI(APIView):
    def get(self, request):
        d = parse_date(request.GET.get("date")) or datetime.now().date()
        usage = ingredient_usage_for_day(d)

        rows = []
        for ing in Ingredient.objects.all().order_by("name"):
            # Latest stock before given date (supports either current_stock or quantity field)
            snap = (InventoryLevel.objects
                    .filter(ingredient=ing, date__lte=d)
                    .order_by("-date")
                    .first())
            if snap:
                cur = float(getattr(snap, "current_stock", getattr(snap, "quantity", 0.0)) or 0.0)
            else:
                cur = 0.0

            pred = float(usage.get(ing.name, 0.0))
            rows.append({
                "id": str(ing.id),
                "ingredient": ing.name,
                "unit": ing.unit,
                "currentStock": cur,
                "predictedUsage": round(pred, 2),
                "reorderLevel": ing.reorder_level,
                "cost": ing.unit_cost,
            })
        return Response(rows)
