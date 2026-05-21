import React from "react";
import { cn } from "@/lib/utils";
import { Link, useLocation, Outlet } from "react-router-dom";
import { motion } from "framer-motion";
import { LucideIcon, ArrowLeft } from "lucide-react";

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  roles?: string[];
}

interface AdminLayoutProps {
  title: string;
  subtitle: string;
  navItems: NavItem[];
  userRole?: string;
  children: React.ReactNode;
  headerActions?: React.ReactNode;
}

export function AdminLayout({
  title,
  subtitle,
  navItems,
  userRole,
  children,
  headerActions,
}: AdminLayoutProps) {
  const location = useLocation();

  const filteredNav = navItems.filter((item) => {
    if (!item.roles) return true;
    if (!userRole) return false;
    return item.roles.includes(userRole);
  });

  return (
    <div className="flex flex-col lg:flex-row min-h-[calc(100vh-3.5rem)] bg-[#020817]">
      {/* Admin Sidebar */}
      <aside className="w-full lg:w-64 border-b lg:border-b-0 lg:border-r border-white/[0.06] bg-[#030c1a]/50 backdrop-blur-sm p-4 lg:p-6 overflow-y-auto">
        <div className="mb-8 hidden lg:block">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Management</h2>
        </div>
        <nav className="flex flex-row lg:flex-col gap-1 overflow-x-auto lg:overflow-x-visible pb-2 lg:pb-0">
          {filteredNav.map((item) => {
            const Icon = item.icon;
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap",
                  active
                    ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/20"
                    : "text-slate-400 hover:text-white hover:bg-white/[0.05]"
                )}
              >
                <Icon className={cn("w-4.5 h-4.5", active ? "text-indigo-400" : "text-slate-500")} />
                <span>{item.label}</span>
              </Link>
            );
          })}

          <div className="my-4 border-t border-white/[0.06] hidden lg:block" />
          
          <Link
            to="/dashboard"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-indigo-400 hover:text-white hover:bg-indigo-500/10 transition-all duration-200 whitespace-nowrap"
          >
            <ArrowLeft className="w-4.5 h-4.5" />
            <span>Back to App</span>
          </Link>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 flex flex-col">
        {/* Sub-header */}
        <div className="px-4 lg:px-8 py-6 border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">{title}</h1>
            <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
          </div>
          {headerActions && (
            <div className="flex items-center gap-3">
              {headerActions}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4 lg:p-8 overflow-y-auto">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Outlet />
          </motion.div>
        </div>
      </main>
    </div>
  );
}
