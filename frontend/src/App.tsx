import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Brain, Loader2 } from "lucide-react";

// ─── Context & Guards ─────────────────────────────────────────────────────────
import { AuthProvider } from "@/lib/auth/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

// ─── Layouts ──────────────────────────────────────────────────────────────────
import { AppLayout } from "@/components/layout/AppLayout";

// ─── Error Handling ───────────────────────────────────────────────────────────
import { setupGlobalErrorHandlers, setToastFunction } from "@/lib/errors";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth/AuthContext";

// ─── Public Pages ─────────────────────────────────────────────────────────────
const LandingPage      = lazy(() => import("./pages/LandingPage"));
const PricingPage      = lazy(() => import("./pages/PricingPage"));
const FeaturesPage     = lazy(() => import("./pages/FeaturesPage"));
const SecurityPage     = lazy(() => import("./pages/SecurityPage"));
const ContactPage      = lazy(() => import("./pages/ContactPage"));
const LoginPage        = lazy(() => import("./pages/LoginPage"));
const SignupPage       = lazy(() => import("./pages/SignupPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage  = lazy(() => import("./pages/ResetPasswordPage"));
const AuthCallbackPage   = lazy(() => import("./pages/AuthCallbackPage"));
const OnboardingPage     = lazy(() => import("./pages/OnboardingPage"));
const NotFound           = lazy(() => import("./pages/NotFound"));
const ForbiddenPage      = lazy(() => import("./pages/ForbiddenPage"));

// ─── Customer App Pages ───────────────────────────────────────────────────────
const DashboardPage  = lazy(() => import("./pages/DashboardPage"));
const UploadPage     = lazy(() => import("./pages/UploadPage"));
const QueryPage      = lazy(() => import("./pages/QueryPage"));
const AnalyticsPage  = lazy(() => import("./pages/AnalyticsPage"));
const RAGHealthPage  = lazy(() => import("./pages/RAGHealthPage"));
const SourcesPage    = lazy(() => import("./pages/SourcesPage"));
const SettingsPage   = lazy(() => import("./pages/SettingsPage"));
const BillingPage    = lazy(() => import("./pages/BillingPage"));
const AccountPage    = lazy(() => import("./pages/AccountPage"));
const AdminLitePage  = lazy(() => import("./pages/AdminLitePage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

setupGlobalErrorHandlers();
setToastFunction((msg, type) => {
  if (type === "error") toast.error(msg);
  else toast.success(msg);
});

const PageLoader = () => (
  <div className="min-h-screen bg-[#020817] flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
        <Brain className="w-6 h-6 text-white" />
      </div>
      <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
    </div>
  </div>
);

// Redirect component for decommissioned routes
function RemovedRouteRedirect() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return <PageLoader />;
  }
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner position="top-right" theme="dark" />
        <BrowserRouter>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* ── Public Routes ── */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/features" element={<FeaturesPage />} />
              <Route path="/security" element={<SecurityPage />} />
              <Route path="/contact" element={<ContactPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/auth/callback" element={<AuthCallbackPage />} />
              <Route path="/forbidden" element={<ForbiddenPage />} />

              {/* ── Compatibility redirects ── */}
              <Route path="/app" element={<Navigate to="/documents" replace />} />
              <Route path="/query" element={<Navigate to="/chat" replace />} />

              {/* ── Removed Portal Routes Redirects ── */}
              <Route path="/admin" element={<RemovedRouteRedirect />} />
              <Route path="/admin/*" element={<RemovedRouteRedirect />} />
              <Route path="/staff" element={<RemovedRouteRedirect />} />
              <Route path="/staff/*" element={<RemovedRouteRedirect />} />
              <Route path="/super-admin" element={<RemovedRouteRedirect />} />
              <Route path="/super-admin/*" element={<RemovedRouteRedirect />} />
              <Route path="/workspaces/:id/admin" element={<RemovedRouteRedirect />} />
              <Route path="/workspaces/:id/admin/*" element={<RemovedRouteRedirect />} />

              {/* ── Customer Portal Routes ── */}
              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/documents" element={<UploadPage />} />
                <Route path="/chat" element={<QueryPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/rag-health" element={<RAGHealthPage />} />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/billing" element={<BillingPage />} />
                <Route path="/account" element={<AccountPage />} />
                <Route path="/onboarding" element={<OnboardingPage />} />
                <Route path="/admin-lite" element={<AdminLitePage />} />
                <Route path="/maintenance" element={<AdminLitePage />} />
              </Route>

              {/* ── Fallbacks & Redirects ── */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
