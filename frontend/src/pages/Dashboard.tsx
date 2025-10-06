import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Plus,
  BookOpen,
  FileText,
  Brain,
  ArrowRight,
  Edit,
  Trash2,
} from "lucide-react";
import { CreateCourseModal } from "@/components/CreateCourseModal";
import { api, Course } from "@/lib/api";
import { useNavigate } from "react-router-dom";

export function Dashboard() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      setIsLoading(true);
      const fetchedCourses = await api.getCourses();
      setCourses(fetchedCourses);
    } catch (err) {
      setError("Failed to load courses");
      console.error("Error loading courses:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateCourse = async (name: string, description: string) => {
    try {
      const newCourse = await api.createCourse({ name, description });
      setCourses((prev) => [...prev, newCourse]);
    } catch (err) {
      throw err; // Re-throw to let the modal handle the error
    }
  };

  const handleDeleteCourse = async (courseId: number) => {
    if (
      !confirm(
        "Are you sure you want to delete this course? This action cannot be undone."
      )
    ) {
      return;
    }

    try {
      await api.deleteCourse(courseId);
      setCourses((prev) => prev.filter((course) => course.id !== courseId));
    } catch (err) {
      alert("Failed to delete course");
      console.error("Error deleting course:", err);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStepTitle = (step: number) => {
    const titles = {
      1: "Create Course",
      2: "Upload Files",
      3: "Generate Learning Content",
      4: "Study Mode",
    };
    return titles[step as keyof typeof titles];
  };

  const getStepDescription = (step: number) => {
    const descriptions = {
      1: "Start by creating a new course to organize your learning materials",
      2: "Upload your PDFs, DOCX files, or text documents to process",
      3: "Let AI create summarized notes, key points, and interactive quizzes",
      4: "Study with AI-generated content and test your knowledge",
    };
    return descriptions[step as keyof typeof descriptions];
  };

  const getStepIcon = (step: number) => {
    const icons = {
      1: BookOpen,
      2: FileText,
      3: Brain,
      4: BookOpen,
    };
    const Icon = icons[step as keyof typeof icons];
    return <Icon className="h-6 w-6 text-primary" />;
  };

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-foreground">
          Welcome to MindCrush
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Transform your lengthy educational materials into digestible,
          interactive learning experiences with AI.
        </p>
      </div>

      {/* Step-by-Step Flow */}
      <div className="space-y-6">
        <h2 className="text-2xl font-semibold text-center">How It Works</h2>

        <div className="flex flex-col lg:flex-row items-center justify-center gap-4">
          {[1, 2, 3, 4].map((step, index) => (
            <React.Fragment key={step}>
              <Card className="text-center w-full max-w-xs">
                <CardHeader className="pb-3">
                  <div className="flex justify-center mb-3">
                    {getStepIcon(step)}
                  </div>
                  <CardTitle className="text-lg">
                    {getStepTitle(step)}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {getStepDescription(step)}
                  </p>
                </CardContent>
              </Card>

              {/* Arrow between cards (except after the last card) */}
              {index < 3 && (
                <div className="hidden lg:flex items-center">
                  <ArrowRight className="h-6 w-6 text-muted-foreground" />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Create Course Button */}
      <div className="text-center">
        <Button
          onClick={() => setIsCreateModalOpen(true)}
          size="lg"
          className="px-8 py-6 text-lg"
        >
          <Plus className="h-5 w-5 mr-2" />
          Create Course
        </Button>
      </div>

      {/* Courses Section */}
      <Card>
        <CardHeader>
          <CardTitle>Your Courses</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">Loading courses...</p>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-600">{error}</p>
              <Button onClick={loadCourses} variant="outline" className="mt-2">
                Retry
              </Button>
            </div>
          ) : courses.length === 0 ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                <BookOpen className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground text-lg">No courses yet</p>
              <p className="text-sm text-muted-foreground mt-1 mb-4">
                Create your first course to get started
              </p>
              <Button onClick={() => setIsCreateModalOpen(true)} size="lg">
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Course
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {courses.map((course) => (
                <Card
                  key={course.id}
                  className="hover:shadow-md transition-shadow cursor-pointer group"
                  onClick={() => navigate(`/course/${course.id}`)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-lg group-hover:text-primary transition-colors">
                        {course.name}
                      </CardTitle>
                      <div className="flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            // TODO: Implement edit functionality
                          }}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteCourse(course.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {course.description && (
                      <p className="text-sm text-muted-foreground mb-3">
                        {course.description}
                      </p>
                    )}
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Created: {formatDate(course.created_at)}</span>
                      <span>Updated: {formatDate(course.updated_at)}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Course Modal */}
      <CreateCourseModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateCourse}
      />
    </div>
  );
}
