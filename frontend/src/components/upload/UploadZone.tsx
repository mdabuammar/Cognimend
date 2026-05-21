import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, X, Check, Loader2, CloudUpload, AlertCircle, ShieldAlert, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { uploadAPI } from "@/lib/api";
import { validateFile, validateTitle, sanitizeFilename, formatFileSize, ALLOWED_FILE_TYPES } from "@/lib/security/fileValidation";
import { rateLimiters, getRateLimitKey, RateLimitError } from "@/lib/security/rateLimit";
import { logger } from "@/lib/security/logger";
import {
  handleError,
  withRetry,
  circuitBreakers,
  withTimeout,
  timeoutDefaults,
  retryStrategies,
  isRetryableError,
} from "@/lib/errors";

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  file?: File;
}

interface UploadZoneProps {
  onFileUpload?: (file: File, title: string, description: string) => void;
}

export function UploadZone({ onFileUpload }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<UploadedFile | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [actualFile, setActualFile] = useState<File | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  // Secure file processing with validation
  const processFile = useCallback((file: File) => {
    // Validate file
    const validation = validateFile(file);
    
    if (!validation.valid) {
      setUploadError(validation.error || 'Invalid file');
      logger.security('File validation failed', { 
        filename: file.name, 
        error: validation.error 
      });
      return;
    }

    // Set warnings if any
    if (validation.warnings) {
      setValidationWarnings(validation.warnings);
    } else {
      setValidationWarnings([]);
    }

    // Use sanitized filename
    const safeName = validation.sanitizedFilename || sanitizeFilename(file.name);
    
    setActualFile(file);
    setSelectedFile({
      id: Math.random().toString(36).substr(2, 9),
      name: safeName,
      size: file.size,
      file: file,
    });
    setTitle(safeName.replace(/\.[^/.]+$/, ""));
    setUploadError(null);
    
    logger.info('File selected', { 
      filename: safeName, 
      size: file.size,
      type: validation.detectedType 
    });
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      processFile(file);
    }
  }, [processFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
    // Reset input to allow selecting the same file again
    e.target.value = '';
  }, [processFile]);

  // Get allowed file extensions for the file input
  const acceptedExtensions = Object.values(ALLOWED_FILE_TYPES)
    .flatMap(t => t.extensions)
    .join(',');

  // Secure title change handler
  const handleTitleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const validation = validateTitle(e.target.value);
    setTitle(validation.sanitized || e.target.value);
  }, []);

  const handleDescriptionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDescription(e.target.value);
  }, []);

  const handleUpload = async () => {
    if (!selectedFile || !title || !actualFile) return;
    
    // Validate title
    const titleValidation = validateTitle(title);
    if (!titleValidation.valid) {
      setUploadError(titleValidation.error || 'Invalid title');
      return;
    }

    // Check rate limit
    const rateLimitKey = getRateLimitKey('upload');
    const rateLimitStatus = rateLimiters.upload.checkAndRecord(rateLimitKey);
    
    if (!rateLimitStatus.allowed) {
      const waitSeconds = Math.ceil(rateLimitStatus.resetInMs / 1000);
      setUploadError(`Too many uploads. Please wait ${waitSeconds} seconds.`);
      logger.security('Upload rate limit exceeded', { filename: selectedFile.name });
      return;
    }
    
    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    
    // Progress simulation
    let progressInterval: ReturnType<typeof setInterval>;
    
    try {
      // Start progress simulation
      progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 85) {
            return 85; // Cap at 85% until actual completion
          }
          return prev + 10;
        });
      }, 200);

      // Use retry logic with circuit breaker for resilient upload
      const uploadResult = await withRetry(
        async (attempt) => {
          if (attempt > 1) {
            logger.info('Retrying upload', { 
              attempt, 
              filename: selectedFile.name 
            });
          }

          // Execute through circuit breaker for protection
          return await circuitBreakers.upload.execute(async () => {
            // Add timeout protection for uploads
            return await withTimeout(
              uploadAPI.uploadDocument(actualFile, titleValidation.sanitized),
              { 
                timeoutMs: timeoutDefaults.upload,
                message: 'Upload timed out. Please try again.'
              }
            );
          });
        },
        {
          ...retryStrategies.upload,
          onRetry: (error, attempt, delayMs) => {
            logger.info('Upload retry scheduled', { 
              attempt, 
              delayMs,
              filename: selectedFile.name,
              error: error instanceof Error ? error.message : String(error)
            });
            // Reset progress for retry
            setUploadProgress(10);
          },
        }
      );

      clearInterval(progressInterval);

      if (uploadResult.success && uploadResult.data) {
        setUploadProgress(100);
        
        logger.info('Upload successful', { 
          filename: selectedFile.name, 
          documentId: uploadResult.data.document_id,
          attempts: uploadResult.attempts
        });
        
        // Callback if provided
        if (onFileUpload) {
          onFileUpload(actualFile, titleValidation.sanitized, description);
        }
        
        setIsUploading(false);
        setUploadSuccess(true);
        
        setTimeout(() => {
          setUploadSuccess(false);
          setSelectedFile(null);
          setTitle("");
          setDescription("");
          setUploadProgress(0);
          setActualFile(null);
          setValidationWarnings([]);
        }, 2000);
      } else {
        // Handle failed upload
        const handled = handleError(uploadResult.error, {
          showToast: false,
          context: { filename: selectedFile.name },
        });
        setUploadError(handled.userMessage);
        setUploadProgress(0);
        setIsUploading(false);
        
        logger.error('Upload failed after retries', { 
          filename: selectedFile.name,
          code: uploadResult.error?.code,
          attempts: uploadResult.attempts
        });
      }
    } catch (error) {
      // Catch any unexpected errors
      clearInterval(progressInterval!);
      
      const handled = handleError(error, {
        showToast: true,
        context: { operation: 'upload', filename: selectedFile.name },
      });
      
      setIsUploading(false);
      setUploadError(handled.userMessage);
      setUploadProgress(0);
      
      logger.error('Upload error', { 
        filename: selectedFile.name,
        error: error instanceof Error ? error.message : String(error),
        isRetryable: isRetryableError(error)
      });
    }
  };

  const removeFile = () => {
    setSelectedFile(null);
    setTitle("");
    setDescription("");
    setActualFile(null);
    setUploadError(null);
    setValidationWarnings([]);
  };

  return (
    <div className="space-y-6">
      {/* Validation Warnings */}
      {validationWarnings.length > 0 && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-3">
          <div className="flex items-center gap-2 text-warning">
            <ShieldAlert className="h-4 w-4" />
            <span className="text-sm font-medium">Warnings:</span>
          </div>
          <ul className="mt-1 text-sm text-warning/80 list-disc list-inside">
            {validationWarnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Drop Zone */}
      <motion.div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 transition-all duration-300 cursor-pointer min-h-[220px] overflow-hidden",
          isDragging
            ? "border-primary bg-primary/5 scale-[1.02]"
            : "border-primary/30 hover:border-primary/60 hover:bg-muted/30"
        )}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
      >
        {/* Background gradient effect */}
        <div className={cn(
          "absolute inset-0 transition-opacity duration-300",
          isDragging ? "opacity-100" : "opacity-0"
        )}>
          <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-accent/10 to-primary/10" />
        </div>

        <input
          type="file"
          accept=".pdf,.docx,.txt,.doc"
          onChange={handleFileSelect}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
          aria-label="Upload document"
        />
        
        <motion.div
          animate={{ y: isDragging ? -8 : 0 }}
          className="flex flex-col items-center gap-4 text-center relative z-0"
        >
          <motion.div
            animate={{ scale: isDragging ? 1.1 : 1 }}
            className={cn(
              "rounded-2xl p-5 transition-all duration-300",
              isDragging 
                ? "bg-gradient-to-br from-primary to-accent shadow-lg" 
                : "bg-gradient-to-br from-primary/10 to-accent/10"
            )}
          >
            <CloudUpload className={cn(
              "h-10 w-10 transition-colors duration-300",
              isDragging ? "text-white" : "text-primary"
            )} />
          </motion.div>
          
          <div>
            <p className="text-lg font-medium text-foreground">
              {isDragging ? "Drop your file here" : "Drag documents here or click to browse"}
            </p>
            <p className="text-sm text-muted-foreground mt-1.5">
              Supports PDF, DOCX, TXT files up to 10MB
            </p>
          </div>
        </motion.div>
      </motion.div>

      {/* Selected File Preview */}
      <AnimatePresence>
        {selectedFile && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="rounded-2xl border bg-card p-6 shadow-lg"
          >
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-4">
                <div className="rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 p-3">
                  <FileText className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">{formatFileSize(selectedFile.size)}</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={removeFile} className="rounded-full hover:bg-destructive/10 hover:text-destructive">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Form Fields */}
            <div className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="title" className="text-sm font-medium">Document Title *</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Company Policy"
                  className="bg-background rounded-xl h-11 text-ellipsis overflow-hidden max-w-full"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="text-sm font-medium">Description (optional)</Label>
                <Input
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g., Q3 2024 updates"
                  className="bg-background rounded-xl h-11"
                />
              </div>

              {/* Progress Bar */}
              <AnimatePresence>
                {isUploading && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-2"
                  >
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-primary to-accent rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${uploadProgress}%` }}
                        transition={{ duration: 0.15 }}
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Uploading... {uploadProgress}%
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Error Message */}
              <AnimatePresence>
                {uploadError && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    className="flex items-center gap-2 text-destructive p-3 rounded-xl bg-destructive/10"
                  >
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span className="text-sm font-medium">{uploadError}</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Success Message */}
              <AnimatePresence>
                {uploadSuccess && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    className="flex items-center gap-2 text-success p-3 rounded-xl bg-success/10"
                  >
                    <div className="rounded-full bg-success p-1">
                      <Check className="h-4 w-4 text-white" />
                    </div>
                    <span className="font-medium">Document uploaded successfully!</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Upload Button */}
              <Button
                onClick={handleUpload}
                disabled={!title || isUploading || uploadSuccess}
                className={cn(
                  "w-full h-12 rounded-xl font-medium text-base transition-all duration-200",
                  !title || isUploading || uploadSuccess
                    ? "bg-muted text-muted-foreground"
                    : "btn-gradient hover:shadow-xl"
                )}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Uploading...
                  </>
                ) : uploadSuccess ? (
                  <>
                    <Check className="mr-2 h-5 w-5" />
                    Uploaded!
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-5 w-5" />
                    Upload Document
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
