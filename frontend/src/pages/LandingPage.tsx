import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Brain, FileText, Quote, BarChart3, HeartPulse, Shield, Cloud,
  ArrowRight, CheckCircle2, Menu, X, Users, Zap, Star,
} from "lucide-react";

// ─── Navbar ───────────────────────────────────────────────────────────────────
function Navbar() {
  const [open, setOpen] = useState(false);
  return (
    <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/[0.06] bg-[#020817]/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold text-white">Cognimend</span>
        </Link>
        <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
          <Link to="/features" className="hover:text-white transition-colors">Features</Link>
          <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
          <a href="#security" className="hover:text-white transition-colors">Security</a>
          <Link to="/login" className="hover:text-white transition-colors">Login</Link>
        </div>
        <div className="hidden md:flex items-center gap-3">
          <Link to="/signup" className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors">
            Start free
          </Link>
        </div>
        <button onClick={() => setOpen(!open)} className="md:hidden p-2 text-slate-400">
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>
      {open && (
        <div className="md:hidden border-t border-white/[0.06] bg-[#020817] px-4 py-4 space-y-3">
          {[["Features", "/features"], ["Pricing", "/pricing"], ["Login", "/login"]].map(([l, h]) => (
            <Link key={l} to={h} className="block text-slate-300 text-sm py-1">{l}</Link>
          ))}
          <Link to="/signup" className="block text-center px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold">Start free</Link>
        </div>
      )}
    </nav>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="relative pt-32 pb-24 px-4 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-indigo-500/5 blur-3xl" />
        <div className="absolute top-1/4 right-1/4 w-64 h-64 rounded-full bg-violet-500/5 blur-3xl" />
      </div>
      <div className="max-w-5xl mx-auto text-center relative">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-6">
          <Zap className="w-3 h-3" /> Autonomous RAG platform — now in early access
        </motion.div>
        <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="text-5xl lg:text-7xl font-black text-white leading-[1.05] tracking-tight mb-6">
          Turn documents into a{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">
            reliable AI assistant
          </span>
        </motion.h1>
        <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Upload documents, ask questions, get source-based answers, and monitor quality — all in one platform built for students, researchers, and teams.
        </motion.p>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
          <Link to="/signup"
            className="flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-bold text-base hover:opacity-90 transition-opacity shadow-2xl shadow-indigo-500/20">
            Start free <ArrowRight className="w-5 h-5" />
          </Link>
          <Link to="/features"
            className="flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-white/[0.05] border border-white/[0.10] text-white font-semibold text-base hover:bg-white/[0.08] transition-colors">
            See how it works
          </Link>
        </motion.div>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
          className="text-sm text-slate-500">
          No credit card required · Source-based answers · Free to start
        </motion.p>
      </div>

      {/* Product preview card */}
      <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.7 }}
        className="max-w-4xl mx-auto mt-16 relative">
        <div className="rounded-3xl bg-white/[0.03] border border-white/[0.08] overflow-hidden shadow-2xl shadow-black/40">
          <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/[0.06] bg-white/[0.02]">
            {["bg-rose-500", "bg-amber-500", "bg-emerald-500"].map((c) => (
              <div key={c} className={`w-2.5 h-2.5 rounded-full ${c}`} />
            ))}
            <span className="text-xs text-slate-500 ml-2">Cognimend · AI Knowledge Assistant</span>
          </div>
          <div className="p-6 grid sm:grid-cols-3 gap-4">
            {/* Chat preview */}
            <div className="sm:col-span-2 space-y-3">
              <div className="flex justify-end">
                <div className="px-4 py-2.5 rounded-2xl rounded-tr-sm bg-indigo-600 text-white text-xs max-w-[80%]">
                  What is the refund policy mentioned in the document?
                </div>
              </div>
              <div className="flex gap-2">
                <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Brain className="w-3 h-3 text-white" />
                </div>
                <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white/[0.05] border border-white/[0.06] text-xs text-slate-200 max-w-[85%] leading-relaxed">
                  According to your documents, the refund period is <strong>30 days</strong> after purchase. Full refunds are available for unused products.
                  <div className="mt-2 flex gap-1">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Confidence: 94%</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">2 sources</span>
                  </div>
                </div>
              </div>
            </div>
            {/* Sources panel */}
            <div className="space-y-2">
              <p className="text-xs text-slate-400 font-medium mb-2">Sources</p>
              {[{ title: "Refund Policy.pdf", page: "Page 2", pct: 94 }, { title: "Customer SOP.docx", page: "Section 4", pct: 87 }].map((s) => (
                <div key={s.title} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                  <p className="text-[10px] font-medium text-white truncate">{s.title}</p>
                  <p className="text-[10px] text-slate-500">{s.page} · {s.pct}% match</p>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500/20 to-violet-500/20 rounded-3xl blur-xl -z-10" />
      </motion.div>
    </section>
  );
}

// ─── Use Cases ────────────────────────────────────────────────────────────────
const USE_CASES = [
  { icon: "🎓", title: "Students", text: "Search lecture notes and research papers instantly." },
  { icon: "🔬", title: "Researchers", text: "Extract insights from hundreds of papers with citations." },
  { icon: "💼", title: "Freelancers", text: "Organize client documents and find answers fast." },
  { icon: "📚", title: "Teachers", text: "Build a searchable knowledge base from course materials." },
  { icon: "🏢", title: "Small Businesses", text: "Instant answers from SOPs, contracts, and policies." },
  { icon: "👥", title: "Teams", text: "Shared workspace with analytics and quality monitoring." },
  { icon: "⚖️", title: "Legal & Finance", text: "Search contracts and compliance docs with source proof." },
  { icon: "🏭", title: "Enterprise", text: "Private deployment, audit logs, and SSO-ready." },
];

// ─── Features ─────────────────────────────────────────────────────────────────
const FEATURES = [
  { icon: FileText, title: "Document Q&A", text: "Ask questions from PDFs, DOCX, and TXT. Every answer cites its source.", accent: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
  { icon: Quote, title: "Source Citations", text: "Every answer shows exactly where it came from — document, page, section.", accent: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  { icon: BarChart3, title: "Quality Monitoring", text: "Track confidence, latency, and feedback. Know when your AI is performing.", accent: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  { icon: HeartPulse, title: "RAG Health Score", text: "A 0–100 score tells you how reliable your knowledge assistant is.", accent: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
  { icon: Cloud, title: "Connected Sources", text: "Bring in files from Google Drive, Notion, and more — you choose what.", accent: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" },
  { icon: Shield, title: "Private Workspaces", text: "Your data is isolated. No cross-user leakage. Ever.", accent: "text-rose-400 bg-rose-500/10 border-rose-500/20" },
];

// ─── Pricing Preview ──────────────────────────────────────────────────────────
const PLANS = [
  { name: "Free", price: "$0", features: ["3 documents", "50 questions/month", "Citations"], cta: "Start free", to: "/signup", highlight: false },
  { name: "Personal", price: "$12/mo", features: ["100 documents", "2,000 questions/month", "Chat history", "Export"], cta: "Start Personal", to: "/signup", highlight: true },
  { name: "Team", price: "$49/mo", features: ["1,000 documents", "Team workspace", "Analytics", "Feedback"], cta: "Start Team", to: "/signup", highlight: false },
  { name: "Business", price: "$149/mo", features: ["10,000 documents", "Drift detection", "API access", "Audit logs"], cta: "Start Business", to: "/signup", highlight: false },
];

// ─── Main Export ──────────────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#020817] text-white">
      <Navbar />
      <Hero />

      {/* Use Cases */}
      <section className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl lg:text-4xl font-black text-white mb-3">Built for everyone who works with documents</h2>
            <p className="text-slate-400">Students, researchers, teams, and enterprises — all in one platform.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {USE_CASES.map((uc, i) => (
              <motion.div key={uc.title} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ delay: i * 0.06 }}
                className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.10] hover:bg-white/[0.05] transition-all">
                <div className="text-3xl mb-3">{uc.icon}</div>
                <h3 className="font-bold text-white mb-1.5">{uc.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{uc.text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-4 bg-white/[0.01] border-y border-white/[0.04]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl lg:text-4xl font-black text-white mb-3">Everything you need, nothing you don't</h2>
            <p className="text-slate-400">Powerful features that stay out of your way.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f, i) => {
              const Icon = f.icon;
              return (
                <motion.div key={f.title} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }} transition={{ delay: i * 0.07 }}
                  className="p-6 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.10] transition-all group">
                  <div className={`w-10 h-10 rounded-xl border flex items-center justify-center mb-4 ${f.accent}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="font-bold text-white mb-2">{f.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{f.text}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Source Trust */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl lg:text-4xl font-black text-white mb-4">AI answers you can actually verify</h2>
          <p className="text-slate-400 mb-12">Every answer shows the exact source — so you always know if you can trust it.</p>
          <div className="p-6 rounded-3xl bg-white/[0.03] border border-white/[0.08] text-left max-w-xl mx-auto">
            <p className="text-sm text-slate-300 mb-3 font-medium">Question: What is the refund period?</p>
            <div className="p-4 rounded-xl bg-white/[0.04] border border-white/[0.06] mb-3">
              <p className="text-sm text-white leading-relaxed">The refund period is <strong>30 days</strong> from the date of purchase, as stated in the company policy.</p>
              <span className="inline-flex items-center gap-1 mt-2 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Confidence: 94%
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-2">Sources:</p>
            {[["Refund Policy.pdf", "Page 2"], ["Support SOP.docx", "Section 4"]].map(([t, p]) => (
              <div key={t} className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.03] border border-white/[0.04] mb-1.5">
                <FileText className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                <span className="text-xs text-slate-300">{t}</span>
                <span className="text-xs text-slate-500 ml-auto">{p}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-4 bg-white/[0.01] border-y border-white/[0.04]" id="pricing">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl lg:text-4xl font-black text-white mb-3">Simple, transparent pricing</h2>
            <p className="text-slate-400">Start free. Upgrade when you need more.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {PLANS.map((plan, i) => (
              <motion.div key={plan.name} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ delay: i * 0.07 }}
                className={`p-6 rounded-2xl border flex flex-col ${plan.highlight ? "border-indigo-500/40 bg-indigo-500/5" : "border-white/[0.06] bg-white/[0.02]"}`}>
                {plan.highlight && <div className="text-xs text-indigo-400 font-bold mb-2">Most popular</div>}
                <h3 className="font-bold text-white mb-1">{plan.name}</h3>
                <div className="text-2xl font-black text-white mb-4">{plan.price}</div>
                <ul className="space-y-2 flex-1 mb-5">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-xs text-slate-300">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />{f}
                    </li>
                  ))}
                </ul>
                <Link to={plan.to}
                  className={`py-2.5 rounded-xl text-xs font-bold text-center transition-colors ${plan.highlight ? "bg-indigo-600 hover:bg-indigo-500 text-white" : "bg-white/[0.06] hover:bg-white/[0.10] text-white"}`}>
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </div>
          <div className="text-center">
            <Link to="/pricing" className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
              View full feature comparison →
            </Link>
          </div>
        </div>
      </section>

      {/* Security */}
      <section className="py-20 px-4" id="security">
        <div className="max-w-4xl mx-auto text-center">
          <Shield className="w-10 h-10 text-indigo-400 mx-auto mb-4" />
          <h2 className="text-3xl font-black text-white mb-4">Built with privacy and security</h2>
          <p className="text-slate-400 mb-10">Your documents stay private. Your workspaces are fully isolated.</p>
          <div className="grid sm:grid-cols-3 gap-4">
            {[
              { title: "Workspace isolation", text: "No data leaks between users or workspaces. Ever." },
              { title: "Secure authentication", text: "JWT tokens, bcrypt passwords, Google OAuth — all secure." },
              { title: "You control connectors", text: "Google login ≠ Drive access. You approve each permission." },
            ].map((s) => (
              <div key={s.title} className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
                <h4 className="font-semibold text-white mb-1.5">{s.title}</h4>
                <p className="text-sm text-slate-400">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <motion.h2 initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
            className="text-4xl lg:text-5xl font-black text-white mb-5 leading-tight">
            Start building your reliable AI knowledge assistant today.
          </motion.h2>
          <p className="text-slate-400 mb-10">Free to start. No credit card. Source-based answers from day one.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/signup"
              className="flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-bold text-base hover:opacity-90 transition-opacity shadow-2xl shadow-indigo-500/20">
              Start free <ArrowRight className="w-5 h-5" />
            </Link>
            <Link to="/login"
              className="flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-white/[0.05] border border-white/[0.10] text-white font-semibold hover:bg-white/[0.08] transition-colors">
              Login
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] px-4 py-10">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Brain className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-white">Cognimend</span>
          </div>
          <div className="flex items-center gap-8 text-sm text-slate-400">
            <Link to="/features" className="hover:text-white transition-colors">Features</Link>
            <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
            <a href="#security" className="hover:text-white transition-colors">Security</a>
          </div>
          <p className="text-sm text-slate-500">© 2026 Cognimend. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
