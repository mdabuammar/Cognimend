import { Link } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";

export default function SuccessPage() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        <CheckCircle2 className="w-14 h-14 text-emerald-400 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">You're all set!</h2>
        <p className="text-slate-400 mb-6">Your action was completed successfully.</p>
        <Link to="/dashboard" className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-colors">
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
