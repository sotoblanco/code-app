import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Code, Save, Trash2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface Exercise {
    id: number;
    title: string;
    description: string;
    initial_code: string;
    test_code: string;
    slug: string;
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

    // New Exercise Form State
    const [newExTitle, setNewExTitle] = useState("");
    const [newExSlug, setNewExSlug] = useState("");
    const [newExDesc, setNewExDesc] = useState("# Instructions\n\nWrite a function...");
    const [newExCode, setNewExCode] = useState("def solution():\n    pass");
    const [newExTest, setNewExTest] = useState("def test_solution():\n    assert solution() is None");
    const { token } = useAuth();

    const fetchCourse = async () => {
        try {
            const res = await fetch(`http://localhost:8000/courses/${id}`);
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

    const handleAddExercise = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!course) return;

        try {
            const res = await fetch(`http://localhost:8000/courses/${course.id}/exercises/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({
                    title: newExTitle,
                    slug: newExSlug,
                    description: newExDesc,
                    initial_code: newExCode,
                    test_code: newExTest,
                    course_id: course.id
                })
            });

            if (res.ok) {
                // Clear form and refresh
                setNewExTitle("");
                setNewExSlug("");
                fetchCourse();
            }
        } catch (err) {
            console.error(err);
        }
    }


    const handleDeleteExercise = async (exerciseId: number) => {
        if (!course || !confirm("Are you sure you want to delete this exercise?")) return;

        try {
            const res = await fetch(`http://localhost:8000/courses/${course.id}/exercises/${exerciseId}`, {
                method: "DELETE",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            if (res.ok) {
                fetchCourse();
            }
        } catch (err) {
            console.error(err);
        }
    }

    if (!course) return <div className="p-8 text-slate-400">Loading course...</div>;

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-8">
            <div className="max-w-6xl mx-auto">
                <Link to="/admin" className="flex items-center gap-2 text-slate-400 hover:text-white mb-6 transition-colors">
                    <ArrowLeft size={20} /> Back to Dashboard
                </Link>

                <header className="mb-8 border-b border-slate-800 pb-6">
                    <h1 className="text-3xl font-bold mb-2">{course.title}</h1>
                    <p className="text-slate-400 font-mono text-sm">{course.slug}</p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Left: Exercise List */}
                    <div className="lg:col-span-1 space-y-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">
                            <Code size={20} className="text-blue-500" /> Exercises
                        </h2>
                        <div className="space-y-2">
                            {course.exercises.map(ex => (
                                <div key={ex.id} className="p-4 bg-slate-900 rounded-lg border border-slate-800 hover:border-slate-700 transition-colors flex justify-between items-start group">
                                    <div>
                                        <h3 className="font-medium">{ex.title}</h3>
                                        <p className="text-xs text-slate-500 font-mono mt-1">{ex.slug}</p>
                                    </div>
                                    <button
                                        onClick={() => handleDeleteExercise(ex.id)}
                                        className="p-1.5 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                                        title="Delete Exercise"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            ))}
                            {course.exercises.length === 0 && (
                                <div className="p-4 text-center text-slate-500 text-sm italic bg-slate-900/50 rounded-lg border border-slate-800 border-dashed">
                                    No exercises yet.
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right: Add Exercise Form */}
                    <div className="lg:col-span-2 bg-slate-900 rounded-xl border border-slate-800 p-6">
                        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
                            <Plus size={20} className="text-blue-500" /> Add New Exercise
                        </h2>

                        <form onSubmit={handleAddExercise} className="space-y-6">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-1">Title</label>
                                    <input
                                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
                                        value={newExTitle} onChange={e => setNewExTitle(e.target.value)} required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-1">Slug</label>
                                    <input
                                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
                                        value={newExSlug} onChange={e => setNewExSlug(e.target.value)} required
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1">Instructions (Markdown)</label>
                                <textarea
                                    className="w-full h-32 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
                                    value={newExDesc} onChange={e => setNewExDesc(e.target.value)} required
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-1">Initial Code</label>
                                    <textarea
                                        className="w-full h-48 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
                                        value={newExCode} onChange={e => setNewExCode(e.target.value)} required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-1">Test Code (Hidden)</label>
                                    <textarea
                                        className="w-full h-48 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
                                        value={newExTest} onChange={e => setNewExTest(e.target.value)} required
                                    />
                                </div>
                            </div>

                            <div className="flex justify-end pt-4 border-t border-slate-800">
                                <button type="submit" className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-medium transition-colors">
                                    <Save size={18} /> Save Exercise
                                </button>
                            </div>
                        </form>
                    </div>

                </div>
            </div>
        </div>
    );
}
