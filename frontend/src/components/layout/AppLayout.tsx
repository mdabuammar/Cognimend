import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate, Outlet } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  BarChart3,
  HeartPulse,
  Settings,
  Bell,
  Menu,
  X,
  ChevronLeft,
  Brain,
  Upload,
  LogOut,
  User,
  CreditCard,
  Zap,
  Search,
  Plus,
  ShieldAlert,
  Lock,
} from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { PlanBadge } from "@/components/ui/cognimend";
import { NotificationBell } from "./NotificationBell";

interface AppLayoutProps {
  children: React.ReactNode;
}

const NAV_MAIN = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/documents", label: "Documents", icon: FileText },
  { path: "/chat", label: "Chat", icon: MessageSquare },
  { path: "/sources", label: "Sources", icon: Search },
  { path: "/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/rag-health", label: "RAG Health", icon: HeartPulse },
  { path: "/billing", label: "Billing", icon: CreditCard },
  { path: "/settings", label: "Settings", icon: Settings },
  { path: "/account", label: "Account", icon: User },
];

function SidebarNavItem({
  item,
  collapsed,
  active,
}: {
  item: { path: string; label: string; icon: React.ElementType };
  collapsed: boolean;
  active: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      to={item.path}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group",
        active
          ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/20"
          : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
      )}
    >
      <Icon
        className={cn(
          "w-4.5 h-4.5 flex-shrink-0",
          active ? "text-indigo-400" : "text-slate-500 group-hover:text-slate-300"
        )}
        style={{ width: "1.1rem", height: "1.1rem" }}
      />
      {!collapsed && (
        <span className="truncate">{item.label}</span>
      )}
      {active && !collapsed && (
        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400" />
      )}
    </Link>
  );
}

export function AppLayout({ children }: AppLayoutProps) {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const sidebar = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className={cn("flex items-center gap-3 px-4 py-5 border-b border-white/[0.06]", collapsed && "justify-center px-3")}>
        <div className="relative flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <div className="absolute inset-0 rounded-lg bg-indigo-400/20 blur-sm -z-10" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="text-base font-bold text-white tracking-tight">Cognimend</div>
            <div className="text-[10px] text-slate-500">AI Knowledge Platform</div>
          </div>
        )}
      </div>

      {/* Quick Upload Button */}
      {!collapsed && (
        <div className="px-3 py-3 border-b border-white/[0.06]">
          <Link
            to="/documents"
            className="flex items-center justify-center gap-2 w-full px-3 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors group"
          >
            <Plus className="w-4 h-4" />
            Upload Document
          </Link>
        </div>
      )}

      {/* Main Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {NAV_MAIN.map((item) => (
          <SidebarNavItem
            key={item.path}
            item={item}
            collapsed={collapsed}
            active={location.pathname === item.path}
          />
        ))}
      </nav>

      {/* User / Plan */}
      {!collapsed && (
        <div className="px-3 pb-4 border-t border-white/[0.06] pt-3">
          <div className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/[0.04] transition-colors cursor-pointer group">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-bold text-white">
                {(user?.full_name || "U").charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">{user?.full_name || "User"}</div>
              <PlanBadge plan="Personal" />
            </div>
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="hidden lg:flex items-center justify-center h-8 w-full border-t border-white/[0.06] text-slate-500 hover:text-white transition-colors"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <ChevronLeft className={cn("w-4 h-4 transition-transform", collapsed && "rotate-180")} />
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#020817] flex">
      {/* ── Desktop Sidebar ── */}
      <motion.aside
        animate={{ width: collapsed ? 64 : 240 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="hidden lg:flex flex-col flex-shrink-0 border-r border-white/[0.06] bg-[#030c1a] overflow-hidden"
      >
        {sidebar}
      </motion.aside>

      {/* ── Mobile Sidebar (Drawer) ── */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="lg:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="lg:hidden fixed left-0 top-0 bottom-0 w-64 bg-[#030c1a] border-r border-white/[0.06] z-50 flex flex-col"
            >
              {sidebar}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* ── Main Area ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-14 flex items-center justify-between px-4 lg:px-6 border-b border-white/[0.06] bg-[#020817]/80 backdrop-blur-xl sticky top-0 z-30">
          {/* Left */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.05] transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
            {/* Page breadcrumb derived from path */}
            <span className="text-sm text-slate-400 hidden sm:block">
              {NAV_MAIN.find((n) => n.path === location.pathname)?.label ?? "Cognimend"}
            </span>
          </div>

          {/* Right */}
          <div className="flex items-center gap-2">
            {/* Quick search placeholder */}
            <button className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-slate-400 text-sm hover:bg-white/[0.06] transition-colors">
              <Search className="w-3.5 h-3.5" />
              <span>Search...</span>
            </button>

            {/* Notifications */}
            <NotificationBell />

            {/* User menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="w-8 h-8 rounded-full p-0">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
                    <span className="text-xs font-bold text-white">
                      {(user?.full_name || "U").charAt(0).toUpperCase()}
                    </span>
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52 rounded-xl bg-[#0d1829] border-white/[0.08]">
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col">
                    <p className="text-sm font-semibold text-white">{user?.full_name || "User"}</p>
                    <p className="text-xs text-slate-400">{user?.email}</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-white/[0.06]" />
                <DropdownMenuItem onClick={() => navigate("/settings")} className="cursor-pointer text-slate-300 hover:text-white focus:text-white">
                  <User className="mr-2 h-4 w-4" />
                  Account Settings
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate("/billing")} className="cursor-pointer text-slate-300 hover:text-white focus:text-white">
                  <CreditCard className="mr-2 h-4 w-4" />
                  Billing
                </DropdownMenuItem>

                {/* ── Maintenance Panel ── */}
                {user?.role === "admin" && (
                  <>
                    <DropdownMenuSeparator className="bg-white/[0.06]" />
                    <DropdownMenuItem 
                      onClick={() => navigate("/admin-lite")} 
                      className="cursor-pointer bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 hover:text-white focus:bg-indigo-500/20"
                    >
                      <Lock className="mr-2 h-4 w-4" />
                      Maintenance Panel
                    </DropdownMenuItem>
                  </>
                )}

                <DropdownMenuSeparator className="bg-white/[0.06]" />
                <DropdownMenuItem onClick={() => navigate("/")} className="cursor-pointer text-slate-300 hover:text-white focus:text-white">
                  <Zap className="mr-2 h-4 w-4" />
                  Upgrade Plan
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-white/[0.06]" />
                <DropdownMenuItem
                  onClick={() => navigate("/login")}
                  className="cursor-pointer text-rose-400 hover:text-rose-300 focus:text-rose-300"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="p-4 lg:p-6 max-w-7xl mx-auto"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
