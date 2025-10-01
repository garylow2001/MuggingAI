import React, { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Upload,
  X,
  CheckCircle,
  AlertCircle,
  Loader2,
  Info,
} from "lucide-react";
import {
  api,
  FileUploadStatusResponse,
  FileUploadStatusResult,
} from "@/lib/api";
import { mutate } from "swr";
import { useToast } from "@/hooks/use-toast";

interface FileUploadProps {
  courseId: number;
}

export function FileUpload({ courseId }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] =
    useState<FileUploadStatusResult | null>(null);
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false);
  const [error, setError] = useState<string>("");
  const { toast } = useToast();
  const [showFileDetails, setShowFileDetails] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      const file = files[0];
      if (isValidFile(file)) {
        setSelectedFile(file);
        setError("");
        setUploadResult(null);
      }
    }
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && isValidFile(file)) {
        setSelectedFile(file);
        setError("");
        setUploadResult(null);
      }
    },
    []
  );

  const isValidFile = (file: File): boolean => {
    const allowedTypes = [".pdf", ".docx", ".txt"];
    const fileExtension = "." + file.name.split(".").pop()?.toLowerCase();

    console.log(
      "Validating file:",
      file.name,
      "Type:",
      fileExtension,
      "Size:",
      file.size
    );

    if (!allowedTypes.includes(fileExtension)) {
      const errorMsg = `File type not supported. Allowed: ${allowedTypes.join(
        ", "
      )}`;
      console.log("File validation failed:", errorMsg);
      setError(errorMsg);
      return false;
    }

    if (file.size > 50 * 1024 * 1024) {
      // 50MB
      const errorMsg = "File too large. Maximum size: 50MB";
      console.log("File validation failed:", errorMsg);
      setError(errorMsg);
      return false;
    }

    console.log("File validation passed");
    return true;
  };

  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any>(null);
  const [polling, setPolling] = useState(false);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setError("");
    setUploadResult(null);

    try {
      const result = await api.uploadFile(courseId, selectedFile);
      if (result.job_id) {
        setJobId(result.job_id);
        setPolling(true);
      } else {
        setError("No job ID returned from backend");
        setIsUploading(false);
      }
      setSelectedFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setIsUploading(false);
    }
  };

  // Polling effect for job status
  useEffect(() => {
    if (!jobId || !polling) return;
    const interval = setInterval(async () => {
      try {
        const status = await api.getUploadStatus(jobId);
        setJobStatus(status);
        // Progress is now the number of messages
        if (status.status === "SUCCESS" || status.status === "FAILURE") {
          setPolling(false);
          setIsUploading(false);
          setUploadResult(status.result || null);
        }
        if (status.status === "FAILURE") {
          setError("Upload failed");
        }
      } catch (e) {
        // handle error
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, polling]);

  const removeFile = () => {
    setSelectedFile(null);
    setError("");
    setUploadResult(null);
    try {
      const key = `lastUploadResult_course_${courseId}`;
      localStorage.removeItem(key);
    } catch (e) {
      /* ignore */
    }
  };

  const handleGenerateNotes = async () => {
    if (!uploadResult) return;
    setIsGeneratingNotes(true);
    try {
      const res = await api.generateNotes(courseId, uploadResult.file_id);

      // Clear persisted upload result so it is not retained after notes are created
      const key = `lastUploadResult_course_${courseId}`;
      localStorage.removeItem(key);

      // Remove upload result from state
      setUploadResult(null);

      // Revalidate notes and course data
      try {
        mutate(["courseNotes", courseId]);
        mutate(["course", courseId]);
      } catch (e) {
        // ignore
      }

      // Show toast confirmation with green tick and 5s auto-dismiss
      toast({
        title: `${res.notes_generated} Notes generated successfully`,
        description: "Open the Notes tab to view them.",
        icon: <CheckCircle className="h-5 w-5 text-green-600" />,
        duration: 5000,
      });
    } catch (e) {
      console.error("Generate notes error", e);
      setError(e instanceof Error ? e.message : "Failed to generate notes");
    } finally {
      setIsGeneratingNotes(false);
    }
  };

  // Restore persisted upload result on mount (per course)
  useEffect(() => {
    try {
      const key = `lastUploadResult_course_${courseId}`;
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw) as FileUploadStatusResponse;
        setUploadResult(parsed.result || null);
      }
    } catch (e) {
      console.warn("Failed to restore persisted upload result", e);
    }
  }, [courseId]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const getFileIcon = (filename: string) => {
    const extension = filename.split(".").pop()?.toLowerCase();
    switch (extension) {
      case "pdf":
        return "📄";
      case "docx":
        return "📝";
      case "txt":
        return "📄";
      default:
        return "📁";
    }
  };

  const getFileTypeInfo = (filename: string) => {
    const extension = filename.split(".").pop()?.toLowerCase();
    switch (extension) {
      case "pdf":
        return "PDF - Best for documents with complex formatting";
      case "docx":
        return "DOCX - Best for rich text documents";
      case "txt":
        return "TXT - Best for simple text content";
      default:
        return "Unknown file type";
    }
  };

  return (
    <>
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Upload className="h-5 w-5" />
            <span>Upload Course Material</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              isDragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-lg font-medium mb-2">
              Drag and drop your file here, or click to browse
            </p>
            <p className="text-sm text-muted-foreground mb-4">
              Supports PDF, DOCX, and TXT files (max 50MB)
            </p>
            <Button
              variant="outline"
              onClick={() => document.getElementById("file-input")?.click()}
              type="button"
              disabled={isUploading}
            >
              Choose File
            </Button>
            <input
              id="file-input"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>

          {/* Selected File */}
          {selectedFile && (
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">
                  {getFileIcon(selectedFile.name)}
                </span>
                <div>
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowFileDetails(true)}
                  type="button"
                  className="text-blue-600 hover:text-blue-700"
                >
                  <Info className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={removeFile}
                  type="button"
                  disabled={isUploading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {/* Modern Progress Status */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex flex-col gap-2 mt-2">
                {jobStatus?.progress_messages?.map(
                  (msg: string, idx: number) => (
                    <div key={idx} className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-primary" />
                      <span className="text-sm text-gray-800">{msg}</span>
                    </div>
                  )
                )}
                {/* Skeleton loader for next message */}
                {polling && (
                  <div className="flex items-center gap-2 animate-pulse">
                    <Loader2 className="h-4 w-4 text-gray-400" />
                    <span className="h-4 w-32 bg-gray-200 rounded" />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Upload Button */}
          {selectedFile && (
            <Button
              onClick={handleUpload}
              disabled={isUploading}
              type="button"
              className="w-full"
              size="lg"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                "Upload & Process"
              )}
            </Button>
          )}

          {/* Error Message */}
          {error && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle className="h-5 w-5 text-red-600" />
              <p className="text-red-600">{error}</p>
            </div>
          )}

          {/* Upload Result */}
          {uploadResult && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-center space-x-2 mb-3">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <h4 className="font-medium text-green-800">
                  Upload Successful!
                </h4>
              </div>
              <div className="space-y-2 text-sm text-green-700">
                <p>
                  <strong>File:</strong> {uploadResult?.filename}
                </p>
                <p>
                  <strong>Chunks created:</strong>{" "}
                  {uploadResult?.chunks_created}
                </p>
                <p>
                  {/* Notes generated field removed, not present in result object */}
                </p>
                <p>
                  <strong>Chapters detected:</strong>{" "}
                  {uploadResult?.statistics?.unique_chapters}
                </p>
                {uploadResult?.statistics?.chapters &&
                  uploadResult.statistics.chapters.length > 0 && (
                    <div>
                      <strong>Chapters:</strong>
                      <ul className="list-disc list-inside ml-2 mt-1">
                        {uploadResult.statistics.chapters.map(
                          (chapter, index) => (
                            <li key={index}>{chapter}</li>
                          )
                        )}
                      </ul>
                    </div>
                  )}
                <div className="mt-3">
                  <Button
                    onClick={handleGenerateNotes}
                    disabled={isGeneratingNotes}
                    size="sm"
                    type="button"
                  >
                    {isGeneratingNotes ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      "Generate notes"
                    )}
                  </Button>
                </div>
                {uploadResult.summaries &&
                  uploadResult.summaries.length > 0 && (
                    <div className="mt-4 p-3 bg-white rounded border">
                      <strong>Summaries</strong>
                      <ul className="list-disc list-inside mt-2 text-sm text-green-700">
                        {uploadResult.summaries.map((s, idx) => (
                          <li key={idx}>
                            <span className="font-medium">
                              Chunk {s.chunk_index}
                            </span>
                            {s.file_id ? (
                              <span> (File {s.file_id})</span>
                            ) : null}
                            : {s.summary}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                <div className="mt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setUploadResult(null);
                      try {
                        const key = `lastUploadResult_course_${courseId}`;
                        localStorage.removeItem(key);
                      } catch (e) {
                        /* ignore */
                      }
                    }}
                    type="button"
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* File Details Modal */}
      {showFileDetails && selectedFile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">File Details</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFileDetails(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="space-y-4">
              <div className="flex items-center space-x-3">
                <span className="text-3xl">
                  {getFileIcon(selectedFile.name)}
                </span>
                <div>
                  <p className="font-medium text-lg">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {selectedFile.type || "Unknown type"}
                  </p>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <p>
                  <strong>Size:</strong> {formatFileSize(selectedFile.size)}
                </p>
                <p>
                  <strong>Last Modified:</strong>{" "}
                  {new Date(selectedFile.lastModified).toLocaleString()}
                </p>
                <p>
                  <strong>File Type:</strong>{" "}
                  {getFileTypeInfo(selectedFile.name)}
                </p>
              </div>

              <div className="pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  This file will be processed to extract text content, create
                  chunks for AI analysis, and generate structured notes for your
                  course.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
