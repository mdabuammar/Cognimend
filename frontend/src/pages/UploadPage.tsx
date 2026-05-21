import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, FileText, Trash2, RotateCcw, Search, Filter,
  CheckCircle2, AlertTriangle, Clock, ChevronDown,
} from "lucide-react";
import { toast } from "sonner";
import { useDocuments, useUploadDocument, useDeleteDocument } from "@/lib/hooks/useApi";
import { DocumentStatusBadge, EmptyState, LoadingSkeleton, PageHeader } from "@/components/ui/cognimend";

const ALLOWED = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"];
const ALLOWED_EXT = [".pdf", ".docx", ".txt", ".md"];

function UploadDropzone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(
      (f) => ALLOWED.includes(f.type) || ALLOWED_EXT.some((ext) => f.name.endsWith(ext))
    );
    if (files.length) onFiles(files);
  }, [onFiles]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`relative border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-300 cursor-pointer ${
        dragging
          ? "border-indigo-400 bg-indigo-500/10"
          : "border-white/[0.10] hover:border-indigo-500/40 hover:bg-white/[0.02]"
      }`}
      onClick={() => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".pdf,.docx,.txt,.md";
        input.multiple = true;
        input.onchange = (e) => {
          const files = Array.from((e.target as HTMLInputElement).files ?? []);
          if (files.length) onFiles(files);
        };
        input.click();
      }}
    >
      <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-colors ${dragging ? "bg-indigo-500/20 border border-indigo-500/30" : "bg-white/[0.04] border border-white/[0.08]"}`}>
        <Upload className={`w-6 h-6 ${dragging ? "text-indigo-400" : "text-slate-400"}`} />
      </div>
      <p className="text-base font-semibold text-white mb-1">
        {dragging ? "Release to upload" : "Drop files here or click to browse"}
      </p>
      <p className="text-sm text-slate-500">
        Supports PDF, DOCX, TXT, and Markdown • Max 50MB per file
      </p>
      <div className="flex items-center justify-center gap-2 mt-4">
        {[".pdf", ".docx", ".txt", ".md"].map((ext) => (
          <span key={ext} className="text-xs px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-slate-400">
            {ext}
          </span>
        ))}
      </div>
    </div>
  );
}

type UploadingFile = { file: File; title: string; progress: number; done: boolean; error?: string };

export default function UploadPage() {
  const navigate = useNavigate();
  const { data: docs = [], isLoading } = useDocuments();
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();
  const [uploading, setUploading] = useState<UploadingFile[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all");

  const handleFiles = async (files: File[]) => {
    const newUploads: UploadingFile[] = files.map((f) => ({
      file: f,
      title: f.name.replace(/\.[^.]+$/, ""),
      progress: 0,
      done: false,
    }));
    setUploading((prev) => [...prev, ...newUploads]);

    for (const item of newUploads) {
      try {
        // Simulate progress
        for (let p = 10; p <= 70; p += 20) {
          await new Promise((r) => setTimeout(r, 200));
          setUploading((prev) =>
            prev.map((u) => u.file === item.file ? { ...u, progress: p } : u)
          );
        }
        await uploadMutation.mutateAsync({ file: item.file, title: item.title });
        setUploading((prev) =>
          prev.map((u) => u.file === item.file ? { ...u, progress: 100, done: true } : u)
        );
        toast.success(`${item.file.name} uploaded. We are preparing it now.`);
      } catch {
        setUploading((prev) =>
          prev.map((u) => u.file === item.file ? { ...u, error: "Upload failed. Please try again." } : u)
        );
        toast.error(`Failed to upload ${item.file.name}`);
      }
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    await deleteMutation.mutateAsync(id);
    toast.success("Document deleted");
  };

  const filtered = docs.filter((d: { title?: string; filename?: string; status?: string }) => {
    const matchSearch = !search || (d.title ?? d.filename ?? "").toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === "all" || d.status === filter;
    return matchSearch && matchFilter;
  });

  const statuses = ["all", "ready", "processing", "failed"];

  return (
    <div>
      <PageHeader
        title="Documents"
        subtitle="Upload and manage your knowledge sources"
        action={
          <button
            onClick={() => navigate("/chat")}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white text-sm font-medium hover:bg-white/[0.08] transition-colors"
          >
            Ask a question →
          </button>
        }
      />

      {/* Upload Zone */}
      <UploadDropzone onFiles={handleFiles} />

      {/* Upload Progress */}
      <AnimatePresence>
        {uploading.filter((u) => !u.done || u.error).length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 space-y-2"
          >
            {uploading.map((u, i) => !u.done && (
              <div key={i} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-white truncate">{u.file.name}</span>
                  <span className="text-xs text-slate-400">{u.progress}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <motion.div
                    className="h-full bg-indigo-500 rounded-full"
                    animate={{ width: `${u.progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
                {u.error && <p className="text-xs text-rose-400 mt-1">{u.error}</p>}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mt-6 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents..."
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-slate-500 text-sm focus:outline-none focus:border-indigo-500/60 transition-colors"
          />
        </div>
        <div className="relative">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="appearance-none pl-4 pr-8 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm focus:outline-none focus:border-indigo-500/60 transition-colors cursor-pointer"
          >
            {statuses.map((s) => (
              <option key={s} value={s} className="bg-[#0d1829]">
                {s === "all" ? "All status" : s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Document List */}
      {isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No documents yet"
          message="Upload your first PDF, DOCX, or TXT file to start asking questions."
          action={{ label: "Upload document", onClick: () => document.querySelector<HTMLDivElement>(".border-dashed")?.click() }}
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((doc: { document_id?: number; id?: number; title?: string; filename?: string; status?: string; chunks?: number; version?: number }, i: number) => {
            const id = doc.document_id ?? doc.id;
            const name = doc.title ?? doc.filename ?? "Untitled";
            const status = doc.status ?? "processing";
            return (
              <motion.div
                key={id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center gap-4 p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.10] hover:bg-white/[0.04] transition-all group"
              >
                {/* Icon */}
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-indigo-400" />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{name}</p>
                  <p className="text-xs text-slate-500">
                    {doc.chunks ?? 0} chunks{doc.version ? ` • v${doc.version}` : ""}
                  </p>
                </div>

                {/* Status */}
                <DocumentStatusBadge status={status} />

                {/* Status Icon */}
                {status === "ready" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                ) : status === "failed" ? (
                  <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                ) : (
                  <Clock className="w-4 h-4 text-amber-400 flex-shrink-0 animate-pulse" />
                )}

                {/* Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {status === "failed" && (
                    <button
                      title="Retry"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => id && handleDelete(id as number, name)}
                    title="Delete"
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
