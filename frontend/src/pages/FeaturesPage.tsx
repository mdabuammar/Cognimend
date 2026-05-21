import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Brain, FileText, Quote, Layers, Cloud, BarChart3, HeartPulse, Activity, Code, ArrowRight,
} from "lucide-react";

const FEATURES = [
  {
    icon: FileText,
    title: "Document Q&A",
    description: "Ask questions from any PDF, DOCX, or TXT file. Cognimend extracts, chunks, and indexes your documents for instant retrieval.",
    detail: "Supports PDFs with 1,000+ pages, multi-format extraction, and deduplication so you never re-process the same file.",
    accent: "indigo",
  },
  {
    icon: Quote,
    title: "Source Citations",
    description: "Every answer includes exactly where it came from — document title, section, and page number.",
    detail: "Never wonder if your AI is making things up. Every claim is grounded in your actual documents.",
    accent: "violet",
  },
  {
    icon: Layers,
    title: "Workspace Management",
    description: "Organize documents by project, class, client, or team. Keep everything private and separate.",
    detail: "Each workspace is fully isolated. No data leaks between workspaces or users.",
    accent: "cyan",
  },
  {
    icon: Cloud,
    title: "Connected Sources",
    description: "Bring documents from Google Drive, Notion, Slack, and more — with a single connection.",
    detail: "You choose exactly which files to import. Google login is separate from Drive access.",
    accent: "blue",
  },
  {
    icon: BarChart3,
    title: "Analytics",
    description: "Track query volume, confidence scores, latency, feedback, and usage over time.",
    detail: "Clean charts powered by Recharts. See what your team asks most and which documents are used most.",
    accent: "emerald",
  },
  {
    icon: HeartPulse,
    title: "RAG Health Score",
    description: "A single score (0–100) tells you how well your AI knowledge assistant is performing.",
    detail: "Combines answer confidence, cache efficiency, and drift detection into one health indicator.",
    accent: "amber",
  },
  {
    icon: Activity,
    title: "Drift Detection",
    description: "Statistical monitoring catches when your AI's quality starts to drop — before users notice.",
    detail: "Uses KS-test, Welch's T-test, and Mann-Whitney U to detect data, retrieval, and performance drift.",
    accent: "rose",
  },
  {
    icon: Code,
    title: "API Access",
    description: "Query your workspace programmatically with a workspace API key. Available on Business and Enterprise plans.",
    detail: "Full REST API with rate limiting, usage tracking, and source-based responses.",
    accent: "violet",
  },
];

const ACCENT_MAP: Record<string, { icon: string; border: string }> = {
  indigo: { icon: "text-indigo-400", border: "border-indigo-500/20" },
  violet: { icon: "text-violet-400", border: "border-violet-500/20" },
  cyan:   { icon: "text-cyan-400",   border: "border-cyan-500/20" },
  blue:   { icon: "text-blue-400",   border: "border-blue-500/20" },
  emerald:{ icon: "text-emerald-400",border: "border-emerald-500/20" },
  amber:  { icon: "text-amber-400",  border: "border-amber-500/20" },
  rose:   { icon: "text-rose-400",   border: "border-rose-500/20" },
};

function Navbar() {
  return (
    <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/[0.06] bg-[#020817]/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <Brain className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="text-base font-bold text-white">Cognimend</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/pricing" className="text-sm text-slate-400 hover:text-white">Pricing</Link>
          <Link to="/login" className="text-sm text-slate-400 hover:text-white">Login</Link>
          <Link to="/signup" className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors">
            Start free
          </Link>
        </div>
      </div>
    </nav>
  );
}

export default function FeaturesPage() {
  return (
    <div className="min-h-screen bg-[#020817]">
      <Navbar />
      <div className="pt-28 pb-20 px-4">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="text-center mb-20">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-4xl lg:text-6xl font-black text-white mb-4"
            >
              Everything you need for{" "}
              <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
                reliable AI answers
              </span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-slate-400 text-lg max-w-xl mx-auto"
            >
              Cognimend gives you every tool to turn documents into a trustworthy AI assistant.
            </motion.p>
          </div>

          {/* Features alternating layout */}
          <div className="space-y-20">
            {FEATURES.map((feature, i) => {
              const Icon = feature.icon;
              const acc = ACCENT_MAP[feature.accent] ?? ACCENT_MAP.indigo;
              const isEven = i % 2 === 0;

              return (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.1 }}
                  className={`grid lg:grid-cols-2 gap-12 items-center ${!isEven ? "lg:direction-rtl" : ""}`}
                >
                  <div className={!isEven ? "lg:order-2" : ""}>
                    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border ${acc.border} bg-white/[0.03] mb-5`}>
                      <Icon className={`w-3.5 h-3.5 ${acc.icon}`} />
                      <span className={`text-xs font-semibold ${acc.icon}`}>{feature.title}</span>
                    </div>
                    <h2 className="text-2xl lg:text-3xl font-black text-white mb-4 leading-tight">
                      {feature.description}
                    </h2>
                    <p className="text-slate-400 leading-relaxed mb-6">{feature.detail}</p>
                    <Link
                      to="/signup"
                      className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                      Try it free <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>

                  <div className={!isEven ? "lg:order-1" : ""}>
                    <div className="relative p-8 rounded-3xl bg-white/[0.03] border border-white/[0.06] overflow-hidden">
                      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-violet-500/5" />
                      <div className={`relative w-14 h-14 rounded-2xl border flex items-center justify-center ${acc.border} bg-white/[0.04]`}>
                        <Icon className={`w-7 h-7 ${acc.icon}`} />
                      </div>
                      <div className="relative mt-4 space-y-2">
                        {[...Array(3)].map((_, i) => (
                          <div key={i} className="h-2.5 rounded-full bg-white/[0.06]" style={{ width: `${80 - i * 15}%` }} />
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* CTA */}
          <div className="text-center mt-24">
            <h2 className="text-3xl font-black text-white mb-4">
              Ready to build your knowledge assistant?
            </h2>
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-bold text-base hover:opacity-90 transition-opacity shadow-xl shadow-indigo-500/20"
            >
              Start free — no credit card <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
