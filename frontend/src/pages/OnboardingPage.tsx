import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Brain, Upload, MessageSquare, FileText, CheckCircle2, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";

const STEPS = [
  { icon: FileText,       title: "Your workspace is ready",       desc: "A personal workspace was created for you." },
  { icon: Upload,         title: "Upload your first document",    desc: "PDF, DOCX, or TXT — up to 10 MB on the free plan." },
  { icon: MessageSquare,  title: "Ask your first question",       desc: "Ask anything from your uploaded documents." },
  { icon: CheckCircle2,   title: "See sources in every answer",   desc: "Every answer shows exactly where it came from." },
];

export default function OnboardingPage() {
  const { user } = useAuth();
  const navigate  = useNavigate();
  const [step, setStep] = useState(0);

  const isLast = step === STEPS.length - 1;
  const S = STEPS[step];
  const Icon = S.icon;

  return (
    <div className="min-h-screen bg-[#020817] flex flex-col items-center justify-center px-4">
      {/* Progress dots */}
      <div className="flex gap-2 mb-10">
        {STEPS.map((_, i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full transition-all ${i === step ? "w-8 bg-indigo-500" : i < step ? "w-4 bg-indigo-500/40" : "w-4 bg-white/10"}`}
          />
        ))}
      </div>

      <motion.div
        key={step}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="max-w-md w-full text-center"
      >
        {/* Logo on first step */}
        {step === 0 && (
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-indigo-500/20">
            <Brain className="w-8 h-8 text-white" />
          </div>
        )}

        {step > 0 && (
          <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6">
            <Icon className="w-7 h-7 text-indigo-400" />
          </div>
        )}

        {step === 0 && (
          <p className="text-indigo-400 font-medium text-sm mb-2">
            Welcome, {user?.full_name?.split(" ")[0] ?? "there"}! 🎉
          </p>
        )}

        <h1 className="text-2xl lg:text-3xl font-black text-white mb-3">{S.title}</h1>
        <p className="text-slate-400 leading-relaxed mb-10">{S.desc}</p>

        <div className="flex flex-col gap-3">
          <button
            onClick={() => isLast ? navigate("/dashboard") : setStep(step + 1)}
            className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors"
          >
            {isLast ? "Go to dashboard" : "Next"}
            <ArrowRight className="w-4 h-4" />
          </button>

          {!isLast && (
            <button onClick={() => navigate("/dashboard")} className="text-sm text-slate-500 hover:text-slate-300 transition-colors py-2">
              Skip intro
            </button>
          )}
        </div>
      </motion.div>
    </div>
  );
}
