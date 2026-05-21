import { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Save } from "lucide-react";
import { PageHeader } from "@/components/ui/cognimend";
import { toast } from "sonner";

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
      <div className="mb-5">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const [workspace, setWorkspace] = useState({ name: "My Workspace", sourceCount: 5, preset: "balanced", autoRemediate: true });
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    await new Promise((r) => setTimeout(r, 800));
    setSaving(false);
    toast.success("Settings saved");
  };

  return (
    <div>
      <PageHeader title="Settings" subtitle="Configure your workspace preferences" />

      <div className="space-y-4 max-w-2xl">
        <Section title="Workspace" description="General workspace configuration">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Workspace Name</label>
              <input
                value={workspace.name}
                onChange={(e) => setWorkspace({ ...workspace, name: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none focus:border-indigo-500/60 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Number of Sources Used</label>
              <p className="text-xs text-slate-500 mb-2">How many document chunks to use when answering questions</p>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={workspace.sourceCount}
                  onChange={(e) => setWorkspace({ ...workspace, sourceCount: parseInt(e.target.value) })}
                  className="flex-1 accent-indigo-500"
                />
                <span className="text-white font-bold w-6 text-center">{workspace.sourceCount}</span>
              </div>
            </div>
          </div>
        </Section>

        <Section title="AI Model" description="Configure which AI model handles your questions">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Quality Preset</label>
            <select
              value={workspace.preset}
              onChange={(e) => setWorkspace({ ...workspace, preset: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none"
            >
              <option value="free" className="bg-[#0d1829]">Free — Llama 3.3 (fastest, no cost)</option>
              <option value="cheap" className="bg-[#0d1829]">Budget — Llama 3.3 70B (good quality)</option>
              <option value="balanced" className="bg-[#0d1829]">Balanced — Claude Haiku (recommended)</option>
              <option value="quality" className="bg-[#0d1829]">Quality — GPT-4o (high accuracy)</option>
              <option value="best" className="bg-[#0d1829]">Best — Claude 3.5 Sonnet (premium)</option>
            </select>
            <p className="text-xs text-slate-500 mt-2">Higher quality = better answers, higher API cost.</p>
          </div>
        </Section>

        <Section title="Auto-Remediation" description="Let Cognimend automatically fix quality issues">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">Enable auto-remediation</p>
              <p className="text-xs text-slate-400 mt-0.5">Automatically adjust settings when answer quality drops</p>
            </div>
            <button
              onClick={() => setWorkspace({ ...workspace, autoRemediate: !workspace.autoRemediate })}
              className={`relative w-11 h-6 rounded-full transition-colors ${workspace.autoRemediate ? "bg-indigo-600" : "bg-white/[0.10]"}`}
            >
              <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${workspace.autoRemediate ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
        </Section>

        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-sm font-semibold transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving..." : "Save settings"}
        </button>

        {/* Danger Zone */}
        <div className="p-5 rounded-2xl border border-rose-500/20 bg-rose-500/5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <h3 className="text-sm font-semibold text-rose-400">Danger Zone</h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Deleting your workspace will permanently remove all documents, queries, and history. This cannot be undone.
          </p>
          <button className="px-4 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 text-sm font-medium transition-colors">
            Delete workspace
          </button>
        </div>
      </div>
    </div>
  );
}
