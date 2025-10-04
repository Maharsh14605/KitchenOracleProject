import os
import pandas as pd
from django.core.management.base import BaseCommand
from predictor.models import PizzaSales, Weather, Holiday

class Command(BaseCommand):
    help = 'Processes raw data and creates a single, merged dataset for model training.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting data processing and feature engineering...")

        # 1. Load data from Django models into Pandas DataFrames
        sales_df = pd.DataFrame(list(PizzaSales.objects.all().values()))
        weather_df = pd.DataFrame(list(Weather.objects.all().values()))
        holiday_df = pd.DataFrame(list(Holiday.objects.all().values()))

        # 2. Convert date/time columns to datetime objects for proper manipulation
        sales_df['order_datetime'] = pd.to_datetime(sales_df['order_date'].astype(str) + ' ' + sales_df['order_time'].astype(str))
        weather_df['datetime'] = pd.to_datetime(weather_df['datetime'])
        holiday_df['date'] = pd.to_datetime(holiday_df['date'])

        # 3. Aggregate sales data by day
        daily_sales_df = sales_df.groupby(sales_df['order_datetime'].dt.date).agg(
            total_sales=('total_price', 'sum'),
            total_orders=('order_id', pd.Series.nunique),
            total_quantity=('quantity', 'sum')
        ).reset_index()

        daily_sales_df['order_datetime'] = pd.to_datetime(daily_sales_df['order_datetime'])
        
        # 4. Merge all three datasets
        # Merge sales with weather
        merged_df = pd.merge(daily_sales_df, weather_df, left_on='order_datetime', right_on='datetime', how='left')
        
        # Merge with holidays
        merged_df = pd.merge(merged_df, holiday_df, left_on='order_datetime', right_on='date', how='left')

        # 5. Feature Engineering
        merged_df['day_of_week'] = merged_df['order_datetime'].dt.day_name()
        merged_df['month'] = merged_df['order_datetime'].dt.month
        merged_df['is_weekend'] = merged_df['day_of_week'].isin(['Saturday', 'Sunday']).astype(int)
        merged_df['is_holiday'] = merged_df['holiday_name'].notna().astype(int)
        
        # Create a new feature for "days until a holiday" to capture anticipation effects
        merged_df['days_until_holiday'] = None
        for i, row in merged_df.iterrows():
            if row['is_holiday'] == 0:
                future_holidays = merged_df[(merged_df['order_datetime'] > row['order_datetime']) & (merged_df['is_holiday'] == 1)]
                if not future_holidays.empty:
                    days_diff = (future_holidays['order_datetime'].iloc[0] - row['order_datetime']).days
                    merged_df.at[i, 'days_until_holiday'] = days_diff

        # 6. Clean up the final DataFrame
        merged_df.drop(columns=['datetime', 'date', 'holiday_name'], inplace=True)
        merged_df.rename(columns={'order_datetime': 'date'}, inplace=True)

        # 7. Save the processed data to a new CSV file
        processed_data_path = os.path.join(os.getcwd(), 'processed_sales_data.csv')
        merged_df.to_csv(processed_data_path, index=False)
        
        self.stdout.write(self.style.SUCCESS(f"Data processing complete! Processed data saved to {processed_data_path}"))