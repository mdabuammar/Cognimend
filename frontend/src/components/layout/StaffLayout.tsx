import React, { useState } from "react";
import { Link, useLocation, useNavigate, Outlet } from "react-router-dom";
import { 
  LayoutDashboard, 
  Users, 
  Ticket, 
  FileSearch, 
  Activity, 
  ShieldAlert, 
  CreditCard, 
  Settings,
  Bell,
  LogOut,
  Brain,
  ChevronLeft,
  Search,
  LifeBuoy,
  MessageSquareWarning,
  Menu,
  X,
  UserCircle
} from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

const STAFF_NAV = [
  { path: "/staff", label: "Operations Overview", icon: LayoutDashboard },
  { path: "/staff/customers", label: "Customers", icon: Users },
  { path: "/staff/support-tickets", label: "Support Tickets", icon: Ticket },
  { path: "/staff/reports", label: "Reports", icon: FileSearch },
  { path: "/staff/usage-review", label: "Usage Review", icon: Activity },
  { path: "/staff/billing-support", label: "Billing Support", icon: CreditCard },
  { path: "/staff/security-review", label: "Security Review", icon: ShieldAlert },
  { path: "/staff/system-incidents", label: "Incidents", icon: MessageSquareWarning },
  { path: "/staff/settings", label: "Settings", icon: Settings },
];

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const sidebar = (
    <div className="flex flex-col h-full bg-[#030c1a] border-r border-amber-500/10">
      <div className={cn("flex items-center gap-3 px-4 py-5 border-b border-white/[0.06]", collapsed && "justify-center px-3")}>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
          <LifeBuoy className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div>
            <div className="text-base font-bold text-white">Staff Portal</div>
            <div className="text-[10px] text-amber-500/80 font-semibold uppercase tracking-wider">Internal Ops</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {STAFF_NAV.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                active
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
              )}
            >
              <Icon className={cn("w-4.5 h-4.5 flex-shrink-0", active ? "text-amber-500" : "text-slate-500")} />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-white/[0.06]">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center justify-center h-8 w-full text-slate-500 hover:text-white transition-colors"
        >
          <ChevronLeft className={cn("w-4 h-4 transition-transform", collapsed && "rotate-180")} />
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#020817] flex">
      <aside className={cn("hidden lg:block flex-shrink-0 transition-all duration-300", collapsed ? "w-16" : "w-64")}>
        {sidebar}
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-16 border-b border-white/[0.06] bg-[#020817]/80 backdrop-blur-md flex items-center justify-between px-4 lg:px-8 sticky top-0 z-30">
          <div className="flex items-center gap-4">
            <button onClick={() => setMobileOpen(true)} className="lg:hidden p-2 text-slate-400">
              <Menu className="w-5 h-5" />
            </button>
            <div className="hidden md:flex items-center gap-2 text-xs font-medium px-2 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <ShieldAlert className="w-3 h-3" />
              Staff Role: {user?.staff_role?.replace('_', ' ').toUpperCase() || 'Support Agent'}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input 
                type="text" 
                placeholder="Search customers..." 
                className="pl-10 pr-4 py-1.5 bg-white/[0.03] border border-white/[0.08] rounded-lg text-sm text-white focus:outline-none focus:border-amber-500/50 w-64"
              />
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-3 p-1.5 rounded-xl hover:bg-white/[0.04] transition-all">
                  <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center text-white font-bold text-xs shadow-lg shadow-amber-500/20">
                    {(user?.full_name || "S").charAt(0).toUpperCase()}
                  </div>
                  <div className="hidden sm:block text-left">
                    <div className="text-sm font-medium text-white">{user?.full_name}</div>
                    <div className="text-[10px] text-slate-500">{user?.email}</div>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-[#0d121f] border-white/[0.08] text-slate-300">
                <DropdownMenuLabel className="text-slate-400 font-normal text-xs uppercase tracking-wider">Staff Account</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => navigate("/staff/settings")} className="focus:bg-white/[0.05] focus:text-white py-2">
                  <Settings className="w-4 h-4 mr-2" /> Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-white/[0.06]" />
                <DropdownMenuItem onClick={() => navigate("/dashboard")} className="focus:bg-white/[0.05] focus:text-white py-2">
                  <UserCircle className="w-4 h-4 mr-2" /> Back to App
                </DropdownMenuItem>
                <DropdownMenuItem onClick={logout} className="focus:bg-rose-500/10 focus:text-rose-400 py-2 text-rose-400">
                  <LogOut className="w-4 h-4 mr-2" /> Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
