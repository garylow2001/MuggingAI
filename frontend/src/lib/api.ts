const API_BASE_URL = "http://localhost:8000/api";

// Types
export interface Course {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CourseCreate {
  name: string;
  description?: string;
}

export interface CourseUpdate {
  name?: string;
  description?: string;
}

export interface FileUpload {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  created_at: string;
  chunks_count: number;
}

export interface Topic {
  id: number;
  title: string;
  chapter_title?: string;
  created_at: string;
}

export interface Note {
  id: number;
  content: string;
  topic_id: number;
  course_id: number;
  created_at: string;
  updated_at: string;
}

export interface TopicWithNotes {
  topic: Topic;
  notes: Note[];
}

export interface FileUploadStatusResult {
  file_id?: number;
  filename?: string;
  file_size?: number;
  chunks_created?: number;
  statistics?: {
    total_chunks: number;
    total_words: number;
    average_chunk_size: number;
    unique_chapters: number;
    chapters: string[];
  };
  summaries?: {
    chunk_index?: number;
    file_id?: number;
    summary: string;
  }[];
}
export interface FileUploadStatusResponse {
  job_id: string;
  status: string;
  progress_messages: string[];
  result?: FileUploadStatusResult;
}

export interface UploadJobResponse {
  message: string;
  job_id: string;
}

// API functions
export const api = {
  // Courses
  async getCourses(): Promise<Course[]> {
    const response = await fetch(`${API_BASE_URL}/courses/`);
    if (!response.ok) {
      throw new Error("Failed to fetch courses");
    }
    return response.json();
  },

  async createCourse(course: CourseCreate): Promise<Course> {
    const response = await fetch(`${API_BASE_URL}/courses/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(course),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to create course");
    }
    return response.json();
  },

  async getCourse(courseId: number): Promise<Course> {
    const response = await fetch(`${API_BASE_URL}/courses/${courseId}`);
    if (!response.ok) {
      throw new Error("Failed to fetch course");
    }
    return response.json();
  },

  async updateCourse(courseId: number, course: CourseUpdate): Promise<Course> {
    const response = await fetch(`${API_BASE_URL}/courses/${courseId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(course),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to update course");
    }
    return response.json();
  },

  async deleteCourse(courseId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/courses/${courseId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Failed to delete course");
    }
  },

  // Files
  async uploadFile(courseId: number, file: File): Promise<UploadJobResponse> {
    const formData = new FormData();
    formData.append("file", file);

    console.log("Uploading file:", file.name, "to course:", courseId);
    console.log("API URL:", `${API_BASE_URL}/files/upload/${courseId}`);

    const response = await fetch(`${API_BASE_URL}/files/upload/${courseId}`, {
      method: "POST",
      body: formData,
    });

    console.log("Upload response status:", response.status);

    if (!response.ok) {
      const error = await response.json();
      console.error("Upload error response:", error);
      throw new Error(error.detail || "Failed to upload file");
    }

    const result = await response.json();
    console.log("Upload success:", result);
    return result;
  },

  async getUploadStatus(jobId: string): Promise<FileUploadStatusResponse> {
    const response = await fetch(
      `${API_BASE_URL}/files/upload/status/${jobId}`
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to get upload status");
    }
    return response.json();
  },

  async getCourseFiles(courseId: number): Promise<FileUpload[]> {
    const response = await fetch(`${API_BASE_URL}/files/${courseId}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error("Course not found");
      }
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Failed to fetch course files");
    }
    return response.json();
  },

  async deleteFile(fileId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/files/${fileId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Failed to delete file");
    }
  },

  async generateNotes(
    courseId: number,
    fileId?: number
  ): Promise<{ message: string; notes_generated: number }> {
    const url = fileId
      ? `${API_BASE_URL}/files/generate-notes/${courseId}?file_id=${fileId}`
      : `${API_BASE_URL}/files/generate-notes/${courseId}`;
    const response = await fetch(url, { method: "POST" });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Failed to generate notes");
    }
    return response.json();
  },

  // Notes
  async getCourseNotes(courseId: number): Promise<TopicWithNotes[]> {
    const response = await fetch(`${API_BASE_URL}/notes/course/${courseId}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error("Course not found");
      }
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Failed to fetch course notes");
    }
    return response.json();
  },

  async updateNote(noteId: number, content: string): Promise<Note> {
    const response = await fetch(`${API_BASE_URL}/notes/${noteId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to update note");
    }
    return response.json();
  },

  async createNote(topicId: number, content: string): Promise<Note> {
    const response = await fetch(`${API_BASE_URL}/notes/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ topic_id: topicId, content }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to create note");
    }
    return response.json();
  },

  async deleteNote(noteId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/notes/${noteId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Failed to delete note");
    }
  },
};
