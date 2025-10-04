import os
import csv
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from predictor.models import PizzaSales, Weather, Holiday

class Command(BaseCommand):
    help = 'Loads data from CSV files into the database'

    def handle(self, *args, **kwargs):
        # Determine the absolute path to the directory containing this script.
        # This is a robust way to handle file paths regardless of where the command is run.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Construct the paths to your three CSV files with their new names.
        # The '..' navigates up the directory tree to the project root.
        sales_csv_path = os.path.join(base_dir, '..', '..', '..', 'Pizza_Sales.csv')
        weather_csv_path = os.path.join(base_dir, '..', '..', '..', 'Weather.csv')
        holiday_csv_path = os.path.join(base_dir, '..', '..', '..', 'Holiday.csv')

        # Use a database transaction for efficiency and to ensure atomicity.
        # If any part of the load fails, the entire transaction will be rolled back.
        with transaction.atomic():
            self.stdout.write("Deleting old data...")
            PizzaSales.objects.all().delete()
            Weather.objects.all().delete()
            Holiday.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Old data deleted."))

            # Load Pizza Sales Data
            self.stdout.write("Loading pizza sales data...")
            try:
                with open(sales_csv_path, 'r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    pizza_sales_objects = []
                    for row in reader:
                        pizza_sales_objects.append(PizzaSales(
                            order_details_id=int(row['order_details_id']),
                            order_id=int(row['order_id']),
                            pizza_id=row['pizza_id'],
                            quantity=int(row['quantity']),
                            order_date=datetime.strptime(row['order_date'], '%m/%d/%y').date(), # Corrected this line
                            order_time=datetime.strptime(row['order_time'], '%H:%M:%S').time(),
                            unit_price=float(row['unit_price']),
                            total_price=float(row['total_price']),
                            pizza_size=row['pizza_size'],
                            pizza_category=row['pizza_category'],
                            pizza_ingredients=row['pizza_ingredients'],
                            pizza_name=row['pizza_name']
                        ))
                    PizzaSales.objects.bulk_create(pizza_sales_objects)
                self.stdout.write(self.style.SUCCESS('Pizza sales data loaded successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error loading pizza sales data: {e}"))
                return

            # Load Weather Data
            self.stdout.write("Loading weather data...")
            try:
                with open(weather_csv_path, 'r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    weather_objects = []
                    for row in reader:
                        weather_objects.append(Weather(
                            datetime=datetime.strptime(row['datetime'], '%Y-%m-%d').date(),
                            tempmax=float(row['tempmax']) if row['tempmax'] else 0.0,
                            tempmin=float(row['tempmin']) if row['tempmin'] else 0.0,
                            temp=float(row['temp']) if row['temp'] else 0.0,
                            precip=float(row['precip']) if row['precip'] else 0.0,
                            snow=float(row['snow']) if row['snow'] else 0.0,
                            windspeed=float(row['windspeed']) if row['windspeed'] else 0.0,
                            sealevelpressure=float(row['sealevelpressure']) if row['sealevelpressure'] else 0.0,
                            cloudcover=float(row['cloudcover']) if row['cloudcover'] else 0.0,
                            visibility=float(row['visibility']) if row['visibility'] else 0.0,
                            uvindex=float(row['uvindex']) if row['uvindex'] else None,
                            conditions=row['conditions'] if row['conditions'] else '',
                            description=row['description'] if row['description'] else '',
                            icon=row['icon'] if row['icon'] else ''
                        ))
                    Weather.objects.bulk_create(weather_objects)
                self.stdout.write(self.style.SUCCESS('Weather data loaded successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error loading weather data: {e}"))
                return

            # Load Holiday Data
            self.stdout.write("Loading holiday data...")
            try:
                with open(holiday_csv_path, 'r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    holiday_objects = []
                    for row in reader:
                        holiday_objects.append(Holiday(
                            date=datetime.strptime(row['Date'].split('T')[0], '%Y-%m-%d').date(),
                            holiday_name=row['Holiday Name']
                        ))
                    Holiday.objects.bulk_create(holiday_objects)
                self.stdout.write(self.style.SUCCESS('Holiday data loaded successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error loading holiday data: {e}"))
                return
