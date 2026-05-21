import { memo, useMemo, useCallback } from 'react';
import { FixedSizeList as List, ListChildComponentProps } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';
import { FileText, Trash2, MoreVertical, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Document {
  id: string;
  name: string;
  status: 'processing' | 'ready' | 'error';
  uploadedAt: Date;
  size: number;
}

interface VirtualizedDocumentListProps {
  documents: Document[];
  onDelete: (id: string) => void;
  onSelect: (id: string) => void;
  selectedIds?: Set<string>;
  itemHeight?: number;
}

// Memoized row component for optimal rendering
const DocumentRow = memo(function DocumentRow({
  index,
  style,
  data,
}: ListChildComponentProps<{
  documents: Document[];
  onDelete: (id: string) => void;
  onSelect: (id: string) => void;
  selectedIds: Set<string>;
}>) {
  const { documents, onDelete, onSelect, selectedIds } = data;
  const doc = documents[index];
  
  const isSelected = selectedIds.has(doc.id);
  
  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete(doc.id);
  }, [doc.id, onDelete]);
  
  const handleSelect = useCallback(() => {
    onSelect(doc.id);
  }, [doc.id, onSelect]);
  
  const statusIcon = useMemo(() => {
    switch (doc.status) {
      case 'ready':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'processing':
        return <Clock className="h-4 w-4 text-yellow-500 animate-pulse" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
    }
  }, [doc.status]);
  
  const formattedSize = useMemo(() => {
    if (doc.size < 1024) return `${doc.size} B`;
    if (doc.size < 1024 * 1024) return `${(doc.size / 1024).toFixed(1)} KB`;
    return `${(doc.size / 1024 / 1024).toFixed(1)} MB`;
  }, [doc.size]);
  
  const formattedDate = useMemo(() => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(doc.uploadedAt));
  }, [doc.uploadedAt]);

  return (
    <div
      style={style}
      onClick={handleSelect}
      className={cn(
        'flex items-center gap-4 px-4 py-2 border-b border-border cursor-pointer transition-colors',
        'hover:bg-muted/50',
        isSelected && 'bg-primary/10 border-primary/30'
      )}
    >
      <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
      
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{doc.name}</p>
        <p className="text-xs text-muted-foreground">
          {formattedSize} • {formattedDate}
        </p>
      </div>
      
      <div className="flex items-center gap-2">
        {statusIcon}
        
        <button
          onClick={handleDelete}
          className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
          aria-label="Delete document"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
});

// Memoized empty state
const EmptyState = memo(function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
      <FileText className="h-12 w-12 mb-4 opacity-50" />
      <p className="text-lg font-medium">No documents</p>
      <p className="text-sm">Upload documents to get started</p>
    </div>
  );
});

// Loading skeleton
const LoadingSkeleton = memo(function LoadingSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 animate-pulse">
          <div className="h-5 w-5 bg-muted rounded" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-3 bg-muted rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
});

export const VirtualizedDocumentList = memo(function VirtualizedDocumentList({
  documents,
  onDelete,
  onSelect,
  selectedIds = new Set(),
  itemHeight = 64,
}: VirtualizedDocumentListProps) {
  // Memoize item data to prevent unnecessary re-renders
  const itemData = useMemo(
    () => ({
      documents,
      onDelete,
      onSelect,
      selectedIds,
    }),
    [documents, onDelete, onSelect, selectedIds]
  );

  if (documents.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="h-full min-h-[400px]">
      <AutoSizer>
        {({ height, width }) => (
          <List
            height={height}
            width={width}
            itemCount={documents.length}
            itemSize={itemHeight}
            itemData={itemData}
            overscanCount={5}
          >
            {DocumentRow}
          </List>
        )}
      </AutoSizer>
    </div>
  );
});

// Export loading skeleton for use during data fetching
export { LoadingSkeleton as DocumentListSkeleton };
