import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Brain, Eye, EyeOff, Loader2, AlertCircle, Chrome, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";

const AUTH_BASE = import.meta.env.VITE_AUTH_URL ?? "http://localhost:8000";

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm]   = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const pwStrong = password.length >= 8;
  const pwMatch  = password === confirm;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!pwMatch) { setError("Passwords do not match."); return; }
    if (!pwStrong) { setError("Password must be at least 8 characters."); return; }
    setLoading(true);
    try {
      const { isNewUser } = await signup(fullName, email, password);
      navigate(isNewUser ? "/onboarding" : "/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sign up failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = () => {
    window.location.href = `${AUTH_BASE}/auth/google/start`;
  };

  return (
    <div className="min-h-screen bg-[#020817] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center justify-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white">Cognimend</span>
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-8"
        >
          <h1 className="text-2xl font-bold text-white mb-1">Create your account</h1>
          <p className="text-slate-400 text-sm mb-7">Free to start. No credit card required.</p>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm mb-5">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleGoogle}
            className="w-full flex items-center justify-center gap-3 py-3 rounded-xl bg-white text-gray-700 font-semibold text-sm hover:bg-gray-50 transition-colors mb-5 shadow-sm"
          >
            <Chrome className="w-4 h-4" />
            Sign up with Google
          </button>

          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-white/[0.08]" />
            <span className="text-xs text-slate-500">or continue with email</span>
            <div className="flex-1 h-px bg-white/[0.08]" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Full name</label>
              <input
                id="signup-name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                placeholder="Jane Smith"
                className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500/50 transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Email</label>
              <input
                id="signup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500/50 transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Password</label>
              <div className="relative">
                <input
                  id="signup-password"
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="At least 8 characters"
                  className="w-full px-4 py-3 pr-11 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500/50 transition-all"
                />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {password && (
                <div className={`flex items-center gap-1 mt-1.5 text-xs ${pwStrong ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="w-3 h-3" />
                  {pwStrong ? "Strong enough" : "At least 8 characters"}
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Confirm password</label>
              <input
                id="signup-confirm"
                type={showPw ? "text" : "password"}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                placeholder="Repeat password"
                className={`w-full px-4 py-3 rounded-xl bg-white/[0.04] border text-white placeholder-slate-500 text-sm focus:outline-none transition-all ${confirm && !pwMatch ? "border-rose-500/50" : "border-white/[0.08] focus:border-indigo-500/50"}`}
              />
              {confirm && !pwMatch && (
                <p className="text-xs text-rose-400 mt-1">Passwords do not match</p>
              )}
            </div>

            <button
              id="signup-submit"
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
            >
              {loading ? <><Loader2 className="w-4 h-4 animate-spin" />Creating account…</> : "Create account"}
            </button>
          </form>

          <p className="text-center text-xs text-slate-500 mt-4 leading-relaxed">
            By signing up you agree to our{" "}
            <a href="#" className="underline hover:text-slate-300">Terms</a>{" "}
            and{" "}
            <a href="#" className="underline hover:text-slate-300">Privacy Policy</a>.
          </p>

          <p className="text-center text-sm text-slate-400 mt-5">
            Already have an account?{" "}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
