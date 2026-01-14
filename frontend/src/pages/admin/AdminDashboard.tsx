import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Book, LayoutGrid, Trash2, MessageSquare, X, Send, Loader2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { API_BASE_URL } from "../../config";
import { discussImplementation } from '../../services/aiService';

interface Course {
    id: number;
    title: string;
    description: string;
    slug: string;
    is_published: boolean;
}

export default function AdminDashboard() {
    const [courses, setCourses] = useState<Course[]>([]);
    const [newCourseTitle, setNewCourseTitle] = useState("");
    const [newCourseSlug, setNewCourseSlug] = useState("");

    // AI Discussion State
    const [showChat, setShowChat] = useState(false);
    const [chatMessage, setChatMessage] = useState("");
    const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'ai', text: string }[]>([]);
    const [isChatLoading, setIsChatLoading] = useState(false);

    const { token } = useAuth();

    const fetchCourses = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/courses/`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setCourses(data);
            }
        } catch (err) {
            console.error("Failed to fetch courses", err);
        }
    }

    useEffect(() => {
        fetchCourses();
    }, []);

    const [isCreating, setIsCreating] = useState(false);

    const handleCreateCourse = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsCreating(true);
        try {
            const res = await fetch(`${API_BASE_URL}/courses/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({
                    title: newCourseTitle,
                    slug: newCourseSlug,
                    description: "New course description",
                    is_published: false
                })
            });
            if (res.ok) {
                setNewCourseTitle("");
                setNewCourseSlug("");
                fetchCourses();
                alert("Course created successfully!");
            } else {
                const data = await res.json();
                alert(`Failed to create course: ${data.detail || "Unknown error"}`);
            }
        } catch (err) {
            console.error("Failed to create course", err);
            alert("Network error. Check console.");
        } finally {
            setIsCreating(false);
        }
    }

    const handleDeleteCourse = async (courseId: number) => {
        if (!confirm("Are you sure you want to delete this course?")) return;

        try {
            const res = await fetch(`${API_BASE_URL}/courses/${courseId}`, {
                method: "DELETE",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            if (res.ok) {
                fetchCourses();
            } else {
                const data = await res.json();
                alert(`Failed to delete: ${data.detail || res.statusText}`);
            }
        } catch (err) {
            console.error("Failed to delete course", err);
            alert("Network error. Check console.");
        }
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-8">
            <div className="max-w-4xl mx-auto">
                <header className="mb-8 flex items-center gap-3 border-b border-slate-800 pb-6">
                    <div className="p-2 bg-blue-600 rounded-lg">
                        <LayoutGrid size={24} className="text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
                        <p className="text-slate-400">Manage courses and exercises</p>
                    </div>
                </header>

                {/* Create Course Form */}
                <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 mb-8">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Plus size={20} className="text-blue-500" /> Create New Course
                    </h2>
                    <form onSubmit={handleCreateCourse} className="flex gap-4 items-end">
                        <div className="flex-1">
                            <label className="block text-sm font-medium text-slate-400 mb-1">Title</label>
                            <input
                                type="text"
                                required
                                value={newCourseTitle}
                                onChange={e => setNewCourseTitle(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none transition-colors"
                                placeholder="e.g. Advanced Python"
                            />
                        </div>
                        <div className="flex-1">
                            <label className="block text-sm font-medium text-slate-400 mb-1">Slug</label>
                            <input
                                type="text"
                                required
                                value={newCourseSlug}
                                onChange={e => setNewCourseSlug(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none transition-colors"
                                placeholder="e.g. advanced-python"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={isCreating}
                            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                        >
                            {isCreating && <Loader2 size={16} className="animate-spin" />}
                            {isCreating ? "Creating..." : "Create"}
                        </button>
                    </form>
                </div>

                {/* Course List */}
                <div className="grid gap-4">
                    {courses.map(course => (
                        <div key={course.id} className="bg-slate-900 p-5 rounded-xl border border-slate-800 flex justify-between items-center hover:border-slate-700 transition-colors">
                            <div className="flex items-center gap-4">
                                <div className="p-3 bg-slate-800 rounded-lg text-slate-400">
                                    <Book size={20} />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg">{course.title}</h3>
                                    <p className="text-sm text-slate-400 font-mono text-xs mt-0.5">{course.slug}</p>
                                </div>
                            </div>
                            <div className="flex gap-3">
                                <Link to={`/course/${course.id}`} className="px-4 py-2 text-sm text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-colors flex items-center">
                                    View Course
                                </Link>
                                <Link to={`/admin/courses/${course.id}`} className="px-4 py-2 text-sm bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors flex items-center">
                                    Manage Exercises
                                </Link>
                                <button
                                    onClick={() => handleDeleteCourse(course.id)}
                                    className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition-colors"
                                    title="Delete Course"
                                >
                                    <Trash2 size={20} />
                                </button>
                            </div>
                        </div>
                    ))}
                    {courses.length === 0 && (
                        <div className="text-center py-12 text-slate-500 bg-slate-900/50 rounded-xl border border-slate-800 border-dashed">
                            No courses found. Create one above!
                        </div>
                    )}
                </div>

                {/* Floating Chat Button */}
                <button
                    onClick={() => setShowChat(true)}
                    className="fixed bottom-8 right-8 bg-purple-600 hover:bg-purple-500 text-white p-4 rounded-full shadow-lg transition-transform hover:scale-110"
                    title="Discuss Implementation Ideas"
                >
                    <MessageSquare size={24} />
                </button>

                {/* Chat Modal/Panel */}
                {showChat && (
                    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                        <div className="bg-slate-900 w-full max-w-lg rounded-xl border border-slate-700 shadow-2xl flex flex-col max-h-[80vh]">
                            <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800 rounded-t-xl">
                                <h3 className="font-semibold text-lg flex items-center gap-2">
                                    <MessageSquare size={18} className="text-purple-400" />
                                    Implementation Discussion
                                </h3>
                                <button onClick={() => setShowChat(false)} className="text-slate-400 hover:text-white">
                                    <X size={20} />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                {chatHistory.length === 0 && (
                                    <div className="text-center text-slate-500 py-8">
                                        <p>Ask me anything about implementing your coding exercises!</p>
                                    </div>
                                )}
                                {chatHistory.map((msg, idx) => (
                                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user'
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-slate-800 text-slate-200 border border-slate-700'
                                            }`}>
                                            <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                                        </div>
                                    </div>
                                ))}
                                {isChatLoading && (
                                    <div className="flex justify-start">
                                        <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                                            <Loader2 size={16} className="animate-spin text-purple-400" />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="p-4 border-t border-slate-700 bg-slate-800 rounded-b-xl">
                                <form
                                    onSubmit={async (e) => {
                                        e.preventDefault();
                                        if (!chatMessage.trim()) return;

                                        const msg = chatMessage;
                                        setChatMessage("");
                                        setChatHistory(prev => [...prev, { role: 'user', text: msg }]);
                                        setIsChatLoading(true);

                                        try {
                                            const res = await discussImplementation(msg);
                                            setChatHistory(prev => [...prev, { role: 'ai', text: res.response }]);
                                        } catch (err) {
                                            console.error(err);
                                            setChatHistory(prev => [...prev, { role: 'ai', text: "Sorry, I encountered an error." }]);
                                        } finally {
                                            setIsChatLoading(false);
                                        }
                                    }}
                                    className="flex gap-2"
                                >
                                    <input
                                        className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-purple-500 outline-none"
                                        placeholder="Type your question..."
                                        value={chatMessage}
                                        onChange={e => setChatMessage(e.target.value)}
                                    />
                                    <button
                                        type="submit"
                                        disabled={isChatLoading || !chatMessage.trim()}
                                        className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white p-2 rounded-lg transition-colors"
                                    >
                                        <Send size={20} />
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
}
