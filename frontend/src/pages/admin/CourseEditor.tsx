import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Code, Trash2, Edit3 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { API_BASE_URL } from "../../config";
import ExercisePreview from '../../components/ExercisePreview';

interface Exercise {
    id: number;
    title: string;
    description: string;
    initial_code: string;
    test_code: string;
    slug: string;
    language: string;
    passing_rule?: string;
}

interface Course {
    id: number;
    title: string;
    slug: string;
    description: string;
    exercises: Exercise[];
}

export default function CourseEditor() {
    const { id } = useParams();
    const [course, setCourse] = useState<Course | null>(null);
    const [previewExercise, setPreviewExercise] = useState<Exercise | null>(null);
    const [isCreating, setIsCreating] = useState(false);
    const { token } = useAuth();

    const fetchCourse = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/courses/${id}`);
            if (res.ok) {
                const data = await res.json();
                setCourse(data);
            }
        } catch (err) {
            console.error(err);
        }
    }

    useEffect(() => {
        if (id) fetchCourse();
    }, [id]);

    const handleCreateExercise = () => {
        setPreviewExercise({
            id: 0,
            title: "New Exercise",
            description: "# New Exercise\n\nWrite a function...",
            initial_code: "def solution():\n    pass",
            test_code: "def test_solution():\n    assert solution() is None",
            slug: `exercise-${Date.now()}`,
            language: "python",
            passing_rule: "tests_pass"
        });
        setIsCreating(true);
    };

    const handleEditExercise = (ex: Exercise) => {
        setPreviewExercise(ex);
        setIsCreating(false);
    };

    const handleDeleteExercise = async (exerciseId: number) => {
        if (!course || !confirm("Are you sure you want to delete this exercise?")) return;

        try {
            const res = await fetch(`${API_BASE_URL}/courses/${course.id}/exercises/${exerciseId}`, {
                method: "DELETE",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            if (res.ok) {
                fetchCourse();
            } else {
                alert("Failed to delete exercise");
            }
        } catch (err) {
            console.error(err);
        }
    }

    if (!course) return <div className="p-8 text-slate-400">Loading course...</div>;

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-8">
            <div className="max-w-4xl mx-auto">
                <Link to="/admin" className="flex items-center gap-2 text-slate-400 hover:text-white mb-6 transition-colors">
                    <ArrowLeft size={20} /> Back to Dashboard
                </Link>

                <header className="mb-8 border-b border-slate-800 pb-6 flex justify-between items-end">
                    <div>
                        <h1 className="text-3xl font-bold mb-2">{course.title}</h1>
                        <p className="text-slate-400 font-mono text-sm">{course.slug}</p>
                    </div>
                    <button
                        onClick={handleCreateExercise}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                    >
                        <Plus size={20} /> Add Exercise
                    </button>
                </header>

                {/* Exercise List */}
                <div className="space-y-4">
                    <h2 className="text-xl font-semibold flex items-center gap-2">
                        <Code size={20} className="text-blue-500" /> Exercises
                    </h2>
                    <div className="space-y-3">
                        {course.exercises.map(ex => (
                            <div key={ex.id} className="p-4 bg-slate-900 rounded-lg border border-slate-800 hover:border-slate-700 transition-colors flex justify-between items-center group">
                                <div>
                                    <h3 className="font-medium text-lg">{ex.title}</h3>
                                    <div className="flex items-center gap-3 mt-1">
                                        <p className="text-xs text-slate-500 font-mono">{ex.slug}</p>
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                                            {ex.language}
                                        </span>
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                                            {ex.passing_rule || "tests_pass"}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => handleEditExercise(ex)}
                                        className="p-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all"
                                        title="Edit Exercise"
                                    >
                                        <Edit3 size={18} />
                                    </button>
                                    <button
                                        onClick={() => handleDeleteExercise(ex.id)}
                                        className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                                        title="Delete Exercise"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </div>
                            </div>
                        ))}
                        {course.exercises.length === 0 && (
                            <div className="p-8 text-center text-slate-500 text-sm italic bg-slate-900/50 rounded-lg border border-slate-800 border-dashed">
                                No exercises yet. Click "Add Exercise" to create one.
                            </div>
                        )}
                    </div>
                </div>

                {/* Exercise Preview Modal */}
                {previewExercise && (
                    <ExercisePreview
                        title={previewExercise.title}
                        description={previewExercise.description}
                        initialCode={previewExercise.initial_code}
                        testCode={previewExercise.test_code}
                        language={previewExercise.language || 'python'}
                        passingRule={previewExercise.passing_rule || 'tests_pass'}
                        onClose={() => setPreviewExercise(null)}
                        onSave={async (data) => {
                            try {
                                const url = isCreating
                                    ? `${API_BASE_URL}/courses/${course.id}/exercises/`
                                    : `${API_BASE_URL}/courses/${course.id}/exercises/${previewExercise.id}`;

                                const method = isCreating ? "POST" : "PUT";

                                const res = await fetch(url, {
                                    method: method,
                                    headers: {
                                        'Content-Type': 'application/json',
                                        'Authorization': `Bearer ${token}`
                                    },
                                    body: JSON.stringify({
                                        title: isCreating ? `New Exercise ${course.exercises.length + 1}` : previewExercise.title, // Can be improved
                                        slug: isCreating ? `exercise-${Date.now()}` : previewExercise.slug,
                                        description: data.description,
                                        initial_code: data.initialCode,
                                        test_code: data.testCode,
                                        language: previewExercise.language,
                                        passing_rule: data.passingRule,
                                        course_id: course.id
                                    })
                                });

                                if (res.ok) {
                                    fetchCourse();
                                    setPreviewExercise(null);
                                } else {
                                    const errorData = await res.json();
                                    alert(`Failed to save: ${errorData.detail || 'Unknown error'}`);
                                }
                            } catch (err) {
                                console.error(err);
                                alert('Network error while saving');
                            }
                        }}
                    />
                )}
            </div>
        </div>
    );
}
