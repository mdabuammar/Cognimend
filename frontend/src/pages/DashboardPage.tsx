import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  FileText, MessageSquare, TrendingUp, HeartPulse,
  Upload, ArrowRight, Clock, CheckCircle2, AlertTriangle, Zap,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { StatCard, HealthScoreCard, EmptyState, LoadingSkeleton, ConfidenceBadge, PageHeader } from "@/components/ui/cognimend";
import { useDashboardStats, useDocuments, useQueryHistory, useHealthScore } from "@/lib/hooks/useApi";

// ─── Mock fallback data ───────────────────────────────────────────────────────
const MOCK_TREND = [
  { time: "Mon", queries: 12, confidence: 78 },
  { time: "Tue", queries: 19, confidence: 82 },
  { time: "Wed", queries: 15, confidence: 80 },
  { time: "Thu", queries: 25, confidence: 85 },
  { time: "Fri", queries: 22, confidence: 88 },
  { time: "Sat", queries: 8, confidence: 86 },
  { time: "Sun", queries: 11, confidence: 87 },
];

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) => {
  if (active && payload?.length) {
    return (
      <div className="bg-[#0d1829] border border-white/[0.08] rounded-xl p-3 text-xs">
        <p className="text-slate-400 mb-1">{label}</p>
        {payload.map((p) => (
          <p key={p.name} className="text-white font-medium">
            {p.name === "queries" ? `${p.value} questions` : `${p.value}% confidence`}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const statsQuery = useDashboardStats();
  const docsQuery = useDocuments();
  const historyQuery = useQueryHistory(5);
  const health = useHealthScore();

  const stats = statsQuery.data;
  const docs = docsQuery.data ?? [];
  const history = historyQuery.data ?? [];
  const isNewUser = docs.length === 0 && !docsQuery.isLoading;

  // Format display values
  const totalDocs = stats?.total_documents ?? docs.length;
  const totalQueries = stats?.total_queries ?? 0;
  const avgConf = stats?.avg_confidence ? Math.round(stats.avg_confidence) : 0;
  const avgLatency = stats?.avg_latency_ms ? `${Math.round(stats.avg_latency_ms)}ms` : "—";

  if (isNewUser) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh]">
        <EmptyState
          icon={Zap}
          title="Your knowledge assistant is ready."
          message="Upload your first document to start asking questions with source-based answers."
          action={{ label: "Upload your first document", onClick: () => navigate("/documents") }}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Your knowledge assistant at a glance"
        action={
          <button
            onClick={() => navigate("/documents")}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors"
          >
            <Upload className="w-4 h-4" /> Upload
          </button>
        }
      />

      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Total Documents"
          value={statsQuery.isLoading ? "—" : totalDocs}
          icon={FileText}
          accent="indigo"
          delay={0}
          sub="Ready to query"
        />
        <StatCard
          label="Questions This Month"
          value={statsQuery.isLoading ? "—" : totalQueries.toLocaleString()}
          icon={MessageSquare}
          accent="violet"
          delay={0.05}
          trend={{ value: 12 }}
        />
        <StatCard
          label="Avg. Confidence"
          value={statsQuery.isLoading ? "—" : `${avgConf}%`}
          icon={TrendingUp}
          accent="emerald"
          delay={0.1}
          sub="Answer accuracy"
        />
        <StatCard
          label="Avg. Response Time"
          value={statsQuery.isLoading ? "—" : avgLatency}
          icon={Clock}
          accent="cyan"
          delay={0.15}
        />
      </div>

      {/* ── Main grid ── */}
      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        {/* Query trend chart */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-2 p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-white">Query Activity</h3>
              <p className="text-xs text-slate-500 mt-0.5">Questions asked this week</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={MOCK_TREND}>
              <defs>
                <linearGradient id="queryGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="queries" stroke="#6366f1" strokeWidth={2} fill="url(#queryGrad)" name="queries" />
              <Area type="monotone" dataKey="confidence" stroke="#10b981" strokeWidth={2} fill="url(#confGrad)" name="confidence" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Health Score */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <h3 className="text-sm font-semibold text-white mb-1">RAG Health</h3>
          <p className="text-xs text-slate-500 mb-5">System quality score</p>
          <HealthScoreCard
            score={health.score}
            status={health.status}
            isLoading={health.isLoading}
          />
          <div className="mt-4 space-y-2.5">
            {[
              { label: "Answer confidence", value: health.avgConf > 0 ? `${Math.round(health.avgConf)}%` : "—", ok: health.avgConf >= 75 },
              { label: "Cache efficiency", value: health.cacheHit > 0 ? `${Math.round(health.cacheHit)}%` : "—", ok: health.cacheHit >= 60 },
              { label: "Drift detected", value: health.hasDrift ? "Yes" : "None", ok: !health.hasDrift },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between text-xs">
                <span className="text-slate-400">{item.label}</span>
                <span className={item.ok ? "text-emerald-400 font-medium" : "text-amber-400 font-medium"}>
                  {item.value}
                </span>
              </div>
            ))}
          </div>
          <button
            onClick={() => navigate("/rag-health")}
            className="w-full mt-4 text-xs text-indigo-400 hover:text-indigo-300 flex items-center justify-center gap-1 transition-colors"
          >
            View full health report <ArrowRight className="w-3 h-3" />
          </button>
        </motion.div>
      </div>

      {/* ── Bottom grid ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Recent Documents</h3>
            <button onClick={() => navigate("/documents")} className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
              View all <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {docsQuery.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : docs.length === 0 ? (
            <div className="text-center py-8 text-slate-500 text-sm">No documents yet</div>
          ) : (
            <div className="space-y-2">
              {docs.slice(0, 5).map((doc: { document_id?: number; id?: number; filename?: string; title?: string; status?: string; chunks?: number }) => (
                <div
                  key={doc.document_id ?? doc.id}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/[0.03] transition-colors group"
                >
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-4 h-4 text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{doc.title ?? doc.filename}</p>
                    <p className="text-xs text-slate-500">{doc.chunks ?? 0} chunks</p>
                  </div>
                  {doc.status === "ready" ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  ) : doc.status === "failed" ? (
                    <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                  ) : (
                    <div className="w-4 h-4 border-2 border-indigo-400/40 border-t-indigo-400 rounded-full animate-spin flex-shrink-0" />
                  )}
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Recent Chats */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Recent Questions</h3>
            <button onClick={() => navigate("/chat")} className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
              Open chat <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {historyQuery.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : history.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-slate-500 text-sm mb-3">No questions yet</p>
              <button
                onClick={() => navigate("/chat")}
                className="text-xs text-indigo-400 hover:text-indigo-300"
              >
                Ask your first question →
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {history.slice(0, 5).map((item: { id: number; question: string; confidence: number; latency_ms: number }) => (
                <div
                  key={item.id}
                  className="flex items-start gap-3 p-3 rounded-xl hover:bg-white/[0.03] transition-colors"
                >
                  <MessageSquare className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{item.question}</p>
                    <p className="text-xs text-slate-500">{item.latency_ms}ms</p>
                  </div>
                  <ConfidenceBadge score={Math.round(item.confidence * 100)} />
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
