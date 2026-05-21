import { motion } from "framer-motion";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { PageHeader, StatCard, EmptyState } from "@/components/ui/cognimend";
import { BarChart3, TrendingUp, Clock, ThumbsUp } from "lucide-react";
import { useDashboardStats, useTrends } from "@/lib/hooks/useApi";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444"];

const MOCK_TREND = [
  { day: "May 3", queries: 8, confidence: 74 },
  { day: "May 4", queries: 15, confidence: 78 },
  { day: "May 5", queries: 22, confidence: 80 },
  { day: "May 6", queries: 18, confidence: 83 },
  { day: "May 7", queries: 31, confidence: 85 },
  { day: "May 8", queries: 27, confidence: 84 },
  { day: "May 9", queries: 35, confidence: 88 },
];

const MOCK_FEEDBACK = [
  { name: "Helpful", value: 68 },
  { name: "Not helpful", value: 22 },
  { name: "No feedback", value: 10 },
];

const TooltipStyle = ({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) => {
  if (active && payload?.length) {
    return (
      <div className="bg-[#0d1829] border border-white/[0.08] rounded-xl p-3 text-xs shadow-2xl">
        <p className="text-slate-400 mb-1.5">{label}</p>
        {payload.map((p) => (
          <p key={p.name} className="text-white font-medium">
            {p.name}: {p.value}{p.name === "confidence" ? "%" : ""}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function AnalyticsPage() {
  const statsQuery = useDashboardStats();
  const stats = statsQuery.data;

  const totalQueries = stats?.total_queries ?? 158;
  const avgConf = stats?.avg_confidence ? Math.round(stats.avg_confidence) : 84;
  const avgLatency = stats?.avg_latency_ms ? Math.round(stats.avg_latency_ms) : 420;

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Query volume, confidence trends, and quality metrics" />

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Queries" value={totalQueries} icon={BarChart3} accent="indigo" delay={0} />
        <StatCard label="Avg. Confidence" value={`${avgConf}%`} icon={TrendingUp} accent="emerald" delay={0.05} trend={{ value: 4 }} />
        <StatCard label="Avg. Latency" value={`${avgLatency}ms`} icon={Clock} accent="amber" delay={0.1} />
        <StatCard label="Helpful Rate" value="76%" icon={ThumbsUp} accent="violet" delay={0.15} trend={{ value: 2 }} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Query Volume */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <h3 className="text-sm font-semibold text-white mb-1">Query Volume</h3>
          <p className="text-xs text-slate-500 mb-5">Questions asked per day</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={MOCK_TREND}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipStyle />} />
              <Bar dataKey="queries" fill="#6366f1" radius={[4, 4, 0, 0]} name="queries" />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Confidence Trend */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <h3 className="text-sm font-semibold text-white mb-1">Answer Confidence</h3>
          <p className="text-xs text-slate-500 mb-5">Average confidence score over time</p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={MOCK_TREND}>
              <defs>
                <linearGradient id="confGrad2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis domain={[60, 100]} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipStyle />} />
              <Area type="monotone" dataKey="confidence" stroke="#10b981" strokeWidth={2} fill="url(#confGrad2)" name="confidence" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Feedback Breakdown */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <h3 className="text-sm font-semibold text-white mb-1">Feedback</h3>
          <p className="text-xs text-slate-500 mb-5">User rating distribution</p>
          <div className="flex justify-center mb-4">
            <PieChart width={140} height={140}>
              <Pie data={MOCK_FEEDBACK} cx={65} cy={65} innerRadius={45} outerRadius={65} dataKey="value" strokeWidth={0}>
                {MOCK_FEEDBACK.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
              </Pie>
            </PieChart>
          </div>
          <div className="space-y-2">
            {MOCK_FEEDBACK.map((f, i) => (
              <div key={f.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i] }} />
                  <span className="text-slate-400">{f.name}</span>
                </div>
                <span className="text-white font-medium">{f.value}%</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Top Questions */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="lg:col-span-2 p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <h3 className="text-sm font-semibold text-white mb-1">Most Asked Topics</h3>
          <p className="text-xs text-slate-500 mb-5">Frequently queried subjects</p>
          <div className="space-y-3">
            {[
              { topic: "Refund and return policies", count: 24, pct: 85 },
              { topic: "Product specifications", count: 19, pct: 68 },
              { topic: "Shipping timelines", count: 15, pct: 54 },
              { topic: "Account and billing", count: 12, pct: 43 },
              { topic: "Technical troubleshooting", count: 9, pct: 32 },
            ].map((item) => (
              <div key={item.topic}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-300 truncate">{item.topic}</span>
                  <span className="text-slate-500 ml-2">{item.count}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.06]">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${item.pct}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="h-full rounded-full bg-indigo-500"
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
