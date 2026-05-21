import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Trash2, MoreVertical, Clock, Check, AlertCircle, Loader2, Sparkles, RefreshCw, Download, Eye, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

interface Document {
  id: string;
  name: string;
  version: string;
  uploadedAt: Date;
  status: "processing" | "ready" | "error";
}

interface ApiDocument {
  id: number;
  title: string;
  filename: string;
  version: number;
  status: string;
  chunk_count: number;
  created_at: string;
}

interface DocumentDetails {
  id: number;
  title: string;
  filename: string;
  file_hash: string;
  version: number;
  status: string;
  chunk_count: number;
  created_at: string;
}

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? "s" : ""} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? "s" : ""} ago`;
  return `${diffDays} day${diffDays !== 1 ? "s" : ""} ago`;
}

function StatusBadge({ status }: { status: Document["status"] }) {
  const config = {
    processing: {
      label: "Processing",
      className: "bg-info/10 text-info border-info/20",
      icon: Loader2,
      iconClass: "animate-spin",
    },
    ready: {
      label: "Ready",
      className: "bg-success/10 text-success border-success/20",
      icon: Check,
      iconClass: "",
    },
    error: {
      label: "Error",
      className: "bg-destructive/10 text-destructive border-destructive/20",
      icon: AlertCircle,
      iconClass: "",
    },
  };

  const { label, className, icon: Icon, iconClass } = config[status];

  return (
    <Badge variant="outline" className={cn("gap-1.5 px-2.5 py-1", className)}>
      <Icon className={cn("h-3 w-3", iconClass)} />
      {label}
    </Badge>
  );
}

export function DocumentList() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetails | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [reindexingId, setReindexingId] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_URL}/documents`);
      if (!response.ok) throw new Error("Failed to fetch documents");
      const data = await response.json();
      
      const mappedDocs: Document[] = (data.documents || []).map((doc: ApiDocument) => ({
        id: String(doc.id),
        name: doc.title || doc.filename,
        version: `v${doc.version}`,
        uploadedAt: new Date(doc.created_at.endsWith('Z') ? doc.created_at : doc.created_at + 'Z'),
        status: doc.status as "processing" | "ready" | "error",
      }));
      
      setDocuments(mappedDocs);
    } catch (err) {
      console.error("Error fetching documents:", err);
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchDocuments, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await fetch(`${API_URL}/documents/${id}`, { method: "DELETE" });
      setDocuments((docs) => docs.filter((doc) => doc.id !== id));
      toast({
        title: "Document deleted",
        description: "The document has been successfully deleted.",
      });
    } catch (err) {
      console.error("Error deleting document:", err);
      toast({
        title: "Error",
        description: "Failed to delete document.",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const handleViewDetails = async (id: string) => {
    try {
      const response = await fetch(`${API_URL}/documents/${id}`);
      if (!response.ok) throw new Error("Failed to fetch document details");
      const data = await response.json();
      setSelectedDocument(data.document);
      setDetailsOpen(true);
    } catch (err) {
      console.error("Error fetching document details:", err);
      toast({
        title: "Error",
        description: "Failed to load document details.",
        variant: "destructive",
      });
    }
  };

  const handleDownload = async (id: string, filename: string) => {
    try {
      const response = await fetch(`${API_URL}/documents/${id}/download`);
      if (!response.ok) throw new Error("Failed to download document");
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename.replace(/\.[^/.]+$/, "") + ".txt";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast({
        title: "Download started",
        description: "Your document is being downloaded.",
      });
    } catch (err) {
      console.error("Error downloading document:", err);
      toast({
        title: "Error",
        description: "Failed to download document.",
        variant: "destructive",
      });
    }
  };

  const handleReindex = async (id: string) => {
    setReindexingId(id);
    try {
      const response = await fetch(`${API_URL}/documents/${id}/reindex`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to re-index document");
      
      toast({
        title: "Re-indexing complete",
        description: "The document has been successfully re-indexed.",
      });
      
      // Refresh the document list
      fetchDocuments();
    } catch (err) {
      console.error("Error re-indexing document:", err);
      toast({
        title: "Error",
        description: "Failed to re-index document.",
        variant: "destructive",
      });
    } finally {
      setReindexingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-secondary/20 to-primary/20 flex items-center justify-center">
            <Sparkles className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-foreground">Your Documents</h2>
            <p className="text-sm text-muted-foreground">
              {documents.length} document{documents.length !== 1 ? "s" : ""} in your knowledge base
            </p>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={fetchDocuments} className="rounded-full" disabled={loading}>
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </Button>
      </div>

      {error && (
        <div className="text-center py-4 text-destructive">
          {error}
        </div>
      )}

      {loading && documents.length === 0 ? (
        <div className="text-center py-16">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="text-sm text-muted-foreground mt-4">Loading documents...</p>
        </div>
      ) : (
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {documents.map((doc, index) => (
            <motion.div
              key={doc.id}
              layout
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -100, transition: { duration: 0.2 } }}
              transition={{ delay: index * 0.05 }}
              className={cn(
                "group rounded-2xl border bg-card p-5 transition-all duration-200 hover:shadow-lg hover:border-primary/20 hover-lift",
                deletingId === doc.id && "opacity-50 scale-95"
              )}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="rounded-xl bg-gradient-to-br from-primary/10 to-accent/10 p-3 shrink-0 group-hover:from-primary/20 group-hover:to-accent/20 transition-colors">
                    <FileText className="h-5 w-5 text-primary" />
                  </div>
                  
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-foreground truncate">{doc.name}</h3>
                      <Badge variant="secondary" className="shrink-0 bg-secondary/10 text-secondary">{doc.version}</Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-1.5 text-sm text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      <span>{formatRelativeTime(doc.uploadedAt)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <StatusBadge status={doc.status} />
                  
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-popover rounded-xl">
                      <DropdownMenuItem 
                        className="rounded-lg cursor-pointer"
                        onClick={() => handleViewDetails(doc.id)}
                      >
                        <Eye className="h-4 w-4 mr-2" />
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        className="rounded-lg cursor-pointer"
                        onClick={() => handleDownload(doc.id, doc.name)}
                        disabled={doc.status !== "ready"}
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Download
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        className="rounded-lg cursor-pointer"
                        onClick={() => handleReindex(doc.id)}
                        disabled={doc.status === "processing" || reindexingId === doc.id}
                      >
                        <RotateCcw className={cn("h-4 w-4 mr-2", reindexingId === doc.id && "animate-spin")} />
                        {reindexingId === doc.id ? "Re-indexing..." : "Re-index"}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="rounded-full text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="bg-card rounded-2xl">
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete Document</AlertDialogTitle>
                        <AlertDialogDescription>
                          Are you sure you want to delete "{doc.name}"? This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel className="rounded-xl">Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => handleDelete(doc.id)}
                          className="rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {documents.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-16 rounded-2xl border-2 border-dashed"
          >
            <div className="rounded-full bg-muted p-4 w-fit mx-auto mb-4">
              <FileText className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="font-medium text-foreground">No documents uploaded yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Drag and drop files above to get started
            </p>
          </motion.div>
        )}
      </div>
      )}

      {/* Document Details Dialog */}
      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent className="bg-card rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              Document Details
            </DialogTitle>
            <DialogDescription>
              View detailed information about this document.
            </DialogDescription>
          </DialogHeader>
          {selectedDocument && (
            <div className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Title</p>
                  <p className="font-medium">{selectedDocument.title}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Filename</p>
                  <p className="font-medium truncate">{selectedDocument.filename}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Version</p>
                  <p className="font-medium">v{selectedDocument.version}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <Badge 
                    variant="outline" 
                    className={cn(
                      "mt-1",
                      selectedDocument.status === "ready" && "bg-success/10 text-success border-success/20",
                      selectedDocument.status === "processing" && "bg-info/10 text-info border-info/20",
                      selectedDocument.status === "error" && "bg-destructive/10 text-destructive border-destructive/20"
                    )}
                  >
                    {selectedDocument.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Chunks</p>
                  <p className="font-medium">{selectedDocument.chunk_count}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Created</p>
                  <p className="font-medium">
                    {new Date(selectedDocument.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              {selectedDocument.file_hash && (
                <div>
                  <p className="text-sm text-muted-foreground">File Hash (SHA-256)</p>
                  <p className="font-mono text-xs break-all mt-1 bg-muted p-2 rounded-lg">
                    {selectedDocument.file_hash}
                  </p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
