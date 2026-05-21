import { useState } from "react";
import { motion } from "framer-motion";
import { Cloud, HardDrive, Folder, StickyNote, Hash, Globe, ChevronRight, CheckCircle2, AlertTriangle, RefreshCw, Unplug, Info } from "lucide-react";
import { PageHeader, EmptyState } from "@/components/ui/cognimend";

interface Connector {
  id: string;
  name: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  border: string;
  description: string;
  comingSoon?: boolean;
  connected?: boolean;
  lastSync?: string;
  filesImported?: number;
  status?: "synced" | "syncing" | "error";
}

const CONNECTORS: Connector[] = [
  {
    id: "google-drive",
    name: "Google Drive",
    icon: Cloud,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    description: "Import documents from your Google Drive folders",
    connected: false,
    status: "synced",
    filesImported: 0,
    lastSync: undefined,
  },
  {
    id: "onedrive",
    name: "OneDrive",
    icon: HardDrive,
    color: "text-sky-400",
    bg: "bg-sky-500/10",
    border: "border-sky-500/20",
    description: "Import from Microsoft OneDrive and SharePoint",
    comingSoon: true,
  },
  {
    id: "dropbox",
    name: "Dropbox",
    icon: Folder,
    color: "text-indigo-400",
    bg: "bg-indigo-500/10",
    border: "border-indigo-500/20",
    description: "Connect your Dropbox for seamless document access",
    comingSoon: true,
  },
  {
    id: "notion",
    name: "Notion",
    icon: StickyNote,
    color: "text-slate-300",
    bg: "bg-slate-500/10",
    border: "border-slate-500/20",
    description: "Import Notion pages and databases",
    comingSoon: true,
  },
  {
    id: "slack",
    name: "Slack",
    icon: Hash,
    color: "text-violet-400",
    bg: "bg-violet-500/10",
    border: "border-violet-500/20",
    description: "Search through Slack messages and files",
    comingSoon: true,
  },
  {
    id: "website",
    name: "Website",
    icon: Globe,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    description: "Crawl and index any public website",
    comingSoon: true,
  },
];

function ConnectorCard({ connector }: { connector: Connector }) {
  const [loading, setLoading] = useState(false);
  const Icon = connector.icon;

  const handleConnect = async () => {
    if (connector.comingSoon) return;
    setLoading(true);
    // TODO: trigger OAuth flow
    await new Promise((r) => setTimeout(r, 1000));
    setLoading(false);
    alert("Google OAuth integration coming — set GOOGLE_DRIVE_CLIENT_ID in .env");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative p-5 rounded-2xl bg-white/[0.03] border transition-all duration-300 ${
        connector.comingSoon
          ? "border-white/[0.04] opacity-70"
          : connector.connected
          ? "border-emerald-500/20 hover:border-emerald-500/30"
          : "border-white/[0.06] hover:border-white/[0.10] hover:bg-white/[0.04]"
      }`}
    >
      {connector.comingSoon && (
        <span className="absolute top-3 right-3 text-xs px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-400 border border-slate-500/20">
          Coming soon
        </span>
      )}

      <div className="flex items-start gap-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center border flex-shrink-0 ${connector.bg} ${connector.border}`}>
          <Icon className={`w-5 h-5 ${connector.color}`} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white mb-1">{connector.name}</h3>
          <p className="text-xs text-slate-400 leading-relaxed">{connector.description}</p>
        </div>
      </div>

      {connector.connected ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Connected
            </div>
            <span className="text-slate-500">
              {connector.filesImported} files imported
            </span>
          </div>
          {connector.lastSync && (
            <p className="text-xs text-slate-500">Last sync: {connector.lastSync}</p>
          )}
          <div className="flex gap-2">
            <button className="flex items-center gap-1.5 flex-1 justify-center px-3 py-2 rounded-xl bg-white/[0.05] text-slate-300 text-xs hover:bg-white/[0.08] transition-colors">
              <RefreshCw className="w-3 h-3" /> Sync now
            </button>
            <button className="flex items-center gap-1.5 flex-1 justify-center px-3 py-2 rounded-xl bg-rose-500/10 text-rose-400 text-xs hover:bg-rose-500/20 transition-colors border border-rose-500/20">
              <Unplug className="w-3 h-3" /> Disconnect
            </button>
          </div>
        </div>
      ) : !connector.comingSoon ? (
        <button
          onClick={handleConnect}
          disabled={loading}
          className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs font-semibold transition-colors"
        >
          {loading ? (
            <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>Connect <ChevronRight className="w-3.5 h-3.5" /></>
          )}
        </button>
      ) : null}
    </motion.div>
  );
}

export default function SourcesPage() {
  return (
    <div>
      <PageHeader
        title="Knowledge Sources"
        subtitle="Connect external sources and Cognimend will make selected content searchable"
      />

      {/* Important notice */}
      <div className="flex items-start gap-3 p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 mb-6">
        <Info className="w-4 h-4 text-indigo-400 mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <span className="text-white font-medium">Your privacy is protected. </span>
          <span className="text-slate-400">
            Signing in with Google does not give Cognimend access to your Drive.
            You explicitly choose which files to import. You can disconnect anytime.
          </span>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {CONNECTORS.map((c) => (
          <ConnectorCard key={c.id} connector={c} />
        ))}
      </div>

      <div className="mt-8 p-5 rounded-2xl bg-white/[0.02] border border-white/[0.04] text-center">
        <p className="text-sm text-slate-400">
          Need a specific connector?{" "}
          <a href="mailto:hello@cognimend.ai" className="text-indigo-400 hover:text-indigo-300 underline">
            Let us know
          </a>{" "}
          and we'll prioritize it.
        </p>
      </div>
    </div>
  );
}
