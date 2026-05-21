import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Brain, ArrowLeft, Mail, CheckCircle2 } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setSent(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#020817] flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        <Link to="/" className="flex items-center gap-2 mb-10">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold text-white">Cognimend</span>
        </Link>

        {sent ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-5">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-black text-white mb-2">Check your email</h1>
            <p className="text-slate-400 text-sm mb-6">
              We sent a reset link to <span className="text-white font-medium">{email}</span>. Check your inbox and click the link to reset your password.
            </p>
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 text-sm font-medium flex items-center justify-center gap-1.5">
              <ArrowLeft className="w-4 h-4" /> Back to login
            </Link>
          </div>
        ) : (
          <>
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-6">
              <Mail className="w-6 h-6 text-indigo-400" />
            </div>
            <h1 className="text-2xl font-black text-white mb-1">Reset your password</h1>
            <p className="text-slate-400 text-sm mb-8">
              Enter your email and we'll send you a link to reset your password.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Email address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-slate-500 text-sm focus:outline-none focus:border-indigo-500/60 transition-colors"
                  placeholder="you@example.com"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Sending...
                  </span>
                ) : "Send reset link"}
              </button>
            </form>

            <Link to="/login" className="flex items-center justify-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors mt-6">
              <ArrowLeft className="w-4 h-4" /> Back to login
            </Link>
          </>
        )}
      </motion.div>
    </div>
  );
}
