import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { DollarSign, ShoppingCart, TrendingUp, Calendar as CalendarIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";

type WeeklyForecastItem = {
  day: string;     // "Mon", "Tue", ...
  date: string;    // "YYYY-MM-DD"
  amount: number;  // predicted sales
  change: number;  // delta vs previous day
  error?: string;
};

type SalesTrendItem = {
  order_date?: string;
  date?: string;
  sales: number;
};

type QuickStats = {
  today_sales: number;
  total_orders: number;
  avg_check: number;
};

type DashboardPayload = QuickStats & {
  weekly_forecast: WeeklyForecastItem[];
  sales_trend: SalesTrendItem[];
  day_of_week_data?: { day: string; sales: number }[];
};

type DailyDetail = {
  topPizzas: { pizza_name: string; quantity: number; revenue: number }[];
  avg_check: number;
  total_sales: number;
  total_orders: number;
};

const fmtDate = (d: Date) => format(d, "yyyy-MM-dd");

export default function Dashboard() {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);

  const [stats, setStats] = useState<QuickStats | null>(null);
  const [weeklyForecast, setWeeklyForecast] = useState<WeeklyForecastItem[]>([]);
  const [salesTrendData, setSalesTrendData] = useState<SalesTrendItem[]>([]);
  const [prediction, setPrediction] = useState<number | null>(null);

  const [dailyDetail, setDailyDetail] = useState<DailyDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [predictLoading, setPredictLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async (anchor?: Date) => {
    setLoading(true);
    setError(null);
    try {
      const qs = anchor ? `?start_date=${fmtDate(anchor)}` : "";
      const res = await fetch(`/api/dashboard/stats/${qs}`);
      if (!res.ok) throw new Error("Failed to load dashboard data");
      const data: DashboardPayload = await res.json();

      setStats({
        today_sales: data.today_sales,
        total_orders: data.total_orders,
        avg_check: data.avg_check,
      });

      // ensure amount is numeric for recharts
      const wf = (data.weekly_forecast || []).map((d) => ({
        ...d,
        amount: Number(d.amount ?? 0),
      }));
      setWeeklyForecast(wf);

      setSalesTrendData(data.sales_trend || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  // initial load
  useEffect(() => {
    fetchDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // when date changes, refetch weekly forecast anchored at selectedDate
  useEffect(() => {
    fetchDashboard(selectedDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate]);

  const trendData = useMemo(
    () =>
      (salesTrendData || []).map((d) => ({
        date: d.date ?? d.order_date,
        sales: d.sales,
      })),
    [salesTrendData]
  );

  const handlePredict = async () => {
    if (!selectedDate) {
      setError("Please pick a date to predict.");
      return;
    }
    setPredictLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/predict/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prediction_date: fmtDate(selectedDate) }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Prediction failed");
      setPrediction(Number(json.predicted_sales ?? 0));
    } catch (e: any) {
      setError(e?.message || "Prediction failed");
    } finally {
      setPredictLoading(false);
    }
  };

  const refreshSalesForSelectedDate = async () => {
    if (!selectedDate) {
      setError("Please pick a date first.");
      return;
    }
    setError(null);
    try {
      const url = `/api/dashboard/sales?date=${encodeURIComponent(fmtDate(selectedDate))}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to refresh cards");
      const data: QuickStats = await res.json();
      setStats(data);
    } catch (e: any) {
      setError(e?.message || "Failed to refresh cards");
    }
  };

  const loadDailyDetail = async () => {
    if (!selectedDate) {
      setError("Please pick a date first.");
      return;
    }
    setError(null);
    try {
      const url = `/api/salesdata/${encodeURIComponent(fmtDate(selectedDate))}/`;
      const res = await fetch(url);
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load daily detail");
      setDailyDetail(json);
    } catch (e: any) {
      setError(e?.message || "Failed to load daily detail");
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Sales Prediction Dashboard</h1>
          <p className="text-slate-400">Forecast your daily sales with AI-powered analytics</p>
        </div>
      </div>

      {error && (
        <Card className="border-red-500/40 bg-red-500/10">
          <CardContent className="py-3 text-red-200 text-sm">{error}</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left column: prediction panel */}
        <Card>
          <CardHeader>
            <CardTitle>Sales Prediction</CardTitle>
            <CardDescription>Select a date to predict sales</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex w-full items-center gap-3">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
                      !selectedDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {selectedDate ? format(selectedDate, "PPP") : <span>Pick a date</span>}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={selectedDate}
                    onSelect={setSelectedDate}
                    initialFocus
                    // Month/Year controls:
                    captionLayout="dropdown"
                    fromYear={2010}
                    toYear={new Date().getFullYear() + 2}
                    pagedNavigation
                  />
                </PopoverContent>
              </Popover>

              <Button onClick={handlePredict} disabled={!selectedDate || predictLoading}>
                {predictLoading ? "Predicting..." : "Predict Sales"}
              </Button>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="secondary" onClick={refreshSalesForSelectedDate} disabled={!selectedDate}>
                Refresh Cards
              </Button>
              <Button variant="ghost" onClick={loadDailyDetail} disabled={!selectedDate}>
                View Daily Detail
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Predicted Sales</CardDescription>
                  <CardTitle className="text-2xl flex items-center gap-2">
                    <DollarSign className="w-5 h-5" />
                    {prediction !== null ? prediction.toFixed(2) : "0.00"}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Orders Today</CardDescription>
                  <CardTitle className="text-2xl flex items-center gap-2">
                    <ShoppingCart className="w-5 h-5" />
                    {stats?.total_orders ?? 0}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Avg Check</CardDescription>
                  <CardTitle className="text-2xl">
                    ${stats ? (stats.avg_check || 0).toFixed(2) : "0.00"}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>
          </CardContent>
        </Card>

        {/* Middle column: today summary */}
        <Card>
          <CardHeader>
            <CardTitle>Today’s Summary</CardTitle>
            <CardDescription>Live overview</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-slate-400 text-sm">Sales</div>
              <div className="text-2xl font-semibold">${stats ? (stats.today_sales || 0).toFixed(2) : "0.00"}</div>
            </div>
            <div>
              <div className="text-slate-400 text-sm">Orders</div>
              <div className="text-2xl font-semibold">{stats?.total_orders ?? 0}</div>
            </div>
            <div>
              <div className="text-slate-400 text-sm">Avg Check</div>
              <div className="text-2xl font-semibold">${stats ? (stats.avg_check || 0).toFixed(2) : "0.00"}</div>
            </div>
          </CardContent>
        </Card>

        {/* Right column: weekly forecast */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" /> Weekly Forecast
            </CardTitle>
            <CardDescription>
              7-day outlook starting {selectedDate ? format(selectedDate, "PPP") : "today"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Ensure the parent actually has size */}
            <div className="w-full h-[260px] min-w-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={weeklyForecast}
                  margin={{ top: 8, right: 12, bottom: 8, left: 12 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" />
                  <YAxis
                    width={48}
                    domain={[
                      (dataMin: number) => Math.floor(dataMin - 10),
                      (dataMax: number) => Math.ceil(dataMax + 10),
                    ]}
                    allowDecimals={false}
                  />
                  <Tooltip
                    formatter={(v: any) => Number(v).toFixed(2)}
                    labelFormatter={(_, i) => weeklyForecast?.[i!]?.date ?? ""}
                  />
                  {/* Explicit fill to avoid theme resets making bars transparent */}
                  <Bar
                    dataKey="amount"
                    isAnimationActive={false}
                    barSize={28}
                    radius={[6, 6, 0, 0]}
                    fill="#60a5fa"      // tailwind sky-400
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="text-xs text-slate-400 mt-2">
              Showing {weeklyForecast.length} forecast days
              {weeklyForecast.some((d) => d.error) && " · Some days are provisional due to missing data"}
            </div>

            {/* Debug helper: comment out when happy */}
            {/* <pre className="text-[10px] text-slate-400 mt-2 overflow-auto max-h-24">
              {JSON.stringify(weeklyForecast, null, 2)}
            </pre> */}
          </CardContent>
        </Card>
      </div>

      {/* Sales trend */}
      <Card>
        <CardHeader>
          <CardTitle>Sales Trend</CardTitle>
          <CardDescription>Historic daily sales</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="w-full h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="sales" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Daily detail preview */}
      {dailyDetail && (
        <Card>
          <CardHeader>
            <CardTitle>
              Daily Detail ({selectedDate ? fmtDate(selectedDate) : ""})
            </CardTitle>
            <CardDescription>
              Orders: {dailyDetail.total_orders} · Sales: ${dailyDetail.total_sales.toFixed(2)} · Avg check: $
              {dailyDetail.avg_check.toFixed(2)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-slate-300 mb-2">Top pizzas</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {dailyDetail.topPizzas.map((p) => (
                <div
                  key={p.pizza_name}
                  className="flex justify-between border border-white/10 rounded-md px-3 py-2"
                >
                  <span>{p.pizza_name}</span>
                  <span>
                    {p.quantity} · ${p.revenue.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading overlay (simple) */}
      {loading && (
        <div className="text-xs text-slate-400">Loading dashboard…</div>
      )}
    </div>
  );
}
