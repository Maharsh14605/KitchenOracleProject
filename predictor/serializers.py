from rest_framework import serializers
from .models import PizzaSales, Weather, Holiday

class PizzaSalesSerializer(serializers.ModelSerializer):
    """
    Serializes all fields from the PizzaSales model.
    """
    class Meta:
        model = PizzaSales
        fields = '__all__'

class WeatherSerializer(serializers.ModelSerializer):
    """
    Serializes all fields from the Weather model.
    """
    class Meta:
        model = Weather
        fields = '__all__'

class HolidaySerializer(serializers.ModelSerializer):
    """
    Serializes all fields from the Holiday model.
    """
    class Meta:
        model = Holiday
        fields = '__all__'
        
class DailySalesSerializer(serializers.Serializer):
    """
    Serializer for the aggregated daily sales data.
    This is not a ModelSerializer because it's based on aggregated data,
    not a single model.
    """
    order_date = serializers.DateField()
    total_sales = serializers.FloatField()
    total_orders = serializers.IntegerField()
    avg_check = serializers.FloatField()
    day_of_week = serializers.CharField(max_length=10)