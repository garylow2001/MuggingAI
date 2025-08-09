import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, FileText, X, CheckCircle, AlertCircle, Loader2, Info, Eye } from 'lucide-react';
import { api, FileUploadResponse } from '@/lib/api';

interface FileUploadProps {
  courseId: number;
  onUploadComplete: () => void;
}

export function FileUpload({ courseId, onUploadComplete }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadResult, setUploadResult] = useState<FileUploadResponse | null>(null);
  const [error, setError] = useState<string>('');
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
        setError('');
        setUploadResult(null);
      }
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && isValidFile(file)) {
      setSelectedFile(file);
      setError('');
      setUploadResult(null);
    }
  }, []);

  const isValidFile = (file: File): boolean => {
    const allowedTypes = ['.pdf', '.docx', '.txt'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    
    console.log('Validating file:', file.name, 'Type:', fileExtension, 'Size:', file.size);
    
    if (!allowedTypes.includes(fileExtension)) {
      const errorMsg = `File type not supported. Allowed: ${allowedTypes.join(', ')}`;
      console.log('File validation failed:', errorMsg);
      setError(errorMsg);
      return false;
    }
    
    if (file.size > 50 * 1024 * 1024) { // 50MB
      const errorMsg = 'File too large. Maximum size: 50MB';
      console.log('File validation failed:', errorMsg);
      setError(errorMsg);
      return false;
    }
    
    console.log('File validation passed');
    return true;
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError('');
    setUploadResult(null);
    setUploadProgress(0);

    try {
      console.log('Starting file upload...');
      
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 10;
        });
      }, 200);

      const result = await api.uploadFile(courseId, selectedFile);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      
      console.log('Upload successful:', result);
      setUploadResult(result);
      setSelectedFile(null);
      
      // Reset progress after showing result
      setTimeout(() => {
        setUploadProgress(0);
        onUploadComplete();
      }, 2000);
      
    } catch (err) {
      console.error('Upload error:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploadProgress(0);
    } finally {
      setIsUploading(false);
    }
  };

  const removeFile = () => {
    setSelectedFile(null);
    setError('');
    setUploadResult(null);
    setUploadProgress(0);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (filename: string) => {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'pdf':
        return '📄';
      case 'docx':
        return '📝';
      case 'txt':
        return '📄';
      default:
        return '📁';
    }
  };

  const getFileTypeInfo = (filename: string) => {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'pdf':
        return 'Portable Document Format - Best for documents with complex formatting';
      case 'docx':
        return 'Microsoft Word Document - Best for rich text documents';
      case 'txt':
        return 'Plain Text - Best for simple text content';
      default:
        return 'Unknown file type';
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
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-primary/50'
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
              onClick={() => document.getElementById('file-input')?.click()}
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
                <span className="text-2xl">{getFileIcon(selectedFile.name)}</span>
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
                  className="text-blue-600 hover:text-blue-700"
                >
                  <Info className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={removeFile}
                  disabled={isUploading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {/* Upload Progress */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Processing file...</span>
                <span>{Math.round(uploadProgress)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-primary h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Upload Button */}
          {selectedFile && (
            <Button
              onClick={handleUpload}
              disabled={isUploading}
              className="w-full"
              size="lg"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                'Upload & Process'
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
                <h4 className="font-medium text-green-800">Upload Successful!</h4>
              </div>
              <div className="space-y-2 text-sm text-green-700">
                <p><strong>File:</strong> {uploadResult.filename}</p>
                <p><strong>Chunks created:</strong> {uploadResult.chunks_created}</p>
                <p><strong>Notes generated:</strong> {uploadResult.notes_generated}</p>
                <p><strong>Chapters detected:</strong> {uploadResult.statistics.unique_chapters}</p>
                {uploadResult.statistics.chapters && uploadResult.statistics.chapters.length > 0 && (
                  <div>
                    <strong>Chapters:</strong>
                    <ul className="list-disc list-inside ml-2 mt-1">
                      {uploadResult.statistics.chapters.map((chapter, index) => (
                        <li key={index}>{chapter}</li>
                      ))}
                    </ul>
                  </div>
                )}
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
                <span className="text-3xl">{getFileIcon(selectedFile.name)}</span>
                <div>
                  <p className="font-medium text-lg">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {selectedFile.type || 'Unknown type'}
                  </p>
                </div>
              </div>
              
              <div className="space-y-2 text-sm">
                <p><strong>Size:</strong> {formatFileSize(selectedFile.size)}</p>
                <p><strong>Last Modified:</strong> {new Date(selectedFile.lastModified).toLocaleString()}</p>
                <p><strong>File Type:</strong> {getFileTypeInfo(selectedFile.name)}</p>
              </div>
              
              <div className="pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  This file will be processed to extract text content, create chunks for AI analysis, 
                  and generate structured notes for your course.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
