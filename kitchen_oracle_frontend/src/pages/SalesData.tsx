import { useEffect, useMemo, useState } from "react";
import { format, parseISO, isWithinInterval, compareDesc } from "date-fns";
import {
  BarChart3,
  Eye,
  TrendingUp,
  TrendingDown,
  Calendar as CalendarIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type SalesRow = {
  date: string;        // "YYYY-MM-DD"
  totalSales: number;
  totalOrders: number;
  avgCheck: number;
  dayOfWeek: string;
};

type DailyDetail = {
  topPizzas: { pizza_name: string; quantity: number; revenue: number }[];
  avg_check: number;
  total_sales: number;
  total_orders: number;
};

type Range = { from?: Date; to?: Date } | undefined;

const fmtUSD = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function SalesData() {
  const [rows, setRows] = useState<SalesRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState<Range>(undefined);
  const [error, setError] = useState<string | null>(null);

  // dialog
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [detail, setDetail] = useState<DailyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ---- Fetch all rows once ----
  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/salesdata/");
        if (!res.ok) throw new Error("Failed to load sales data");
        const data = await res.json();
        // backend returns [{date,totalSales,totalOrders,avgCheck,dayOfWeek}]
        setRows(
          (data as any[]).map((r) => ({
            date: r.date,
            totalSales: Number(r.totalSales || 0),
            totalOrders: Number(r.totalOrders || 0),
            avgCheck: Number(r.avgCheck || 0),
            dayOfWeek: r.dayOfWeek,
          }))
        );
      } catch (e: any) {
        setError(e?.message || "Failed to load sales data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ---- Filter by date range (client-side) ----
  const filtered = useMemo(() => {
    if (!range?.from || !range?.to) {
      // no range selected -> show everything
      return [...rows].sort((a, b) =>
        compareDesc(parseISO(a.date), parseISO(b.date))
      );
    }
    return rows
      .filter((r) =>
        isWithinInterval(parseISO(r.date), { start: range.from!, end: range.to! })
      )
      .sort((a, b) => compareDesc(parseISO(a.date), parseISO(b.date)));
  }, [rows, range]);

  // ---- Summary cards based on filtered data ----
  const cards = useMemo(() => {
    if (filtered.length === 0) {
      return {
        sevenDayAvg: 0,
        bestDay: { sales: 0, dow: "-" },
        totalOrders: 0,
        avgCheck: 0,
      };
    }

    const best = filtered.reduce(
      (acc, r) => (r.totalSales > acc.sales ? { sales: r.totalSales, dow: r.dayOfWeek } : acc),
      { sales: 0, dow: "-" }
    );

    const totalOrders = filtered.reduce((s, r) => s + r.totalOrders, 0);
    const totalSales = filtered.reduce((s, r) => s + r.totalSales, 0);
    const avgCheck = totalOrders > 0 ? totalSales / totalOrders : 0;

    // "7-day average" from the latest up to 7 rows in the filtered set
    const latest7 = filtered.slice(0, 7);
    const sevenDayAvg =
      latest7.reduce((s, r) => s + r.totalSales, 0) / Math.max(1, latest7.length);

    return { sevenDayAvg, bestDay: best, totalOrders, avgCheck };
  }, [filtered]);

  // ---- Daily detail dialog ----
  const openDetails = async (isoDate: string) => {
    setSelectedDate(isoDate);
    setDetail(null);
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/salesdata/${encodeURIComponent(isoDate)}/`);
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load daily detail");
      // backend returns snake_case keys; map to our UI
      const mapped: DailyDetail = {
        topPizzas: (json.topPizzas || []).map((p: any) => ({
          pizza_name: p.pizza_name ?? p.name,
          quantity: Number(p.quantity || 0),
          revenue: Number(p.revenue || 0),
        })),
        avg_check: Number(json.avg_check || 0),
        total_sales: Number(json.total_sales || 0),
        total_orders: Number(json.total_orders || 0),
      };
      setDetail(mapped);
    } catch (e: any) {
      setError(e?.message || "Failed to load daily detail");
    } finally {
      setDetailLoading(false);
    }
  };

  // ---- CSV export (filtered) ----
  const exportCSV = () => {
    if (filtered.length === 0) return;
    const header = ["date,totalSales,totalOrders,avgCheck,dayOfWeek"];
    const lines = filtered.map(
      (r) =>
        `${r.date},${r.totalSales.toFixed(2)},${r.totalOrders},${r.avgCheck.toFixed(
          2
        )},${r.dayOfWeek}`
    );
    const blob = new Blob([header.concat(lines).join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const label =
      range?.from && range?.to
        ? `sales_${format(range.from, "yyyyMMdd")}-${format(range.to, "yyyyMMdd")}.csv`
        : "sales_all.csv";
    a.download = label;
    a.click();
    URL.revokeObjectURL(url);
  };

  // % change helper
  const dayChange = (current: number, previous: number) =>
    previous ? ((current - previous) / previous) * 100 : 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">Sales Data &amp; Insights</h1>
          <p className="text-slate-400">
            Historical daily sales data with detailed breakdowns
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Date range picker */}
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "justify-start text-left font-normal min-w-[260px]",
                  !range?.from && !range?.to && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {range?.from && range?.to ? (
                  <>
                    {format(range.from, "PPP")} – {format(range.to, "PPP")}
                  </>
                ) : (
                  <span>Select date range</span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="p-0" align="end">
              <Calendar
                mode="range"
                selected={range}
                onSelect={setRange}
                numberOfMonths={2}
                defaultMonth={range?.from}
                captionLayout="dropdown"
                fromYear={2010}
                toYear={new Date().getFullYear() + 2}
                pagedNavigation
                initialFocus
              />
            </PopoverContent>
          </Popover>

          <Button onClick={exportCSV} className="bg-gradient-primary text-white shadow-glow">
            <BarChart3 className="w-4 h-4 mr-2" />
            Export Data
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">7-Day Average</p>
                <p className="text-2xl font-bold text-white">${fmtUSD(cards.sevenDayAvg)}</p>
              </div>
              <TrendingUp className="w-8 h-8 text-success" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Best Day</p>
                <p className="text-2xl font-bold text-white">
                  ${fmtUSD(cards.bestDay.sales)}
                </p>
                <p className="text-xs text-slate-500">{cards.bestDay.dow}</p>
              </div>
              <CalendarIcon className="w-8 h-8 text-warning" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Total Orders</p>
                <p className="text-2xl font-bold text-white">
                  {cards.totalOrders.toLocaleString()}
                </p>
              </div>
              <BarChart3 className="w-8 h-8 text-primary" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Avg Check</p>
                <p className="text-2xl font-bold text-white">${fmtUSD(cards.avgCheck)}</p>
              </div>
              <TrendingUp className="w-8 h-8 text-success" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sales Table */}
      <Card className="bg-gradient-card border-white/10 shadow-elegant">
        <CardHeader>
          <CardTitle className="text-white">Daily Sales History</CardTitle>
          <CardDescription className="text-slate-400">
            Click any date for the detailed breakdown
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="text-red-300 text-sm mb-3">
              {error}
            </div>
          )}
          {loading ? (
            <div className="text-slate-400 text-sm">Loading sales…</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-white/10">
                  <TableHead className="text-slate-300">Date</TableHead>
                  <TableHead className="text-slate-300">Day</TableHead>
                  <TableHead className="text-slate-300">Total Sales</TableHead>
                  <TableHead className="text-slate-300">Orders</TableHead>
                  <TableHead className="text-slate-300">Avg Check</TableHead>
                  <TableHead className="text-slate-300">Change</TableHead>
                  <TableHead className="text-slate-300">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((day, idx) => {
                  const prev = filtered[idx + 1];
                  const changePct = prev ? dayChange(day.totalSales, prev.totalSales) : 0;

                  return (
                    <TableRow key={day.date} className="border-white/10 hover:bg-white/5">
                      <TableCell className="text-white font-medium">
                        {format(parseISO(day.date), "MMM d, yyyy")}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-slate-300 border-white/20">
                          {day.dayOfWeek}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-white font-bold">
                        ${fmtUSD(day.totalSales)}
                      </TableCell>
                      <TableCell className="text-slate-300">{day.totalOrders}</TableCell>
                      <TableCell className="text-slate-300">${fmtUSD(day.avgCheck)}</TableCell>
                      <TableCell>
                        <div
                          className={cn(
                            "flex items-center gap-1",
                            changePct > 0
                              ? "text-success"
                              : changePct < 0
                              ? "text-destructive"
                              : "text-slate-400"
                          )}
                        >
                          {changePct > 0 ? (
                            <TrendingUp className="w-4 h-4" />
                          ) : changePct < 0 ? (
                            <TrendingDown className="w-4 h-4" />
                          ) : null}
                          {changePct !== 0 ? `${changePct > 0 ? "+" : ""}${changePct.toFixed(1)}%` : "-"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              className="bg-white/5 border-white/20 text-white hover:bg-white/10"
                              onClick={() => openDetails(day.date)}
                            >
                              <Eye className="w-4 h-4 mr-2" />
                              View Details
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="bg-slate-900 border-white/10 text-white">
                            <DialogHeader>
                              <DialogTitle>
                                Sales Details – {format(parseISO(selectedDate || day.date), "MMMM d, yyyy")}
                              </DialogTitle>
                              <DialogDescription className="text-slate-400">
                                {day.dayOfWeek}
                              </DialogDescription>
                            </DialogHeader>

                            {detailLoading ? (
                              <div className="text-slate-400 text-sm">Loading…</div>
                            ) : detail ? (
                              <div className="space-y-6">
                                {/* Summary */}
                                <div className="grid grid-cols-3 gap-4">
                                  <div className="text-center p-4 bg-white/5 rounded-lg">
                                    <p className="text-2xl font-bold text-white">${fmtUSD(detail.total_sales)}</p>
                                    <p className="text-sm text-slate-400">Total Sales</p>
                                  </div>
                                  <div className="text-center p-4 bg-white/5 rounded-lg">
                                    <p className="text-2xl font-bold text-white">{detail.total_orders}</p>
                                    <p className="text-sm text-slate-400">Total Orders</p>
                                  </div>
                                  <div className="text-center p-4 bg-white/5 rounded-lg">
                                    <p className="text-2xl font-bold text-white">${fmtUSD(detail.avg_check)}</p>
                                    <p className="text-sm text-slate-400">Average Check</p>
                                  </div>
                                </div>

                                {/* Top pizzas */}
                                <div>
                                  <h4 className="text-lg font-semibold text-white mb-3">Top 5 Pizzas</h4>
                                  <div className="space-y-2">
                                    {detail.topPizzas.map((p, i) => (
                                      <div
                                        key={`${p.pizza_name}-${i}`}
                                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                                      >
                                        <div className="flex items-center gap-3">
                                          <span className="w-6 h-6 bg-primary rounded-full flex items-center justify-center text-xs font-bold">
                                            {i + 1}
                                          </span>
                                          <span className="text-white font-medium">{p.pizza_name}</span>
                                        </div>
                                        <div className="text-right">
                                          <p className="text-white font-medium">{p.quantity} sold</p>
                                          <p className="text-sm text-slate-400">${fmtUSD(p.revenue)}</p>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="text-slate-400 text-sm">No details available.</div>
                            )}
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
