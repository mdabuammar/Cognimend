// Shared UI components for Cognimend
// StatCard, HealthScoreCard, EmptyState, LoadingSkeleton, PlanBadge, UsageBar

import { motion } from "framer-motion";
import { LucideIcon, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── StatCard ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  trend?: { value: number; label?: string };
  accent?: "indigo" | "emerald" | "amber" | "rose" | "cyan" | "violet";
  delay?: number;
}

export function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  trend,
  accent = "indigo",
  delay = 0,
}: StatCardProps) {
  const accentMap = {
    indigo: "from-indigo-500/10 border-indigo-500/20 text-indigo-400",
    emerald: "from-emerald-500/10 border-emerald-500/20 text-emerald-400",
    amber: "from-amber-500/10 border-amber-500/20 text-amber-400",
    rose: "from-rose-500/10 border-rose-500/20 text-rose-400",
    cyan: "from-cyan-500/10 border-cyan-500/20 text-cyan-400",
    violet: "from-violet-500/10 border-violet-500/20 text-violet-400",
  };

  const trendColor =
    trend && trend.value > 0
      ? "text-emerald-400"
      : trend && trend.value < 0
      ? "text-rose-400"
      : "text-slate-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="group relative p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.12] hover:bg-white/[0.05] transition-all duration-300"
    >
      <div className="flex items-start justify-between mb-4">
        <div
          className={cn(
            "w-10 h-10 rounded-xl bg-gradient-to-br border flex items-center justify-center",
            accentMap[accent]
          )}
        >
          <Icon className="w-5 h-5" />
        </div>
        {trend !== undefined && (
          <span className={cn("text-xs font-semibold tabular-nums", trendColor)}>
            {trend.value > 0 ? "+" : ""}
            {trend.value}
            {trend.label ?? "%"}
          </span>
        )}
      </div>
      <div className="text-2xl font-bold text-white tabular-nums mb-1">{value}</div>
      <div className="text-sm text-slate-400">{label}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </motion.div>
  );
}

// ─── HealthScoreCard ──────────────────────────────────────────────────────────

interface HealthScoreCardProps {
  score: number;
  status: "healthy" | "degraded" | "critical";
  isLoading?: boolean;
}

export function HealthScoreCard({ score, status, isLoading }: HealthScoreCardProps) {
  const statusConfig = {
    healthy: {
      label: "Healthy",
      color: "text-emerald-400",
      ring: "stroke-emerald-400",
      bg: "bg-emerald-400/10",
      icon: CheckCircle2,
    },
    degraded: {
      label: "Degraded",
      color: "text-amber-400",
      ring: "stroke-amber-400",
      bg: "bg-amber-400/10",
      icon: AlertTriangle,
    },
    critical: {
      label: "Critical",
      color: "text-rose-400",
      ring: "stroke-rose-400",
      bg: "bg-rose-400/10",
      icon: XCircle,
    },
  };

  const cfg = statusConfig[status];
  const Icon = cfg.icon;
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center p-6 rounded-2xl bg-white/[0.03] border border-white/[0.06] gap-3">
      {isLoading ? (
        <div className="w-24 h-24 rounded-full bg-white/5 animate-pulse" />
      ) : (
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
            <motion.circle
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              strokeWidth="8"
              strokeLinecap="round"
              className={cfg.ring}
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1.2, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-black text-white">{score}</span>
          </div>
        </div>
      )}
      <div className="text-center">
        <div className={cn("flex items-center gap-1 font-semibold text-sm", cfg.color)}>
          <Icon className="w-3.5 h-3.5" />
          {cfg.label}
        </div>
        <div className="text-xs text-slate-500 mt-1">RAG Health Score</div>
      </div>
    </div>
  );
}

// ─── EmptyState ───────────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  message: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon: Icon, title, message, action }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center justify-center py-20 px-6 text-center"
    >
      <div className="w-16 h-16 rounded-2xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center mb-5">
        <Icon className="w-7 h-7 text-slate-400" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-slate-400 text-sm max-w-sm leading-relaxed mb-6">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors"
        >
          {action.label}
        </button>
      )}
    </motion.div>
  );
}

// ─── LoadingSkeleton ──────────────────────────────────────────────────────────

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-14 rounded-xl bg-white/[0.03] animate-pulse"
          style={{ animationDelay: `${i * 0.1}s` }}
        />
      ))}
    </div>
  );
}

// ─── PlanBadge ────────────────────────────────────────────────────────────────

type Plan = "Free" | "Personal" | "Team" | "Business" | "Enterprise";

export function PlanBadge({ plan }: { plan: Plan }) {
  const map: Record<Plan, string> = {
    Free: "bg-slate-500/20 text-slate-300 border-slate-500/30",
    Personal: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
    Team: "bg-violet-500/20 text-violet-300 border-violet-500/30",
    Business: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    Enterprise: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  };
  return (
    <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full border", map[plan])}>
      {plan}
    </span>
  );
}

// ─── UsageBar ─────────────────────────────────────────────────────────────────

interface UsageBarProps {
  label: string;
  used: number;
  limit: number;
  unit?: string;
}

export function UsageBar({ label, used, limit, unit = "" }: UsageBarProps) {
  const pct = Math.min((used / limit) * 100, 100);
  const color =
    pct >= 90 ? "bg-rose-500" : pct >= 70 ? "bg-amber-500" : "bg-indigo-500";

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1.5">
        <span className="text-slate-300">{label}</span>
        <span className="text-slate-400 tabular-nums">
          {used.toLocaleString()}{unit} / {limit.toLocaleString()}{unit}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={cn("h-full rounded-full", color)}
        />
      </div>
    </div>
  );
}

// ─── ConfidenceBadge ──────────────────────────────────────────────────────────

export function ConfidenceBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-emerald-400 bg-emerald-400/10"
      : score >= 60
      ? "text-amber-400 bg-amber-400/10"
      : "text-rose-400 bg-rose-400/10";

  return (
    <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full tabular-nums", color)}>
      {score}%
    </span>
  );
}

// ─── PageHeader ───────────────────────────────────────────────────────────────

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-8">
      <div>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {subtitle && <p className="text-slate-400 text-sm mt-1">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

// ─── DocumentStatusBadge ──────────────────────────────────────────────────────

type DocStatus = "processing" | "extracting" | "chunking" | "embedding" | "indexing" | "ready" | "failed";

const statusLabels: Record<DocStatus, string> = {
  processing: "Processing",
  extracting: "Reading file",
  chunking: "Preparing content",
  embedding: "Making searchable",
  indexing: "Finalizing",
  ready: "Ready",
  failed: "Failed",
};

const statusStyles: Record<DocStatus, string> = {
  processing: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  extracting: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  chunking: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  embedding: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
  indexing: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  failed: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

export function DocumentStatusBadge({ status }: { status: string }) {
  const s = (status as DocStatus) in statusLabels ? (status as DocStatus) : "processing";
  return (
    <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full border", statusStyles[s])}>
      {statusLabels[s]}
    </span>
  );
}
