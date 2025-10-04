import { Outlet, NavLink } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChefHat, BarChart3, Package, Calendar, TrendingUp } from "lucide-react";

const Layout = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-primary rounded-lg flex items-center justify-center shadow-glow">
                <ChefHat className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Kitchen Oracle</h1>
                <p className="text-sm text-slate-400">Sales & Inventory Intelligence</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-white/10 bg-black/10 backdrop-blur-sm">
        <div className="container mx-auto px-4">
          <div className="flex items-center gap-6 h-14">
            <NavLink 
              to="/" 
              className={({ isActive }) => 
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  isActive 
                    ? 'bg-primary text-primary-foreground shadow-glow' 
                    : 'text-slate-300 hover:text-white hover:bg-white/10'
                }`
              }
            >
              <TrendingUp className="w-4 h-4" />
              Prediction Dashboard
            </NavLink>
            
            <NavLink 
              to="/sales-data" 
              className={({ isActive }) => 
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  isActive 
                    ? 'bg-primary text-primary-foreground shadow-glow' 
                    : 'text-slate-300 hover:text-white hover:bg-white/10'
                }`
              }
            >
              <BarChart3 className="w-4 h-4" />
              Sales Data
            </NavLink>
            
            <NavLink 
              to="/inventory" 
              className={({ isActive }) => 
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  isActive 
                    ? 'bg-primary text-primary-foreground shadow-glow' 
                    : 'text-slate-300 hover:text-white hover:bg-white/10'
                }`
              }
            >
              <Package className="w-4 h-4" />
              Inventory
            </NavLink>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;