import { useState } from "react";
import { motion } from "framer-motion";
import { CreditCard, Zap, CheckCircle2, ArrowRight } from "lucide-react";
import { PageHeader, UsageBar, PlanBadge } from "@/components/ui/cognimend";

const PLANS = [
  {
    name: "Free",
    price: "$0",
    features: ["3 documents", "50 questions/month", "Basic source citations", "Personal workspace"],
  },
  {
    name: "Personal",
    price: "$12",
    popular: true,
    features: ["100 documents", "2,000 questions/month", "Full source citations", "Chat history", "Export answers"],
  },
  {
    name: "Team",
    price: "$49",
    features: ["1,000 documents", "20,000 questions/month", "Team workspace", "Analytics", "Feedback tracking"],
  },
  {
    name: "Business",
    price: "$149",
    features: ["10,000 documents", "100,000 questions/month", "Drift detection", "API access", "Advanced analytics"],
  },
];

export default function BillingPage() {
  const [billing, setBilling] = useState<"monthly" | "yearly">("monthly");

  const currentUsage = {
    queries: { used: 38, limit: 50 },
    documents: { used: 2, limit: 3 },
    storage: { used: 12, limit: 50, unit: " MB" },
  };

  return (
    <div>
      <PageHeader title="Billing" subtitle="Manage your plan, usage, and billing information" />

      {/* Current Plan */}
      <div className="grid lg:grid-cols-2 gap-6 mb-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-6 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-semibold text-white">Current Plan</h3>
            <PlanBadge plan="Free" />
          </div>
          <div className="space-y-4">
            <UsageBar label="Questions this month" used={currentUsage.queries.used} limit={currentUsage.queries.limit} />
            <UsageBar label="Documents" used={currentUsage.documents.used} limit={currentUsage.documents.limit} />
            <UsageBar label="Storage" used={currentUsage.storage.used} limit={currentUsage.storage.limit} unit={currentUsage.storage.unit} />
          </div>
          <div className="mt-5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <p className="text-xs text-amber-400">
              You've used 76% of your monthly questions. Upgrade to avoid interruptions.
            </p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="p-6 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
        >
          <h3 className="text-sm font-semibold text-white mb-5">Billing Details</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Current plan</span>
              <span className="text-white font-medium">Free</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Billing cycle</span>
              <span className="text-white font-medium">—</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Next billing</span>
              <span className="text-white font-medium">—</span>
            </div>
          </div>
          <div className="mt-5 pt-5 border-t border-white/[0.06] flex items-center gap-3">
            <CreditCard className="w-4 h-4 text-slate-400" />
            <span className="text-sm text-slate-400">No payment method on file</span>
          </div>
        </motion.div>
      </div>

      {/* Upgrade Plans */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-white">Upgrade your plan</h3>
          <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.04] border border-white/[0.06]">
            <button
              onClick={() => setBilling("monthly")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${billing === "monthly" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBilling("yearly")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${billing === "yearly" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"}`}
            >
              Yearly <span className="text-emerald-400">−20%</span>
            </button>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {PLANS.map((plan, i) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
              className={`relative p-5 rounded-2xl border transition-all ${
                plan.popular
                  ? "border-indigo-500/40 bg-indigo-500/5"
                  : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.10]"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-indigo-600 text-white text-xs font-semibold">
                  Most popular
                </div>
              )}
              <div className="mb-4">
                <h4 className="text-sm font-bold text-white mb-1">{plan.name}</h4>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-black text-white">
                    {billing === "yearly" && plan.price !== "$0"
                      ? `$${Math.round(parseInt(plan.price.slice(1)) * 0.8)}`
                      : plan.price}
                  </span>
                  {plan.price !== "$0" && <span className="text-slate-400 text-xs">/mo</span>}
                </div>
              </div>
              <ul className="space-y-2 mb-5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-xs text-slate-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
                  plan.name === "Free"
                    ? "bg-white/[0.05] text-slate-400 cursor-default"
                    : plan.popular
                    ? "bg-indigo-600 hover:bg-indigo-500 text-white"
                    : "bg-white/[0.05] hover:bg-white/[0.08] text-white border border-white/[0.08]"
                }`}
                disabled={plan.name === "Free"}
              >
                {plan.name === "Free" ? "Current plan" : <>Upgrade <ArrowRight className="w-3 h-3" /></>}
              </button>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Billing History */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]"
      >
        <h3 className="text-sm font-semibold text-white mb-4">Billing History</h3>
        <div className="text-center py-8 text-slate-500 text-sm">
          No billing history yet — upgrade to a paid plan to see invoices here.
        </div>
      </motion.div>
    </div>
  );
}
