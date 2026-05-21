import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthContext";
import { Brain, Loader2 } from "lucide-react";

/**
 * Handles the redirect from Google OAuth.
 * The AuthContext already reads ?access_token & ?refresh_token on mount,
 * so we just wait for auth to settle then redirect.
 */
export default function AuthCallbackPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading) {
      navigate(isAuthenticated ? "/dashboard" : "/login", { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  return (
    <div className="min-h-screen bg-[#020817] flex flex-col items-center justify-center gap-4">
      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg">
        <Brain className="w-6 h-6 text-white" />
      </div>
      <div className="flex items-center gap-2 text-slate-300 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        Signing you in…
      </div>
    </div>
  );
}
