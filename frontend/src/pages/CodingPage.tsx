import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import MarkdownViewer from '../components/MarkdownViewer';
import { CodeEditor } from '../components/CodeEditor';
import { Play, RotateCw, ChevronLeft, ChevronRight, BookOpen, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import confetti from 'canvas-confetti';

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
    exercises: Exercise[];
}

export default function CodingPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [course, setCourse] = useState<Course | null>(null);
    const [currentExerciseIndex, setCurrentExerciseIndex] = useState(0);

    const [code, setCode] = useState<string>("");
    const [output, setOutput] = useState<string>("");
    const [isRunning, setIsRunning] = useState(false);
    const { token, logout, isAuthenticated } = useAuth();

    useEffect(() => {
        if (!isAuthenticated) {
            navigate('/login');
        }
    }, [isAuthenticated, navigate]);

    // Fetch Course Data
    useEffect(() => {
        const fetchCourse = async () => {
            try {
                // Default to course ID 1 if no ID provided (or handle "No courses" state)
                const courseId = id || "1";
                const res = await fetch(`http://localhost:8000/courses/${courseId}`);
                if (res.ok) {
                    const data = await res.json();
                    setCourse(data);

                    // Initialize code if exercises exist
                    if (data.exercises && data.exercises.length > 0) {
                        setCode(data.exercises[0].initial_code);
                    }
                } else {
                    console.error("Course not found");
                }
            } catch (err) {
                console.error(err);
            }
        }
        fetchCourse();
    }, [id]);

    // Handle Exercise Change
    const exercise = course?.exercises[currentExerciseIndex];

    useEffect(() => {
        if (exercise) {
            setCode(exercise.initial_code);
            setOutput("");
        }
    }, [exercise]);

    const handleRun = async () => {
        if (!exercise) return;

        setIsRunning(true);
        setOutput("Running...");

        try {
            const response = await fetch('http://localhost:8000/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    code: code + "\n\n" + exercise.test_code
                })
            });

            const data = await response.json();

            if (data.exit_code === 0) {
                setOutput(data.stdout || "Success!");
                confetti({
                    particleCount: 100,
                    spread: 70,
                    origin: { y: 0.6 }
                });
            } else {
                const errorMsg = data.stderr ? `Error:\n${data.stderr}` : "";
                const outputMsg = data.stdout ? `\nOutput:\n${data.stdout}` : "";
                setOutput(`${errorMsg}${outputMsg}`.trim() || `Process exited with code ${data.exit_code}`);
            }
        } catch (e) {
            setOutput("Failed to connect to execution server.");
        } finally {
            setIsRunning(false);
        }
    };

    if (!course) {
        return (
            <div className="flex h-screen w-full bg-slate-950 items-center justify-center text-slate-400">
                <div className="text-center">
                    <h2 className="text-xl font-semibold mb-2">Welcome to Code App</h2>
                    <p className="mb-4">Please go to Admin Panel to create a course first.</p>
                    <button onClick={() => navigate('/admin')} className="text-blue-400 hover:underline">Go to Admin</button>
                </div>
            </div>
        );
    }

    if (course.exercises.length === 0) {
        return (
            <div className="flex h-screen w-full bg-slate-950 items-center justify-center text-slate-400">
                <div className="text-center">
                    <h2 className="text-xl font-semibold mb-2">{course.title}</h2>
                    <p>No exercises added yet.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-screen w-full bg-slate-950 text-slate-100 overflow-hidden font-sans">

            {/* Sidebar  */}
            <div className="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 gap-4">
                <div
                    className="p-2 bg-blue-600 rounded-lg shadow-lg shadow-blue-500/20 cursor-pointer hover:bg-blue-500 transition-colors"
                    onClick={() => navigate('/')}
                    title="Back to Courses"
                >
                    <BookOpen size={24} className="text-white" />
                </div>

                {/* Navigation Dots */}
                <div className="flex flex-col gap-2 mt-4">
                    {course.exercises.map((ex, idx) => (
                        <div
                            key={ex.id}
                            onClick={() => setCurrentExerciseIndex(idx)}
                            className={`
                        w-10 h-10 rounded-lg flex items-center justify-center cursor-pointer transition-colors font-bold text-sm
                        ${currentExerciseIndex === idx ? 'bg-slate-700 text-white' : 'hover:bg-slate-800 text-slate-400'}
                    `}
                        >
                            {idx + 1}
                        </div>
                    ))}
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">

                {/* Header */}
                <header className="h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <h1 className="font-semibold text-lg tracking-tight text-white">{exercise?.title}</h1>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">Python</span>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setCurrentExerciseIndex(Math.max(0, currentExerciseIndex - 1))}
                            disabled={currentExerciseIndex === 0}
                            className="p-2 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronLeft size={20} />
                        </button>
                        <span className="text-sm text-slate-400">
                            {currentExerciseIndex + 1} / {course.exercises.length}
                        </span>
                        <button
                            onClick={() => setCurrentExerciseIndex(Math.min(course.exercises.length - 1, currentExerciseIndex + 1))}
                            disabled={currentExerciseIndex === course.exercises.length - 1}
                            className="p-2 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronRight size={20} />
                        </button>
                        <div className="w-px h-6 bg-slate-800 mx-2" />
                        <button
                            onClick={logout}
                            className="p-2 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 transition-colors"
                            title="Sign Out"
                        >
                            <LogOut size={20} />
                        </button>
                    </div>
                </header>

                {/* Split View */}
                <div className="flex-1 flex overflow-hidden">

                    {/* Left: Instructions */}
                    <div className="w-1/2 flex flex-col border-r border-slate-800 bg-slate-950/50">
                        <div className="flex-1 overflow-y-auto custom-scrollbar">
                            {exercise && <MarkdownViewer content={exercise.description} />}
                        </div>
                    </div>

                    {/* Right: Code & Output */}
                    <div className="w-1/2 flex flex-col bg-[#1e1e1e]">
                        {/* Editor Toolbar */}
                        <div className="h-10 border-b border-[#333] flex items-center px-4 justify-between bg-[#252526]">
                            <div className="flex items-center gap-2 text-sm text-slate-400">
                                <span className="flex items-center gap-1.5 px-3 py-1 bg-[#1e1e1e] rounded text-slate-200 border border-[#333]">
                                    📄 main.py
                                </span>
                            </div>
                        </div>

                        {/* Editor */}
                        <div className="flex-1 min-h-0">
                            <CodeEditor
                                code={code}
                                onChange={(val) => setCode(val || "")}
                                language="python"
                            />
                        </div>

                        {/* Output / Console Panel */}
                        <div className="h-1/3 border-t border-[#333] flex flex-col bg-[#1e1e1e]">
                            <div className="h-10 flex items-center justify-between px-4 border-b border-[#333] bg-[#252526]">
                                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Console Output</span>

                                <div className="flex gap-2">
                                    <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium rounded transition-colors">
                                        <RotateCw size={14} /> Reset
                                    </button>
                                    <button
                                        onClick={handleRun}
                                        disabled={isRunning}
                                        className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded shadow shadow-blue-900/20 transition-all disabled:opacity-50"
                                    >
                                        <Play size={14} fill="currentColor" /> {isRunning ? 'Running...' : 'Run Code'}
                                    </button>
                                </div>
                            </div>
                            <div className="flex-1 p-4 font-mono text-sm overflow-auto custom-scrollbar">
                                {output ? (
                                    <pre className="text-slate-300 whitespace-pre-wrap">{output}</pre>
                                ) : (
                                    <span className="text-slate-600 italic">Run your code to see output...</span>
                                )}
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}
