import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send, Copy, ThumbsUp, ThumbsDown, FileText, ChevronRight,
  MessageSquare, Sparkles, X, ExternalLink, AlertTriangle, HelpCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useQueryDocuments, useQueryHistory, useDocuments } from "@/lib/hooks/useApi";
import { ConfidenceBadge, EmptyState, LoadingSkeleton } from "@/components/ui/cognimend";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  citations?: Citation[];
  latency?: number;
  loading?: boolean;
  faithfulness_score?: number;
  unsupported_claim_rate?: number;
  claim_support_rate?: number;
  verification_status?: string;
  verification_summary?: string;
  claim_passport_status?: "skipped" | "pending" | "available" | "failed";
  trust_status?: string;
  judge_status?: string;
  claim_verifications?: Array<{
    claim: string;
    status: "supported" | "unsupported" | "contradicted" | "uncertain";
    confidence: number;
    explanation: string;
  }>;
  // Trust Engine telemetry fields
  citation_truth_score?: number | null;
  citation_quality_label?: "strong" | "partial" | "weak" | null;
  citation_verifications?: Array<{
    citation_id: string;
    document_id: string;
    chunk_id: string;
    page_number?: number | null;
    related_claims: string[];
    support_status: "supports" | "partial" | "weak" | "irrelevant" | "contradicted";
    support_score: number;
    explanation: string;
  }>;
  conflict_detected?: boolean;
  conflict_summary?: string | null;
  conflict_sources?: Array<{
    document_id: string;
    document_title: string;
    page_number?: number | null;
    claim: string;
    uploaded_at?: string | null;
    snippet: string;
  }>;
  evidence_gap_detected?: boolean;
  freshness_warning?: string | null;
  evidence_gap_summary?: string;
  missing_information?: string[];
  suggested_actions?: string[];
  conflict_details?: Array<{
    document_id_a: number;
    document_id_b: number;
    document_title_a: string;
    document_title_b: string;
    topic: string;
    explanation: string;
  }>;
  latest_source_id?: string | null;
  trust_mode?: "fast" | "verified" | "strict";
}

interface Citation {
  document_id: number;
  title: string;
  snippet: string;
  similarity: number;
  version?: number;
  uploaded_at?: string;
  document_created_at?: string | null;
  document_updated_at?: string | null;
  source_freshness_label?: "latest" | "recent" | "older" | "unknown";
  is_latest_relevant_source?: boolean;
}

interface QueryDocument {
  document_id?: number | string;
  id?: number | string;
  title?: string;
  filename?: string;
  created_at?: string | null;
}

function UserMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-tr-sm bg-indigo-600 text-white text-sm leading-relaxed shadow-lg shadow-indigo-500/10">
        {msg.content}
      </div>
    </div>
  );
}

