import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldAlert, ArrowLeft, Lock, Globe } from "lucide-react";
import { motion } from "framer-motion";

export default function ForbiddenPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center px-4 relative overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full max-w-4xl max-h-[600px] bg-rose-500/10 blur-[150px] -z-10 rounded-full" />
      
      <div className="w-full max-w-lg text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-slate-900/40 backdrop-blur-2xl border border-rose-500/20 rounded-[40px] p-12 shadow-2xl shadow-rose-500/10"
        >
          <div className="w-20 h-20 rounded-3xl bg-rose-500/10 flex items-center justify-center mx-auto mb-8 border border-rose-500/20">
            <Lock className="w-10 h-10 text-rose-500" />
          </div>

          <h1 className="text-4xl font-black text-white tracking-tight mb-4">Access Denied</h1>
          <p className="text-slate-400 text-lg leading-relaxed mb-10">
            You don't have the required administrative clearance to access this portal. 
            All unauthorized access attempts are logged for security auditing.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={() => navigate(-1)}
              className="flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-white/[0.03] border border-white/[0.08] text-white font-bold hover:bg-white/[0.06] transition-all"
            >
              <ArrowLeft className="w-5 h-5" /> Go Back
            </button>
            <Link
              to="/dashboard"
              className="flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-indigo-600 text-white font-bold hover:bg-indigo-500 shadow-xl shadow-indigo-600/20 transition-all"
            >
              <Globe className="w-5 h-5" /> Return Home
            </Link>
          </div>
        </motion.div>

        <div className="mt-12 flex items-center justify-center gap-3 text-rose-500/60 font-mono text-xs uppercase tracking-[0.2em]">
          <ShieldAlert className="w-4 h-4" />
          <span>Security Protocol 403-E Active</span>
        </div>
      </div>
    </div>
  );
}
