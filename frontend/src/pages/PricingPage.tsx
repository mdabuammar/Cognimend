import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Brain, CheckCircle2, ArrowRight, X } from "lucide-react";

const PLANS = [
  {
    name: "Free",
    monthly: 0,
    yearly: 0,
    description: "Try Cognimend risk-free",
    cta: "Start free",
    ctaTo: "/signup",
    features: ["3 documents", "50 questions/month", "Source citations", "Personal workspace"],
    notIncluded: ["Chat history", "Analytics", "Team features", "API access"],
  },
  {
    name: "Personal",
    monthly: 12,
    yearly: 10,
    description: "For individuals and researchers",
    cta: "Start Personal",
    ctaTo: "/signup",
    popular: true,
    features: ["100 documents", "2,000 questions/month", "Full source citations", "Chat history", "Export answers", "Google Drive (coming)"],
    notIncluded: ["Team features", "API access", "Drift detection"],
  },
  {
    name: "Team",
    monthly: 49,
    yearly: 39,
    description: "For growing teams",
    cta: "Start Team",
    ctaTo: "/signup",
    features: ["1,000 documents", "20,000 questions/month", "Team workspace", "Analytics dashboard", "Feedback tracking", "5 team members"],
    notIncluded: ["API access", "Drift detection"],
  },
  {
    name: "Business",
    monthly: 149,
    yearly: 119,
    description: "Advanced features for power users",
    cta: "Start Business",
    ctaTo: "/signup",
    features: ["10,000 documents", "100,000 questions/month", "Drift detection & auto-healing", "API access", "Advanced analytics", "20 team members", "Audit logs"],
    notIncluded: [],
  },
  {
    name: "Enterprise",
    monthly: null,
    yearly: null,
    description: "Custom for large organizations",
    cta: "Contact sales",
    ctaTo: "/signup",
    features: ["Unlimited documents", "Custom query limits", "Private deployment", "SSO-ready", "Audit logs", "Custom connectors", "Dedicated support"],
    notIncluded: [],
  },
];

const FAQS = [
  { q: "What counts as a document?", a: "Each uploaded PDF, DOCX, or TXT file counts as one document. Connector-imported files also count toward your limit." },
  { q: "Can I change my plan anytime?", a: "Yes. You can upgrade or downgrade your plan at any time. Upgrades take effect immediately." },
  { q: "Is the free plan really free?", a: "Yes, completely free — no credit card required. The Free plan gives you 3 documents and 50 questions per month." },
  { q: "What is drift detection?", a: "Drift detection monitors your AI assistant's quality over time and automatically fixes issues when answer quality drops." },
  { q: "Does Google login give you Drive access?", a: "No. Google login is only for authentication. Drive access requires a separate connector permission you explicitly approve." },
];

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
          <Link to="/login" className="text-sm text-slate-400 hover:text-white transition-colors">Login</Link>
          <Link to="/signup" className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors">
            Start free
          </Link>
        </div>
      </div>
    </nav>
  );
}

export default function PricingPage() {
  const [billing, setBilling] = useState<"monthly" | "yearly">("monthly");

  return (
    <div className="min-h-screen bg-[#020817]">
      <Navbar />

      <div className="pt-28 pb-20 px-4">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="text-center mb-12">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-4"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              Transparent pricing
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-4xl lg:text-6xl font-black text-white mb-4"
            >
              Simple, honest pricing
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-slate-400 text-lg max-w-xl mx-auto mb-8"
            >
              Start free. Upgrade when you need more. No hidden fees.
            </motion.p>

            {/* Toggle */}
            <div className="inline-flex items-center gap-1 p-1 rounded-xl bg-white/[0.04] border border-white/[0.06]">
              <button
                onClick={() => setBilling("monthly")}
                className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${billing === "monthly" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"}`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBilling("yearly")}
                className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${billing === "yearly" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"}`}
              >
                Yearly <span className="text-emerald-400 text-xs ml-1">Save 20%</span>
              </button>
            </div>
          </div>

          {/* Plan Cards */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-20">
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`relative p-5 rounded-2xl border flex flex-col ${
                  plan.popular
                    ? "border-indigo-500/40 bg-gradient-to-b from-indigo-500/10 to-transparent"
                    : "border-white/[0.06] bg-white/[0.02]"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-indigo-600 text-white text-xs font-bold">
                    Most popular
                  </div>
                )}
                <div className="mb-5">
                  <h3 className="text-base font-bold text-white mb-1">{plan.name}</h3>
                  <p className="text-xs text-slate-400 mb-3">{plan.description}</p>
                  {plan.monthly !== null ? (
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-black text-white">
                        ${billing === "yearly" ? plan.yearly : plan.monthly}
                      </span>
                      <span className="text-slate-400 text-xs">/mo</span>
                    </div>
                  ) : (
                    <div className="text-2xl font-black text-white">Custom</div>
                  )}
                </div>

                <ul className="space-y-2 flex-1 mb-5">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-slate-300">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                  {plan.notIncluded.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-slate-600">
                      <X className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                </ul>

                <Link
                  to={plan.ctaTo}
                  className={`w-full py-2.5 rounded-xl text-sm font-semibold text-center transition-colors flex items-center justify-center gap-1.5 ${
                    plan.popular
                      ? "bg-indigo-600 hover:bg-indigo-500 text-white"
                      : plan.monthly === 0
                      ? "bg-white/[0.06] hover:bg-white/[0.10] text-white"
                      : "bg-white/[0.05] hover:bg-white/[0.08] text-white border border-white/[0.08]"
                  }`}
                >
                  {plan.cta} <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </motion.div>
            ))}
          </div>

          {/* FAQ */}
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-black text-white text-center mb-8">Frequently asked questions</h2>
            <div className="space-y-3">
              {FAQS.map((faq, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07 }}
                  className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
                >
                  <h4 className="text-sm font-semibold text-white mb-2">{faq.q}</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">{faq.a}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
