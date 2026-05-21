import React, { useState } from "react";
import { Link, useLocation, useNavigate, useParams, Outlet } from "react-router-dom";
import { 
  Building2, 
  Users, 
  UserPlus, 
  Network, 
  FileText, 
  ShieldCheck, 
  Activity, 
  History, 
  Key, 
  CreditCard, 
  Settings,
  ChevronLeft,
  Search,
  ArrowLeft,
  Lock,
  Globe,
  MoreVertical,
  LogOut,
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

export default function WorkspaceAdminLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { id: workspaceId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const workspace = user?.workspaces.find(w => w.id === workspaceId) || user?.workspaces[0];
  const baseUrl = `/workspaces/${workspace?.id}/admin`;

  const ADMIN_NAV = [
    { path: `${baseUrl}`, label: "Overview", icon: Building2 },
    { path: `${baseUrl}/users`, label: "Users", icon: Users },
    { path: `${baseUrl}/invitations`, label: "Invitations", icon: UserPlus },
    { path: `${baseUrl}/departments`, label: "Departments", icon: Network },
    { path: `${baseUrl}/documents`, label: "Documents", icon: FileText },
    { path: `${baseUrl}/access-control`, label: "Access Control", icon: ShieldCheck },
    { path: `${baseUrl}/usage`, label: "Usage", icon: Activity },
    { path: `${baseUrl}/audit-logs`, label: "Audit Logs", icon: History },
    { path: `${baseUrl}/security`, label: "Security", icon: Lock },
    { path: `${baseUrl}/api-keys`, label: "API Keys", icon: Key },
    { path: `${baseUrl}/billing`, label: "Billing", icon: CreditCard },
    { path: `${baseUrl}/settings`, label: "Settings", icon: Settings },
  ];

  const sidebar = (
    <div className="flex flex-col h-full bg-[#030c1a] border-r border-indigo-500/10">
      <div className={cn("px-4 py-5 border-b border-white/[0.06]", collapsed && "flex justify-center")}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/20">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-bold text-white truncate">Admin Console</div>
              <div className="text-[10px] text-slate-500 truncate">{workspace?.name || "Workspace"}</div>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {ADMIN_NAV.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                active
                  ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                  : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
              )}
            >
              <Icon className={cn("w-4.5 h-4.5 flex-shrink-0", active ? "text-indigo-400" : "text-slate-500")} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </div>

      <div className="p-3 border-t border-white/[0.06]">
        <button
          onClick={() => navigate(`/workspaces/${workspace?.id}`)}
          className={cn(
            "flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-white/[0.05] transition-all",
            collapsed && "justify-center"
          )}
        >
          <ArrowLeft className="w-4.5 h-4.5 flex-shrink-0" />
          {!collapsed && <span>Exit Admin</span>}
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
            <div className="flex items-center gap-2 text-xs font-semibold px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Globe className="w-3.5 h-3.5" />
              {workspace?.role?.toUpperCase()} ACCESS
            </div>
          </div>

          <div className="flex items-center gap-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-3 p-1.5 rounded-xl hover:bg-white/[0.04] transition-all">
                  <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow-lg shadow-indigo-600/20">
                    {(user?.full_name || "A").charAt(0).toUpperCase()}
                  </div>
                  <div className="hidden sm:block text-left">
                    <div className="text-sm font-medium text-white">{user?.full_name}</div>
                    <div className="text-[10px] text-slate-500">{user?.email}</div>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-[#0d121f] border-white/[0.08] text-slate-300">
                <DropdownMenuLabel className="text-slate-400 font-normal text-xs uppercase tracking-wider">Account Settings</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => navigate("/account")} className="focus:bg-white/[0.05] focus:text-white py-2">
                  <UserCircle className="w-4 h-4 mr-2" /> Profile
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-white/[0.06]" />
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
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
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