// ========== ANSWER TRUST BADGE COMPONENT ==========
function AnswerTrustBadge({ 
  faithfulnessScore, 
  unsupportedClaimRate,
  verificationStatus,
  content,
  citationTruthScore,
  citationQualityLabel,
  freshnessWarning,
  conflictDetected,
  evidenceGapDetected
}: { 
  faithfulnessScore?: number; 
  unsupportedClaimRate?: number;
  verificationStatus?: string;
  content: string;
  citationTruthScore?: number | null;
  citationQualityLabel?: "strong" | "partial" | "weak" | null;
  freshnessWarning?: string | null;
  conflictDetected?: boolean;
  evidenceGapDetected?: boolean;
}) {
  let label = "Verified from your documents";
  let color = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  let tooltip = "This answer is fully supported by the facts in your documents.";

  const isRefusal = 
    /i cannot/i.test(content) || 
    /i do not have/i.test(content) || 
    /i don't have/i.test(content) || 
    /not found in your documents/i.test(content) || 
    /sorry, but/i.test(content) ||
    /i'm sorry/i.test(content);

  if (isRefusal || verificationStatus === "refused" || (faithfulnessScore !== undefined && faithfulnessScore < 0.3)) {
    label = "Honest Refusal";
    color = "bg-slate-500/10 text-slate-400 border-slate-500/20";
    tooltip = "The assistant honestly refused to answer because evidence is missing.";
  } else if (unsupportedClaimRate !== undefined && unsupportedClaimRate > 0) {
    label = "Partially verified";
    color = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    tooltip = "Some claims in this answer might not be backed by cited sources.";
  } else if (faithfulnessScore !== undefined) {
    if (faithfulnessScore >= 0.8) {
      label = "Verified from your documents";
      color = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    } else if (faithfulnessScore >= 0.5) {
      label = "Partially verified";
      color = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    } else {
      label = "Low evidence match";
      color = "bg-rose-500/10 text-rose-400 border-rose-500/20";
      tooltip = "Warning: The text has low verification fidelity against your sources.";
    }
  }

  let citationTruthBadge = null;
  if (citationTruthScore !== undefined && citationTruthScore !== null) {
    const scoreVal = Math.round(citationTruthScore * 100);
    let scoreColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    if (scoreVal < 50) {
      scoreColor = "bg-rose-500/10 text-rose-400 border-rose-500/20";
    } else if (scoreVal < 80) {
      scoreColor = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    }
    const qualityLabel = citationQualityLabel === "strong" ? "Strong" : citationQualityLabel === "partial" ? "Partial" : "Weak";
    citationTruthBadge = (
      <span 
        className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full border transition-all cursor-help flex items-center gap-1", scoreColor)}
        title={`Citation Truth Score: ${scoreVal}%. Backend-computed support between the answer and cited chunks.`}
      >
        <span>🎯</span>
        <span>Citation Quality: {qualityLabel}</span>
      </span>
    );
  }

  return (
    <>
      <span 
        className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full border transition-all cursor-help flex items-center gap-1", color)}
        title={tooltip}
      >
        <span>🛡️</span>
        <span>{label}</span>
      </span>

      {citationTruthBadge}

      {conflictDetected && (
        <span 
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full border border-rose-500/20 bg-rose-500/10 text-rose-400 transition-all cursor-help flex items-center gap-1"
          title="Conflicting facts were found between different documents in your knowledge base."
        >
          <span>⚠️</span>
          <span>Conflicting Info Found</span>
        </span>
      )}

      {evidenceGapDetected && (
        <span 
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full border border-sky-500/20 bg-sky-500/10 text-sky-400 transition-all cursor-help flex items-center gap-1"
          title="Evidence gaps detected! The documents in this workspace might not contain the necessary information to fully answer this question."
        >
          <span>🔍</span>
          <span>Evidence Gap</span>
        </span>
      )}

      {freshnessWarning && (
        <span 
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full border border-yellow-500/20 bg-yellow-500/10 text-yellow-400 transition-all cursor-help flex items-center gap-1"
          title="Warning: The answer was generated using older documents when newer versions of those documents or related content exist in the workspace."
        >
          <span>🕒</span>
          <span>Outdated Sources Used</span>
        </span>
      )}
    </>
  );
}

