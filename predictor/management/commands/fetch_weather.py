from django.core.management.base import BaseCommand
from datetime import date, timedelta
from predictor.services.open_meteo import fetch_and_store

class Command(BaseCommand):
    help = "Fetch Open-Meteo weather for a date range (defaults: today..+15)."

    def add_arguments(self, parser):
        parser.add_argument("--start", type=str, help="YYYY-MM-DD (default: today)")
        parser.add_argument("--end", type=str, help="YYYY-MM-DD (default: today+15)")

    def handle(self, *args, **opts):
        today = date.today()
        start = date.fromisoformat(opts["start"]) if opts.get("start") else today
        end   = date.fromisoformat(opts["end"])   if opts.get("end")   else today + timedelta(days=15)
        n = fetch_and_store(start, end)
        self.stdout.write(self.style.SUCCESS(f"Saved/updated weather rows: {n} ({start}..{end})"))
