import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, BookOpen, Upload, FileText, Brain, Trash2 } from 'lucide-react';
import { api, Course, FileUpload, TopicWithNotes } from '@/lib/api';
import { FileUpload as FileUploadComponent } from '@/components/FileUpload';
import { NotesDisplay } from '@/components/NotesDisplay';

export function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const [course, setCourse] = useState<Course | null>(null);
  const [files, setFiles] = useState<FileUpload[]>([]);
  const [notes, setNotes] = useState<TopicWithNotes[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (courseId) {
      loadCourseData();
    }
  }, [courseId]);

  const loadCourseData = async () => {
    try {
      setIsLoading(true);
      setError(''); // Clear any previous errors
      
      // Load course data first (required)
      const courseData = await api.getCourse(parseInt(courseId!));
      setCourse(courseData);
      
      // Load files and notes separately to handle empty states gracefully
      try {
        const filesData = await api.getCourseFiles(parseInt(courseId!));
        setFiles(filesData);
      } catch (filesErr) {
        console.warn('Failed to load course files:', filesErr);
        setFiles([]); // Set empty array if files fail to load
      }
      
      try {
        const notesData = await api.getCourseNotes(parseInt(courseId!));
        setNotes(notesData);
      } catch (notesErr) {
        console.warn('Failed to load course notes:', notesErr);
        setNotes([]); // Set empty array if notes fail to load
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load course data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUploadComplete = () => {
    loadCourseData(); // Reload data to show new files and notes
  };

  const handleFileDelete = async (fileId: number) => {
    if (!confirm('Are you sure you want to delete this file? This will also remove all associated notes and chunks.')) {
      return;
    }

    try {
      await api.deleteFile(fileId);
      await loadCourseData(); // Reload data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete file');
    }
  };

  const handleNotesUpdate = () => {
    loadCourseData(); // Reload notes data
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center">Loading course...</div>
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600">
          {error || 'Course not found'}
        </div>
        <Button onClick={() => navigate('/')} className="mt-4">
          Back to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <Button
            variant="ghost"
            onClick={() => navigate('/')}
            className="p-2"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{course.name}</h1>
            {course.description && (
              <p className="text-muted-foreground mt-1">{course.description}</p>
            )}
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          Created: {new Date(course.created_at).toLocaleDateString()}
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
          <TabsTrigger value="study">Study Mode</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Files Uploaded</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{files.length}</div>
                <p className="text-xs text-muted-foreground">
                  {files.length === 0 ? 'No files yet' : 'Course materials'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Topics</CardTitle>
                <BookOpen className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{notes.length}</div>
                <p className="text-xs text-muted-foreground">
                  {notes.length === 0 ? 'No topics yet' : 'AI-generated topics'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Notes</CardTitle>
                <Brain className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {notes.reduce((total, topic) => total + topic.notes.length, 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {notes.length === 0 ? 'No notes yet' : 'AI-generated notes'}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Button
                  onClick={() => setActiveTab('files')}
                  className="h-20 text-lg"
                >
                  <Upload className="h-6 w-6 mr-3" />
                  Upload New File
                </Button>
                <Button
                  onClick={() => setActiveTab('notes')}
                  variant="outline"
                  className="h-20 text-lg"
                >
                  <BookOpen className="h-6 w-6 mr-3" />
                  View Notes
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Files Tab */}
        <TabsContent value="files" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Course Files</h2>
            <Button onClick={() => setActiveTab('overview')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Overview
            </Button>
          </div>

          {/* File Upload */}
          <FileUploadComponent
            courseId={course.id}
            onUploadComplete={handleFileUploadComplete}
          />

          {/* Files List */}
          {files.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Uploaded Files</span>
                  <span className="text-sm font-normal text-muted-foreground">
                    {files.length} file{files.length !== 1 ? 's' : ''}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {files.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="text-2xl">
                          {file.file_type === 'pdf' ? '📄' : 
                           file.file_type === 'docx' ? '📝' : '📄'}
                        </div>
                        <div className="flex-1">
                          <p className="font-medium">{file.filename}</p>
                          <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                            <span className="uppercase">{file.file_type}</span>
                            <span>•</span>
                            <span>{file.chunks_count} chunk{file.chunks_count !== 1 ? 's' : ''}</span>
                            <span>•</span>
                            <span>{new Date(file.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleFileDelete(file.id)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Empty State */}
          {files.length === 0 && (
            <Card>
              <CardContent className="p-8 text-center">
                <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-medium mb-2">No Files Yet</h3>
                <p className="text-muted-foreground mb-4">
                  Upload your first course material to get started with AI-powered learning.
                </p>
                <div className="text-sm text-muted-foreground space-y-1">
                  <p>• PDF documents for complex formatting</p>
                  <p>• Word documents for rich text content</p>
                  <p>• Text files for simple content</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Notes Tab */}
        <TabsContent value="notes" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Course Notes</h2>
            <Button onClick={() => setActiveTab('overview')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Overview
            </Button>
          </div>

          <NotesDisplay
            courseId={course.id}
            topicsWithNotes={notes}
            onNotesUpdate={handleNotesUpdate}
          />
        </TabsContent>

        {/* Study Mode Tab */}
        <TabsContent value="study" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Study Mode</h2>
            <Button onClick={() => setActiveTab('overview')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Overview
            </Button>
          </div>

          <Card>
            <CardContent className="p-8 text-center">
              <Brain className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-medium mb-2">Study Mode Coming Soon</h3>
              <p className="text-muted-foreground">
                Interactive study features, quizzes, and spaced repetition will be available here.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 