// ========== CLAIM PASSPORT CARD COMPONENT ==========
function ClaimPassport({
  claims,
  status,
}: {
  claims?: NonNullable<Message["claim_verifications"]>;
  status?: Message["claim_passport_status"];
}) {
  const [expanded, setExpanded] = useState(false);

  if (!claims || claims.length === 0) {
    if (status === "pending") {
      return (
        <div className="mt-4 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.02] px-4 py-3 text-xs text-indigo-300">
          Claim Passport is being prepared.
        </div>
      );
    }
    if (status === "failed" || status === "skipped") {
      return (
        <div className="mt-4 rounded-xl border border-slate-500/20 bg-slate-500/[0.02] px-4 py-3 text-xs text-slate-400">
          Claim verification unavailable right now.
        </div>
      );
    }
    return null;
  }

  return (
    <div className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.01] overflow-hidden shadow-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-xs font-semibold text-slate-300 hover:text-white hover:bg-white/[0.02] transition-colors"
      >
        <span className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          Claim Passport ({claims.length} claims verified)
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
          {expanded ? "Hide Details" : "View Claims"}
        </span>
      </button>
      
      {expanded && (
        <div className="p-4 border-t border-white/[0.06] space-y-3 bg-[#020815]/50">
          {claims.map((c, i) => {
            const statusConfig = {
              supported: { label: "Found in documents", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: "🟢" },
              unsupported: { label: "Not in documents", color: "bg-rose-500/10 text-rose-400 border-rose-500/20", icon: "🔴" },
              contradicted: { label: "Conflict found", color: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: "🟡" },
              uncertain: { label: "Uncertain evidence", color: "bg-slate-500/10 text-slate-400 border-slate-500/20", icon: "⚪" }
            }[c.status] || { label: "Unverified", color: "bg-slate-500/10 text-slate-400 border-slate-500/20", icon: "⚪" };

            return (
              <div key={i} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 mb-2">
                  <p className="text-xs font-medium text-slate-200 leading-relaxed">{c.claim}</p>
                  <span className={cn("text-[9px] font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 self-start flex items-center gap-1", statusConfig.color)}>
                    <span>{statusConfig.icon}</span>
                    <span>{statusConfig.label}</span>
                  </span>
                </div>
                {c.explanation && (
                  <p className="text-[11px] text-slate-400 mb-2 leading-relaxed bg-white/[0.01] p-2 rounded border border-white/[0.02]">
                    {c.explanation}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-slate-500 flex-shrink-0">Verification confidence:</span>
                  <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div 
                      className="h-full bg-indigo-500 transition-all duration-500" 
                      style={{ width: `${c.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400 font-semibold">{Math.round(c.confidence * 100)}%</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ========== EVIDENCE GAP SUGGESTIONS ==========
function EvidenceGapPanel({ 
  gapDetected,
  gapSummary,
  missingInformation,
  suggestedActions
}: { 
  gapDetected?: boolean;
  gapSummary?: string;
  missingInformation?: string[];
  suggestedActions?: string[];
}) {
  if (gapDetected !== true) return null;

  const summary = gapSummary || "Not enough evidence was found in your documents to answer safely.";
  const missing = missingInformation && missingInformation.length > 0 ? missingInformation : [
    "A source passage that directly answers the question."
  ];
  const actions = suggestedActions && suggestedActions.length > 0 ? suggestedActions : [
    "Upload a more relevant document.",
    "Reprocess failed documents.",
    "Ask a more specific question."
  ];

  return (
    <div className="mt-4 p-4 rounded-xl border border-dashed border-indigo-500/20 bg-indigo-500/[0.02]">
      <h4 className="text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
        <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
        Not enough evidence
      </h4>
      <p className="text-xs text-slate-400 leading-relaxed mb-2.5">
        {summary}
      </p>
      <div className="space-y-1.5">
        <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Missing information:</p>
        <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
          {missing.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
        <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Suggested Actions:</p>
        <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
          {actions.map((action, i) => (
            <li key={i}>{action}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

interface AssistantMessageProps {
  msg: Message;
  onFeedback: (id: string, v: "up" | "down") => void;
  getDocMetadata: (docId: number) => {
    title: string;
    filename: string;
    created_at: string | null;
    isLatest: boolean;
  } | null;
}

function AssistantMessage({ msg, onFeedback, getDocMetadata }: AssistantMessageProps) {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Copied to clipboard");
  };

  const handleFeedback = (v: "up" | "down") => {
    setFeedback(v);
    onFeedback(msg.id, v);
    toast.success("Thanks. Your feedback helps improve answer quality.");
  };

  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-md shadow-indigo-500/10">
        <Sparkles className="w-3.5 h-3.5 text-white" />
      </div>
      <div className="flex-1 max-w-[85%] space-y-2">
        <div className="p-4 rounded-2xl rounded-tl-sm bg-white/[0.04] border border-white/[0.06] shadow-sm">
          {msg.loading ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
              Thinking...
            </div>
          ) : (
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
          )}
        </div>

        {!msg.loading && (
          <>
            {/* Answer Trust Badge & Conflict Alerts */}
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <AnswerTrustBadge 
                faithfulnessScore={msg.faithfulness_score} 
                unsupportedClaimRate={msg.unsupported_claim_rate}
                verificationStatus={msg.verification_status}
                content={msg.content}
                citationTruthScore={msg.citation_truth_score}
                citationQualityLabel={msg.citation_quality_label}
                freshnessWarning={msg.freshness_warning}
                conflictDetected={msg.conflict_detected}
                evidenceGapDetected={msg.evidence_gap_detected}
              />
              
              {msg.confidence !== undefined && (
                <ConfidenceBadge score={Math.round(msg.confidence * 100)} />
              )}
              
              {msg.latency && (
                <span className="text-[10px] text-slate-500">{msg.latency}ms</span>
              )}
            </div>

            {/* Conflict Warnings */}
            {msg.conflict_detected && (
              <div className="p-3.5 rounded-xl border border-rose-500/20 bg-rose-500/[0.02] text-xs text-rose-300 leading-relaxed space-y-2">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="font-bold text-rose-200">Conflicting information found:</span> {msg.conflict_summary || "The system detected conflicting statements across your workspace documents."}
                  </div>
                </div>
                {msg.conflict_sources && msg.conflict_sources.length > 0 ? (
                  <div className="space-y-2.5 mt-2 pl-6">
                    {msg.conflict_sources.map((source, idx) => (
                      <div key={idx} className="p-2.5 rounded bg-rose-950/20 border border-rose-500/10 space-y-1">
                        <p className="font-semibold text-rose-200 text-[10px] uppercase tracking-wider">
                          Source: {source.document_title}
                        </p>
                        <p className="text-slate-300">{source.claim}</p>
                        <p className="text-[10px] text-slate-500">
                          {source.snippet}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="pl-6 text-slate-400">
                    Two or more sources in this workspace contain contradicting claims. Please examine the cited sources.
                  </p>
                )}
              </div>
            )}

            {!msg.conflict_detected && msg.claim_verifications?.some(c => c.status === "contradicted") && (
              <div className="p-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.02] text-[11px] text-amber-300 leading-relaxed flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                <div>
                  <span className="font-semibold">Conflict Warning:</span> Your documents contain conflicting information. Please review the cited sources carefully.
                </div>
              </div>
            )}

            {/* Freshness Warnings */}
            {msg.freshness_warning && (
              <div className="p-3 rounded-xl border border-yellow-500/20 bg-yellow-500/[0.02] text-xs text-yellow-300 leading-relaxed flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                <div>
                  <span className="font-bold text-yellow-200">Freshness warning:</span> {msg.freshness_warning}
                </div>
              </div>
            )}

            {/* Claim Passport Card */}
            <ClaimPassport claims={msg.claim_verifications} status={msg.claim_passport_status} />

            {/* Evidence Gap Panel */}
            <EvidenceGapPanel 
              gapDetected={msg.evidence_gap_detected}
              gapSummary={msg.evidence_gap_summary}
              missingInformation={msg.missing_information}
              suggestedActions={msg.suggested_actions}
            />

            {/* Inline Citations & Freshness Badges */}
            {msg.citations && msg.citations.length > 0 && (
              <div className="mt-3 pt-2 border-t border-white/[0.04]">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">Cited Sources:</p>
                <div className="flex flex-wrap gap-2">
                  {msg.citations.map((c, i) => {
                    const metadata = getDocMetadata(c.document_id);
                    
                    let rating = "Weak";
                    let ratingColor = "text-rose-400 bg-rose-500/10 border-rose-500/20";
                    if (c.similarity >= 0.8) {
                      rating = "Good Match";
                      ratingColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
                    } else if (c.similarity >= 0.65) {
                      rating = "Medium Match";
                      ratingColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                    }

                    return (
                      <div 
                        key={i} 
                        className="flex flex-wrap items-center gap-1.5 p-1.5 px-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] text-[11px] text-slate-300 max-w-full"
                      >
                        <FileText className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                        <span className="font-medium truncate max-w-[120px]" title={c.title}>{c.title}</span>
                        <span className={cn("text-[9px] px-1.5 py-0.5 rounded border font-semibold flex-shrink-0", ratingColor)}>
                          {rating}
                        </span>
                        {(c.uploaded_at || metadata?.created_at) && (
                          <span className="text-[10px] text-slate-500">
                            ({c.uploaded_at ? new Date(c.uploaded_at).toLocaleDateString() : metadata?.created_at})
                          </span>
                        )}
                        {c.is_latest_relevant_source && (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded shadow-sm shadow-indigo-500/20 animate-pulse">
                            Latest Source
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Utility Actions */}
            <div className="flex items-center gap-3 mt-2 ml-1">
              <div className="flex-1" />
              <button onClick={copy} className="text-xs text-slate-500 hover:text-white flex items-center gap-1 transition-colors">
                <Copy className="w-3 h-3" />
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                onClick={() => handleFeedback("up")}
                className={cn("p-1 rounded-lg transition-colors", feedback === "up" ? "text-emerald-400 bg-emerald-500/10" : "text-slate-500 hover:text-emerald-400")}
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => handleFeedback("down")}
                className={cn("p-1 rounded-lg transition-colors", feedback === "down" ? "text-rose-400 bg-rose-500/10" : "text-slate-500 hover:text-rose-400")}
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ========== SOURCE PANEL WITH FRESHNESS ==========
interface SourcePanelProps {
  citations: Citation[];
  onClose: () => void;
  getDocMetadata: (docId: number) => {
    title: string;
    filename: string;
    created_at: string | null;
    isLatest: boolean;
  } | null;
}

function SourcePanel({ citations, onClose, getDocMetadata }: SourcePanelProps) {
  return (
    <motion.div
      initial={{ x: 320, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 320, opacity: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="w-80 flex-shrink-0 border-l border-white/[0.06] bg-[#030c1a] flex flex-col shadow-2xl"
    >
      <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
        <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
          <FileText className="w-4 h-4 text-indigo-400" />
          Sources ({citations.length})
        </h3>
        <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {citations.map((c, i) => {
          const metadata = getDocMetadata(c.document_id);
          
          let rating = "Weak";
          let ratingColor = "text-rose-400 bg-rose-500/10 border-rose-500/20";
          if (c.similarity >= 0.8) {
            rating = "Good Match";
            ratingColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
          } else if (c.similarity >= 0.65) {
            rating = "Medium Match";
            ratingColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
          }

          return (
            <div
              key={i}
              className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-indigo-500/20 transition-all space-y-2 shadow-sm"
            >
              <div className="flex items-start gap-2">
                <FileText className="w-3.5 h-3.5 text-indigo-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="text-xs font-semibold text-white truncate max-w-[150px]">{c.title}</p>
                    {c.is_latest_relevant_source && (
                      <span className="text-[8px] font-bold px-1 bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded">
                        LATEST
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-slate-500">
                      Match: {Math.round(c.similarity * 100)}%
                    </span>
                    <span className={cn("text-[8px] font-bold px-1 rounded border", ratingColor)}>
                      {rating}
                    </span>
                  </div>
                  {(c.uploaded_at || metadata?.created_at) && (
                    <p className="text-[9px] text-slate-500 mt-0.5">
                      Uploaded on {c.uploaded_at ? new Date(c.uploaded_at).toLocaleDateString() : metadata?.created_at}
                    </p>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed bg-white/[0.01] p-2 rounded border border-white/[0.02]">
                {c.snippet}
              </p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

export default function QueryPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [showSources, setShowSources] = useState(false);
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  
  const [trustMode, setTrustMode] = useState<"fast" | "verified" | "strict">("verified");
  const strictMode = trustMode === "strict";
  const setStrictMode = (enabled: boolean) => setTrustMode(enabled ? "strict" : "verified");
  
  const bottomRef = useRef<HTMLDivElement>(null);

  const queryMutation = useQueryDocuments();
  const { data: docs = [], isLoading: docsLoading } = useDocuments();
  const { data: history = [], isLoading: historyLoading } = useQueryHistory(20);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Find the latest uploaded document
  const documents = docs as QueryDocument[];
  const latestDoc = documents.length > 0 ? documents.reduce((latest, current) => {
    if (!latest.created_at) return current;
    if (!current.created_at) return latest;
    return new Date(current.created_at) > new Date(latest.created_at) ? current : latest;
  }, documents[0]) : null;
  const latestDocId = latestDoc ? (latestDoc.document_id ?? latestDoc.id) : null;

  const getDocMetadata = (docId: number | string) => {
    const d = documents.find((x) => (x.document_id ?? x.id) === docId);
    if (!d) return null;
    return {
      title: d.title,
      filename: d.filename,
      created_at: d.created_at ? new Date(d.created_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      }) : null,
      isLatest: (d.document_id ?? d.id) === latestDocId
    };
  };

  const handleSend = async () => {
    if (!input.trim() || queryMutation.isPending) return;
    const question = input.trim();
    setInput("");

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: question };
    const loadingMsg: Message = { id: (Date.now() + 1).toString(), role: "assistant", content: "", loading: true };
    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    try {
      const res = await queryMutation.mutateAsync({ 
        question, 
        topK: 5,
        verifierMode: trustMode,
        advancedMode: true
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                loading: false,
                content: res.answer,
                confidence: res.confidence,
                citations: res.citations,
                latency: res.latency_ms,
                faithfulness_score: res.faithfulness_score,
                unsupported_claim_rate: res.unsupported_claim_rate,
                claim_support_rate: res.claim_support_rate,
                verification_status: res.verification_status,
                verification_summary: res.verification_summary,
                claim_passport_status: res.claim_passport_status,
                trust_status: res.trust_status,
                judge_status: res.judge_status,
                claim_verifications: res.claim_verifications,
                // Trust Engine fields
                citation_truth_score: res.citation_truth_score,
                citation_quality_label: res.citation_quality_label,
                citation_verifications: res.citation_verifications,
                conflict_detected: res.conflict_detected,
                conflict_summary: res.conflict_summary,
                conflict_sources: res.conflict_sources,
                evidence_gap_detected: res.evidence_gap_detected,
                freshness_warning: res.freshness_warning,
                evidence_gap_summary: res.evidence_gap_summary,
                missing_information: res.missing_information,
                suggested_actions: res.suggested_actions,
                conflict_details: res.conflict_details,
                latest_source_id: res.latest_source_id,
                trust_mode: res.trust_mode,
              }
            : m
        )
      );
      if (res.citations?.length) {
        setActiveCitations(res.citations);
        setShowSources(true);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Something went wrong. Please try again.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, loading: false, content: message }
            : m
        )
      );
    }
  };

  const handleFeedback = (_id: string, _v: "up" | "down") => {
    // Feedback handling
  };

  const readyDocs = docs.filter((d: { status?: string }) => d.status === "ready");

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -m-4 lg:-m-6">
      {/* History Sidebar */}
      <div className="hidden lg:flex w-60 flex-col border-r border-white/[0.06] bg-[#030c1a]">
        <div className="p-4 border-b border-white/[0.06]">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">History</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {historyLoading ? (
            <LoadingSkeleton rows={4} />
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-slate-500 text-xs">No history yet</div>
          ) : (
            history.map((h: { id: number; question: string }) => (
              <button
                key={h.id}
                onClick={() => setInput(h.question)}
                className="w-full text-left p-2.5 rounded-xl text-xs text-slate-400 hover:text-white hover:bg-white/[0.04] transition-colors truncate block"
              >
                {h.question}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#020817]">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4 shadow-inner">
                <Sparkles className="w-7 h-7 text-indigo-400" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">Ask your documents</h3>
              <p className="text-slate-400 text-sm max-w-sm">
                {readyDocs.length > 0
                  ? `${readyDocs.length} document${readyDocs.length > 1 ? "s" : ""} ready. Ask anything from your knowledge base.`
                  : "Upload documents first to start asking questions with source-based answers."}
              </p>
              {readyDocs.length === 0 && !docsLoading && (
                <button
                  onClick={() => navigate("/documents")}
                  className="mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
                >
                  Upload documents →
                </button>
              )}
              {readyDocs.length > 0 && (
                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-md w-full">
                  {["What are the key findings in my documents?", "Summarize the main topics covered", "What are the important dates mentioned?"].map((q) => (
                    <button
                      key={q}
                      onClick={() => setInput(q)}
                      className="text-left p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-indigo-500/30 hover:bg-white/[0.05] text-xs text-slate-300 transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              {messages.map((msg) =>
                msg.role === "user" ? (
                  <UserMessage key={msg.id} msg={msg} />
                ) : (
                  <AssistantMessage 
                    key={msg.id} 
                    msg={msg} 
                    onFeedback={handleFeedback} 
                    getDocMetadata={getDocMetadata}
                  />
                )
              )}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-white/[0.06] p-4 space-y-3 bg-[#030c1a]/30 backdrop-blur-sm">
          {/* Controls / Options */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.04] pb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-300">Trust mode</span>
              <div className="flex rounded-lg border border-white/[0.08] bg-white/[0.03] p-0.5">
                {(["fast", "verified", "strict"] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setTrustMode(mode)}
                    className={cn(
                      "px-2.5 py-1 text-[11px] font-semibold rounded-md capitalize transition-colors",
                      trustMode === mode ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                    )}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={strictMode} 
                  onChange={(e) => setStrictMode(e.target.checked)} 
                  className="sr-only peer"
                />
                <div className="w-8 h-4.5 bg-white/[0.08] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:border-slate-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-indigo-600 peer-checked:after:bg-white peer-checked:after:border-transparent"></div>
                <span className="ml-2 text-xs font-semibold text-slate-300 select-none flex items-center gap-1">
                  🛡️ Strict Evidence Mode 
                  <span className="text-[10px] text-slate-500 font-normal">(refuses when evidence lacks)</span>
                </span>
              </label>
            </div>
            
            {readyDocs.length > 0 && (
              <span className="text-[10px] text-slate-500 font-medium">
                Searching {readyDocs.length} active document{readyDocs.length > 1 ? "s" : ""}
              </span>
            )}
          </div>

          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={readyDocs.length > 0 ? "Ask anything from your documents..." : "Please upload a document to begin..."}
                disabled={readyDocs.length === 0}
                rows={1}
                className="w-full px-4 py-3 pr-12 rounded-2xl bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-slate-500 text-sm focus:outline-none focus:border-indigo-500/60 resize-none transition-colors disabled:opacity-40"
                style={{ minHeight: "48px", maxHeight: "160px" }}
              />
              {activeCitations.length > 0 && (
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="absolute right-3 top-3 p-1 rounded-lg text-slate-400 hover:text-white transition-colors"
                  title="Toggle sources panel"
                >
                  <FileText className="w-4 h-4" />
                </button>
              )}
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || queryMutation.isPending || readyDocs.length === 0}
              className="p-3 rounded-2xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white transition-all flex-shrink-0 shadow-lg shadow-indigo-500/10"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-slate-600 text-center">
            Cognimend Trust Engine checks each claim against verified document context.
          </p>
        </div>
      </div>

      {/* Source Panel */}
      <AnimatePresence>
        {showSources && activeCitations.length > 0 && (
          <SourcePanel 
            citations={activeCitations} 
            onClose={() => setShowSources(false)} 
            getDocMetadata={getDocMetadata}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
