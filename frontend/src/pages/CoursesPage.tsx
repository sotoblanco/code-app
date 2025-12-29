import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Terminal, ChevronRight, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface Course {
    id: number;
    title: string;
    description?: string; // Assuming description might be added later, or just title for now
    exercises: any[]; // We just need the count
}

export default function CoursesPage() {
    const [courses, setCourses] = useState<Course[]>([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    const { logout } = useAuth();

    useEffect(() => {
        const fetchCourses = async () => {
            try {
                const res = await fetch('http://localhost:8000/courses/');
                if (res.ok) {
                    const data = await res.json();
                    setCourses(data);
                }
            } catch (err) {
                console.error("Failed to fetch courses", err);
            } finally {
                setLoading(false);
            }
        };

        fetchCourses();
    }, []);

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col">
            {/* Header */}
            <header className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-8">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-600 rounded-lg">
                        <Terminal size={20} className="text-white" />
                    </div>
                    <h1 className="font-bold text-xl tracking-tight">Code App</h1>
                </div>
                <button
                    onClick={logout}
                    className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
                >
                    <LogOut size={18} />
                    <span className="text-sm font-medium">Sign Out</span>
                </button>
            </header>

            {/* Main Content */}
            <main className="flex-1 max-w-5xl mx-auto w-full p-8">
                <div className="mb-8">
                    <h2 className="text-3xl font-bold mb-2">Available Courses</h2>
                    <p className="text-slate-400">Select a course to start coding.</p>
                </div>

                {loading ? (
                    <div className="flex justify-center py-20">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {courses.length === 0 ? (
                            <div className="col-span-full text-center py-20 text-slate-500 bg-slate-900/50 rounded-xl border border-dashed border-slate-800">
                                <p>No courses available right now.</p>
                            </div>
                        ) : (
                            courses.map((course) => (
                                <div
                                    key={course.id}
                                    className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-blue-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 group cursor-pointer flex flex-col"
                                    onClick={() => navigate(`/course/${course.id}`)}
                                >
                                    <div className="h-2 bg-gradient-to-r from-blue-600 to-indigo-600" />
                                    <div className="p-6 flex-1 flex flex-col">
                                        <div className="flex items-start justify-between mb-4">
                                            <div className="p-3 bg-slate-800 rounded-lg group-hover:bg-blue-500/10 group-hover:text-blue-400 transition-colors">
                                                <BookOpen size={24} />
                                            </div>
                                        </div>

                                        <h3 className="text-xl font-bold mb-2 group-hover:text-blue-400 transition-colors">
                                            {course.title}
                                        </h3>

                                        {course.description && (
                                            <p className="text-slate-400 text-sm mb-4 line-clamp-2">
                                                {course.description}
                                            </p>
                                        )}

                                        <div className="mt-auto pt-4 flex items-center justify-between text-sm text-slate-400">
                                            <span>
                                                {course.exercises?.length || 0} Exercises
                                            </span>
                                            <span className="flex items-center gap-1 group-hover:translate-x-1 transition-transform text-blue-400 opacity-0 group-hover:opacity-100 font-medium">
                                                Start <ChevronRight size={16} />
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
