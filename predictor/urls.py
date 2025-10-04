from django.urls import path
from .views import PredictSalesAPI, SalesDataAPI, DailySalesDetailAPI, InventoryAPI, DashboardStatsAPI, DashboardSalesForDateAPI# Add DashboardStatsAPI here

urlpatterns = [
    path('dashboard/stats/', DashboardStatsAPI.as_view(), name='api_dashboard_stats'),
    path('dashboard/sales', DashboardSalesForDateAPI.as_view(), name='api_dashboard_sales_for_date'),  # NEW
    path('predict/', PredictSalesAPI.as_view(), name='api_predict_sales'),
    path('salesdata/', SalesDataAPI.as_view(), name='api_sales_data'),
    path('salesdata/<str:date_str>/', DailySalesDetailAPI.as_view(), name='api_daily_sales_detail'),
    path('inventory/', InventoryAPI.as_view(), name='api_inventory'),
]
