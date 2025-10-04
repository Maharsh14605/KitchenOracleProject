import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { AlertTriangle, Package, Edit3, Save, X, TrendingDown, Calendar as CalendarIcon } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { cn } from "@/lib/utils";

type InventoryItem = {
  id: string;
  ingredient: string;
  unit: string;
  currentStock: number;
  predictedUsage: number;
  reorderLevel: number;
  cost: number;
};

const fmt = (d: Date) => format(d, "yyyy-MM-dd");

const statusStyles: Record<
  "success" | "warning" | "destructive",
  { badge: string; text: string }
> = {
  success: { badge: "border-green-500/50 text-green-400", text: "text-green-400" },
  warning: { badge: "border-yellow-500/50 text-yellow-400", text: "text-yellow-400" },
  destructive: { badge: "border-red-500/50 text-red-400", text: "text-red-400" },
};

export default function Inventory() {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [rows, setRows] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // inline editing
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<number>(0);

  // ----- fetch -----
  const fetchInventory = async (d: Date) => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(`/api/inventory/?date=${encodeURIComponent(fmt(d))}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load inventory");
      // Coerce numbers
      const normalized: InventoryItem[] = (json as any[]).map((r) => ({
        ...r,
        currentStock: Number(r.currentStock ?? 0),
        predictedUsage: Number(r.predictedUsage ?? 0),
        reorderLevel: Number(r.reorderLevel ?? 0),
        cost: Number(r.cost ?? 0),
      }));
      setRows(normalized);
    } catch (e: any) {
      setErr(e?.message || "Failed to load inventory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory(selectedDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate]);

  // ----- helpers -----
  const getStatus = (current: number, predicted: number, reorder: number) => {
    const remaining = current - predicted;
    if (remaining < 0) return { label: "CRITICAL", key: "destructive" as const, remaining };
    if (current <= reorder) return { label: "LOW STOCK", key: "warning" as const, remaining };
    if (remaining <= reorder * 0.5) return { label: "WARNING", key: "warning" as const, remaining };
    return { label: "GOOD", key: "success" as const, remaining };
  };

  const criticalItems = useMemo(
    () =>
      rows.filter((r) => {
        const s = getStatus(r.currentStock, r.predictedUsage, r.reorderLevel);
        return s.key !== "success";
      }),
    [rows]
  );

  const totalReorderCost = useMemo(() => {
    // naive: bring each low/critical item up to 2× reorder level
    return criticalItems.reduce((sum, r) => {
      const target = r.reorderLevel * 2;
      const need = Math.max(0, target - r.currentStock);
      return sum + need * r.cost;
    }, 0);
  }, [criticalItems]);

  const todaysUsage = useMemo(
    () => rows.reduce((s, r) => s + (r.predictedUsage || 0), 0),
    [rows]
  );

  const inventoryValue = useMemo(
    () => rows.reduce((s, r) => s + (r.currentStock * r.cost || 0), 0),
    [rows]
  );

  // ----- editing -----
  const beginEdit = (id: string, current: number) => {
    setEditingId(id);
    setEditValue(current);
  };
  const cancelEdit = () => {
    setEditingId(null);
    setEditValue(0);
  };
  const saveEdit = (id: string) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, currentStock: editValue } : r)));
    setEditingId(null);
    // NOTE: if you want to persist edits, POST to an update endpoint here.
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Inventory Management</h1>
          <p className="text-slate-400">Monitor stock levels and ingredient usage predictions</p>
        </div>

        <div className="flex items-center gap-3">
          {/* Date picker (month/year dropdown) */}
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="justify-start">
                <CalendarIcon className="mr-2 h-4 w-4" />
                {format(selectedDate, "PPP")}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="p-0">
              <Calendar
                mode="single"
                selected={selectedDate}
                onSelect={(d) => d && setSelectedDate(d)}
                initialFocus
                captionLayout="dropdown"
                fromYear={2010}
                toYear={new Date().getFullYear() + 2}
                pagedNavigation
              />
            </PopoverContent>
          </Popover>

          <Button
            className="bg-gradient-primary text-white shadow-glow"
            onClick={() => fetchInventory(selectedDate)}
          >
            <Package className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error */}
      {err && (
        <Card className="border-red-500/40 bg-red-500/10">
          <CardContent className="py-3 text-red-200 text-sm">{err}</CardContent>
        </Card>
      )}

      {/* Alert Summary */}
      {criticalItems.length > 0 && (
        <Card className="bg-gradient-to-r from-red-500/10 via-yellow-500/10 to-yellow-500/10 border-yellow-500/30">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <AlertTriangle className="w-8 h-8 text-yellow-400" />
                <div>
                  <h3 className="text-lg font-semibold text-white">Reorder Alert</h3>
                  <p className="text-slate-300">
                    {criticalItems.length} items need attention for {format(selectedDate, "PPP")}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-slate-400">Est. Reorder Cost</p>
                <p className="text-2xl font-bold text-white">${totalReorderCost.toFixed(2)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Total Items</p>
                <p className="text-2xl font-bold text-white">{rows.length}</p>
              </div>
              <Package className="w-8 h-8 text-primary" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Low / Critical</p>
                <p className="text-2xl font-bold text-yellow-400">{criticalItems.length}</p>
              </div>
              <AlertTriangle className="w-8 h-8 text-yellow-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Today’s Usage (pred.)</p>
                <p className="text-2xl font-bold text-white">{Math.round(todaysUsage)}</p>
                <p className="text-xs text-slate-500">units</p>
              </div>
              <TrendingDown className="w-8 h-8 text-green-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-card border-white/10">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Inventory Value</p>
                <p className="text-2xl font-bold text-white">${inventoryValue.toFixed(2)}</p>
              </div>
              <Package className="w-8 h-8 text-green-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Inventory Table */}
      <Card className="bg-gradient-card border-white/10 shadow-elegant">
        <CardHeader>
          <CardTitle className="text-white">Current Inventory</CardTitle>
          <CardDescription className="text-slate-400">
            {format(selectedDate, "PPP")} · usage prediction and stock levels
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-white/10">
                <TableHead className="text-slate-300">Ingredient</TableHead>
                <TableHead className="text-slate-300">Unit</TableHead>
                <TableHead className="text-slate-300">Current Stock</TableHead>
                <TableHead className="text-slate-300">Predicted Usage</TableHead>
                <TableHead className="text-slate-300">Remaining</TableHead>
                <TableHead className="text-slate-300">Status</TableHead>
                <TableHead className="text-slate-300">Unit Cost</TableHead>
                <TableHead className="text-slate-300">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((item) => {
                const s = getStatus(item.currentStock, item.predictedUsage, item.reorderLevel);
                const style = statusStyles[s.key];

                return (
                  <TableRow key={item.id} className="border-white/10 hover:bg-white/5">
                    <TableCell className="text-white font-medium">{item.ingredient}</TableCell>
                    <TableCell className="text-slate-300">{item.unit}</TableCell>

                    <TableCell>
                      {editingId === item.id ? (
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            value={editValue}
                            onChange={(e) => setEditValue(Number(e.target.value))}
                            className="w-24 bg-white/10 border-white/20 text-white"
                          />
                          <Button size="sm" onClick={() => saveEdit(item.id)} className="h-8 w-8 p-0 bg-green-600">
                            <Save className="w-4 h-4" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={cancelEdit} className="h-8 w-8 p-0 border-white/20">
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      ) : (
                        <span className="text-white font-bold">{item.currentStock}</span>
                      )}
                    </TableCell>

                    <TableCell className="text-slate-300">{item.predictedUsage}</TableCell>
                    <TableCell className={cn("font-medium", style.text)}>{s.remaining}</TableCell>

                    <TableCell>
                      <Badge variant="outline" className={cn("px-2", style.badge)}>
                        {s.label}
                      </Badge>
                    </TableCell>

                    <TableCell className="text-slate-300">${item.cost.toFixed(2)}</TableCell>

                    <TableCell>
                      {editingId !== item.id && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => beginEdit(item.id, item.currentStock)}
                          className="bg-white/5 border-white/20 text-white hover:bg-white/10"
                        >
                          <Edit3 className="w-4 h-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
              {!loading && rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-slate-400 py-8">
                    No inventory rows for this date.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {loading && <div className="text-xs text-slate-400 mt-2">Loading…</div>}
        </CardContent>
      </Card>

      {/* Tomorrow block kept but now uses real predictedUsage */}
      <Card className="bg-gradient-card border-white/10 shadow-elegant">
        <CardHeader>
          <CardTitle className="text-white">Tomorrow's Usage Forecast</CardTitle>
          <CardDescription className="text-slate-400">
            Based on predicted usage +10% uplift
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {rows.slice(0, 6).map((item) => {
              const willUse = Math.round((item.predictedUsage || 0) * 1.1);
              const remaining = item.currentStock - willUse;
              const style =
                remaining < 0
                  ? "text-red-400"
                  : remaining < Math.max(5, item.reorderLevel) ? "text-yellow-400" : "text-green-400";
              return (
                <div key={item.id} className="p-4 bg-white/5 rounded-lg">
                  <h4 className="font-medium text-white mb-2">{item.ingredient}</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Current:</span>
                      <span className="text-white">
                        {item.currentStock} {item.unit}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Will use:</span>
                      <span className="text-yellow-400">-{willUse} {item.unit}</span>
                    </div>
                    <div className="flex justify-between font-medium">
                      <span className="text-slate-400">Remaining:</span>
                      <span className={style}>
                        {remaining} {item.unit}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
