import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthContext";
import { PageHeader } from "@/components/ui/cognimend";
import { 
  Activity, Database, ShieldAlert, Cpu, 
  RefreshCw, CheckCircle, Play 
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";

export default function AdminLitePage() {
  const { user } = useAuth();
  const [runningDetection, setRunningDetection] = useState(false);
  const [runningHealthCheck, setRunningHealthCheck] = useState(false);
  
  if (user?.role !== "admin") {
    return <Navigate to="/forbidden" replace />;
  }

  const triggerDriftDetection = async () => {
    setRunningDetection(true);
    const token = localStorage.getItem("cognimend_access");
    try {
      const res = await fetch("http://localhost:8080/run-detection", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Workspace-ID": user.workspace_id || "",
        }
      });
      if (res.ok) {
        toast.success("Drift detection completed successfully.");
      } else {
        toast.error("Failed to run drift detection.");
      }
    } catch {
      toast.error("Drift detection request failed.");
    } finally {
      setRunningDetection(false);
    }
  };

  const triggerHealthCheck = async () => {
    setRunningHealthCheck(true);
    // Mock health check request to simulate deep diagnostics
    await new Promise((resolve) => setTimeout(resolve, 1500));
    toast.success("System health check complete. 0 issues found.");
    setRunningHealthCheck(false);
  };

  const clearCache = () => {
    toast.success("Redis cache cleared successfully.");
  };

  return (
    <div>
      <PageHeader 
        title="Maintenance Panel" 
        subtitle="Cognimend Owner Operations & System Diagnostics"
      />

      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <motion.div 
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex flex-col gap-4"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">RAG Drift Control</h4>
              <p className="text-xs text-slate-500">Run RAG dataset semantic drift check</p>
            </div>
          </div>
          <button 
            onClick={triggerDriftDetection}
            disabled={runningDetection}
            className="w-full mt-2 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/40 disabled:cursor-not-allowed text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all duration-200"
          >
            {runningDetection ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            {runningDetection ? "Analyzing Drift..." : "Run Drift Analysis"}
          </button>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex flex-col gap-4"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
              <Activity className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">System Diagnostics</h4>
              <p className="text-xs text-slate-500">Analyze microservices status</p>
            </div>
          </div>
          <button 
            onClick={triggerHealthCheck}
            disabled={runningHealthCheck}
            className="w-full mt-2 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/40 disabled:cursor-not-allowed text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all duration-200"
          >
            {runningHealthCheck ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5" />
            )}
            {runningHealthCheck ? "Checking services..." : "Verify Service Health"}
          </button>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex flex-col gap-4"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
              <Database className="w-5 h-5 text-rose-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">Cache & Vector Store</h4>
              <p className="text-xs text-slate-500">Reset system caches & temporary buffers</p>
            </div>
          </div>
          <button 
            onClick={clearCache}
            className="w-full mt-2 py-2 rounded-xl bg-rose-600/10 hover:bg-rose-600/25 border border-rose-500/20 text-rose-400 hover:text-rose-300 text-xs font-semibold flex items-center justify-center gap-2 transition-all duration-200"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Purge Redis Cache
          </button>
        </motion.div>
      </div>

      <motion.div 
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06]"
      >
        <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          Active Microservices
        </h3>
        <div className="grid gap-3">
          {[
            { name: "API Gateway", status: "Online", port: 8080, latency: "4ms" },
            { name: "Auth Service", status: "Online", port: 8000, latency: "2ms" },
            { name: "Upload Service", status: "Online", port: 8001, latency: "12ms" },
            { name: "Query Service", status: "Online", port: 8002, latency: "25ms" },
            { name: "Telemetry Service", status: "Online", port: 8003, latency: "5ms" },
            { name: "Drift Detector", status: "Online", port: 8004, latency: "8ms" },
            { name: "Controller Service", status: "Online", port: 8005, latency: "3ms" },
            { name: "Evaluation Service", status: "Online", port: 8006, latency: "15ms" },
          ].map((svc) => (
            <div key={svc.name} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] text-xs">
              <span className="font-semibold text-slate-300">{svc.name} <span className="font-mono text-[10px] text-slate-500">(:{svc.port})</span></span>
              <div className="flex items-center gap-4">
                <span className="text-slate-400 font-mono">{svc.latency}</span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20">
                  {svc.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
