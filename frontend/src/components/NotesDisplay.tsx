import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Edit, Save, X, Plus, Trash2, BookOpen, FileText } from 'lucide-react';
import { api, TopicWithNotes, Note } from '@/lib/api';

interface NotesDisplayProps {
  courseId: number;
  topicsWithNotes: TopicWithNotes[];
  onNotesUpdate: () => void;
}

export function NotesDisplay({ courseId, topicsWithNotes, onNotesUpdate }: NotesDisplayProps) {
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingContent, setEditingContent] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState<number | null>(null);
  const [showAddNote, setShowAddNote] = useState<number | null>(null);
  const [newNoteContent, setNewNoteContent] = useState<string>('');

  const handleEdit = (note: Note) => {
    setEditingNoteId(note.id);
    setEditingContent(note.content);
  };

  const handleSave = async () => {
    if (!editingNoteId || !editingContent.trim()) return;

    setIsSaving(true);
    try {
      await api.updateNote(editingNoteId, editingContent.trim());
      setEditingNoteId(null);
      setEditingContent('');
      onNotesUpdate();
    } catch (error) {
      console.error('Failed to update note:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditingNoteId(null);
    setEditingContent('');
  };

  const handleDelete = async (noteId: number) => {
    if (!confirm('Are you sure you want to delete this note?')) return;

    setIsDeleting(noteId);
    try {
      await api.deleteNote(noteId);
      onNotesUpdate();
    } catch (error) {
      console.error('Failed to delete note:', error);
    } finally {
      setIsDeleting(null);
    }
  };

  const handleAddNote = async (topicId: number) => {
    if (!newNoteContent.trim()) return;

    try {
      await api.createNote(topicId, newNoteContent.trim());
      setNewNoteContent('');
      setShowAddNote(null);
      onNotesUpdate();
    } catch (error) {
      console.error('Failed to create note:', error);
    }
  };

  const cancelAddNote = () => {
    setShowAddNote(null);
    setNewNoteContent('');
  };

  if (topicsWithNotes.length === 0) {
    return (
      <Card className="w-full">
        <CardContent className="p-8 text-center">
          <BookOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-medium mb-2">No Notes Yet</h3>
          <p className="text-muted-foreground">
            Upload a file to generate AI-powered notes for this course.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {topicsWithNotes.map(({ topic, notes }) => (
        <Card key={topic.id} className="w-full">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <FileText className="h-5 w-5" />
              <span>{topic.title}</span>
              {topic.chapter_title && (
                <span className="text-sm text-muted-foreground font-normal">
                  ({topic.chapter_title})
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {notes.map((note) => (
              <div key={note.id} className="border rounded-lg p-4">
                {editingNoteId === note.id ? (
                  <div className="space-y-3">
                    <Textarea
                      value={editingContent}
                      onChange={(e) => setEditingContent(e.target.value)}
                      placeholder="Enter note content..."
                      className="min-h-[100px]"
                    />
                    <div className="flex space-x-2">
                      <Button
                        onClick={handleSave}
                        disabled={isSaving}
                        size="sm"
                      >
                        {isSaving ? 'Saving...' : 'Save'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={handleCancel}
                        disabled={isSaving}
                        size="sm"
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="prose prose-sm max-w-none">
                      <pre className="whitespace-pre-wrap font-sans text-sm">{note.content}</pre>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-muted-foreground">
                        Last updated: {new Date(note.updated_at).toLocaleDateString()}
                      </div>
                      <div className="flex space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(note)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(note.id)}
                          disabled={isDeleting === note.id}
                          className="text-red-600 hover:text-red-700"
                        >
                          {isDeleting === note.id ? 'Deleting...' : <Trash2 className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Add Note Button */}
            {showAddNote === topic.id ? (
              <div className="border rounded-lg p-4">
                <Textarea
                  value={newNoteContent}
                  onChange={(e) => setNewNoteContent(e.target.value)}
                  placeholder="Enter new note content..."
                  className="min-h-[100px] mb-3"
                />
                <div className="flex space-x-2">
                  <Button
                    onClick={() => handleAddNote(topic.id)}
                    size="sm"
                  >
                    Add Note
                  </Button>
                  <Button
                    variant="outline"
                    onClick={cancelAddNote}
                    size="sm"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="outline"
                onClick={() => setShowAddNote(topic.id)}
                className="w-full"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Note to {topic.title}
              </Button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
