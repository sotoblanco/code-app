import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import MarkdownViewer from '../components/MarkdownViewer';
import { CodeEditor } from '../components/CodeEditor';
import AIChatPanel from '../components/AIChatPanel';
import DrawingCanvas from '../components/DrawingCanvas';
import { Play, RotateCw, ChevronLeft, ChevronRight, FolderCode, Lightbulb, Link, Trash2, ExternalLink, Send, Sparkles, Compass } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import confetti from 'canvas-confetti';
import { API_BASE_URL, APP_VERSION } from "../config";
import { messageForRunStatus } from '../runErrors';
import { buildTutorContext } from '../tutorContext';
import { testsToRun } from '../testsToRun';
import { Panel, Group, Separator } from "react-resizable-panels";
import { UserMenu } from '../components/UserMenu';
import { WelcomeGate } from '../components/auth/WelcomeGate';
import { fetchSolutionCode } from '../solutionApi';
import { emitLearnerEvent, fetchMyProgress } from '../services/profileService';
import { ShareAchievement } from '../ux-light/components/ShareAchievement';
import { isAuthorRole, studentTestsPlaceholder } from '../testVisibility';
import type { SharePayload } from '../ux-light/shareCard';
import { findLessonPosition, useLessonUrlSync } from '../lessonUrl';
interface Lesson {
    slug: string;
    title: string;
    description: string;
    initial_code: string;
    test_code: string;
    solution_code?: string;
    has_solution?: boolean;
    order: number;
    language: string;
    chapter?: string;
    exercise_type?: "code" | "spreadsheet" | "drawing";
    google_sheet_id?: string;
    copy_on_open?: boolean;
    image_url?: string;
    stroke_color?: string;
    stroke_width?: number;
    skills?: string[];
}

interface Chapter {
    name: string;
    lessons: Lesson[];
}

interface FileCourse {
    slug: string;
    title: string;
    description: string;
    lessons: Lesson[];
    skills?: string[];
}

export default function FileCodingPage({ onSwitchUi }: { onSwitchUi?: () => void }) {
    const { slug, lessonSlug } = useParams();
    const navigate = useNavigate();
    const [course, setCourse] = useState<FileCourse | null>(null);
    const [chapters, setChapters] = useState<Chapter[]>([]);
    const [currentChapterIndex, setCurrentChapterIndex] = useState(0);
    const [currentLessonIndex, setCurrentLessonIndex] = useState(0);
    const [editorTab, setEditorTab] = useState<'main' | 'tests' | 'solution'>('main');
    const [showSolution, setShowSolution] = useState(false);
    const [loadedSolution, setLoadedSolution] = useState('');

    const [code, setCode] = useState<string>("");
    const [output, setOutput] = useState<string>("");
    const [isRunning, setIsRunning] = useState(false);
    const [drawingOutput, setDrawingOutput] = useState<string>("");
    const [isSubmittingDrawing, setIsSubmittingDrawing] = useState(false);
    const [showDrawingSolution, setShowDrawingSolution] = useState(false);
    const drawingCanvasRef = useRef<HTMLCanvasElement | null>(null);
    const { token, isAuthenticated, logout, user } = useAuth();
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
    const [isLearningGuideOpen, setIsLearningGuideOpen] = useState(false);
    const [courseError, setCourseError] = useState<string | null>(null);
    const [userSheetUrl, setUserSheetUrl] = useState<string>("");
    const [sharePayload, setSharePayload] = useState<SharePayload | null>(null);
    const instructionScrollRef = useRef<HTMLDivElement>(null);


    // Extract chapters from lessons
    const extractChapters = (lessons: Lesson[]): Chapter[] => {
        if (lessons.length === 0) return [];

        // Check if lessons have chapter information
        const hasChapters = lessons.some(l => l.chapter);

        if (hasChapters) {
            // Group lessons by chapter
            const chapterMap = new Map<string, Lesson[]>();
            lessons.forEach(lesson => {
                const chapter = lesson.chapter || "default";
                if (!chapterMap.has(chapter)) {
                    chapterMap.set(chapter, []);
                }
                chapterMap.get(chapter)!.push(lesson);
            });

            // Convert to array and sort by chapter name
            return Array.from(chapterMap.entries())
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([name, lessons]) => ({ name, lessons }));
        } else {
            // No chapters, treat all lessons as one group
            return [{ name: "Lessons", lessons }];
        }
    };

    // Fetch Course Data
    useEffect(() => {
        const fetchCourse = async () => {
            if (!isAuthenticated || !token) {
                setIsAuthModalOpen(true);
                return;
            }
            setCourseError(null);
            try {
                const [res, progress] = await Promise.all([
                    fetch(`${API_BASE_URL}/file-courses/${slug}`, {
                        headers: { Authorization: `Bearer ${token}` },
                    }),
                    fetchMyProgress(),
                ]);
                if (res.status === 401) {
                    logout();
                    setIsAuthModalOpen(true);
                    setCourseError('Your session has expired. Please sign in again.');
                    return;
                }
                if (res.ok) {
                    const data = await res.json();
                    const extractedChapters = extractChapters(data.lessons);
                    setCourse(data);
                    setChapters(extractedChapters);

                    // Prefer the lesson named in the URL, else the learner's last lesson, else lesson 1.
                    const courseProgress = progress.find((p) => p.course_slug === slug);
                    const target =
                        findLessonPosition(extractedChapters, lessonSlug) ??
                        findLessonPosition(extractedChapters, courseProgress?.resume_lesson ?? null);
                    if (target) {
                        setCurrentChapterIndex(target.chapterIndex);
                        setCurrentLessonIndex(target.lessonIndex);
                    }
                } else {
                    setCourseError(res.status === 404 ? 'Course not found.' : 'Unable to load this course.');
                }
            } catch (err) {
                console.error(err);
                setCourseError('Unable to connect to the course service.');
            }
        }
        fetchCourse();
    }, [slug, token, isAuthenticated, logout]);

    // Handle Lesson Change
    const currentChapter = chapters[currentChapterIndex];
    const lesson = currentChapter?.lessons[currentLessonIndex];

    useEffect(() => {
        if (lesson && slug) {
            const draftKey = `code_draft_${slug}_${lesson.slug}`;
            const uxKey = `uxlight_code_${slug}_${lesson.slug}`;
            const saved = localStorage.getItem(draftKey) ?? localStorage.getItem(uxKey);
            setCode(saved !== null ? saved : (lesson.initial_code || ""));
            setOutput("");
            setEditorTab('main');
            setShowSolution(false);
            setLoadedSolution('');
            setShowDrawingSolution(false);
            // Load saved spreadsheet URL if any
            const savedUrl = localStorage.getItem(`spreadsheet_copy_${slug}_${lesson.slug}`);
            setUserSheetUrl(savedUrl || "");

            // Record lesson opened in learner profile
            emitLearnerEvent('lesson_opened', {
                course_slug: slug,
                lesson_slug: lesson.slug,
                ui: 'classic',
            });

            // Reset scroll position to top
            if (instructionScrollRef.current) {
                instructionScrollRef.current.scrollTop = 0;
            }
        }
    }, [lesson, slug]);

    const handleCodeChange = (newCode?: string) => {
        const val = newCode || "";
        setCode(val);
        if (slug && lesson) {
            localStorage.setItem(`code_draft_${slug}_${lesson.slug}`, val);
            localStorage.setItem(`uxlight_code_${slug}_${lesson.slug}`, val);
        }
    };

    const handleResetCode = () => {
        if (!lesson || !slug) return;
        if (window.confirm("Are you sure you want to reset your code to the starter code? Current edits will be lost.")) {
            localStorage.removeItem(`code_draft_${slug}_${lesson.slug}`);
            localStorage.removeItem(`uxlight_code_${slug}_${lesson.slug}`);
            setCode(lesson.initial_code || '');
            setOutput('');
            emitLearnerEvent('reset', {
                course_slug: slug,
                lesson_slug: lesson.slug,
            });
        }
    };

    // Save spreadsheet URL when it changes
    useEffect(() => {
        if (lesson && userSheetUrl) {
            localStorage.setItem(`spreadsheet_copy_${slug}_${lesson.slug}`, userSheetUrl);
        } else if (lesson) {
            localStorage.removeItem(`spreadsheet_copy_${slug}_${lesson.slug}`);
        }
    }, [userSheetUrl, lesson, slug]);

    const extractSheetId = (url: string) => {
        const match = url.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
        return match ? match[1] : null;
    };

    const displaySheetId = userSheetUrl ? extractSheetId(userSheetUrl) : lesson?.google_sheet_id;
    const isUsingPersonalCopy = !!(userSheetUrl && extractSheetId(userSheetUrl));
    const sheetMode = 'edit';
    const iframeUrl = displaySheetId
        ? `https://docs.google.com/spreadsheets/d/${displaySheetId}/${sheetMode}?usp=sharing`
        : "";

    const handleRun = async (isSubmit: boolean = false) => {
        if (!lesson) return;

        setIsRunning(true);
        setOutput(isSubmit ? "Running all tests..." : "Running preliminary tests...");

        const headers: HeadersInit = {
            'Content-Type': 'application/json',
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/run`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    code,
                    test_code: testsToRun(lesson.test_code, lesson.language || 'python', isSubmit),
                    language: lesson.language || "python"
                })
            });

            const runError = messageForRunStatus(response.status);
            if (runError) {
                if (response.status === 401) {
                    logout();
                    setIsAuthModalOpen(true);
                }
                setOutput(runError);
                return;
            }

            const data = await response.json();

            if (data.exit_code === 0) {
                setOutput(data.stdout || "Success!");
                if (isSubmit) {
                    confetti({
                        particleCount: 100,
                        spread: 70,
                        origin: { y: 0.6 }
                    });
                    if (course && lesson) {
                        emitLearnerEvent('lesson_passed', {
                            course_slug: slug,
                            lesson_slug: lesson.slug,
                            modality: 'code',
                            xp: 35,
                        });
                        setSharePayload({
                            kind: 'lesson',
                            courseTitle: course.title,
                            lessonTitle: lesson.title,
                            skills: lesson.skills?.length ? lesson.skills : course.skills || [],
                        });
                    }
                }
            } else {
                const errorMsg = data.stderr ? `Error:\n${data.stderr}` : "";
                const outputMsg = data.stdout ? `\nOutput:\n${data.stdout}` : "";
                setOutput(`${errorMsg}${outputMsg}`.trim() || `Process exited with code ${data.exit_code}`);
            }
            } catch {
            setOutput("Failed to connect to execution server.");
        } finally {
            setIsRunning(false);
        }
    };

    const handleDrawingSubmit = async () => {
        if (!lesson || !drawingCanvasRef.current) return;
        setIsSubmittingDrawing(true);
        setDrawingOutput('Evaluating your drawing...');
        try {
            const imageData = drawingCanvasRef.current.toDataURL('image/png');
            const response = await fetch(
                `${API_BASE_URL}/file-courses/${slug}/${lesson.slug}/submit-drawing`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(token ? { Authorization: `Bearer ${token}` } : {}),
                    },
                    body: JSON.stringify({ image_data: imageData }),
                }
            );
            if (response.status === 401) {
                logout();
                setIsAuthModalOpen(true);
                setDrawingOutput('Your session has expired. Please sign in again.');
                return;
            }
            const data = await response.json();
            setDrawingOutput(data.message);
            if (data.passed) {
                confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
                if (course && lesson) {
                    setSharePayload({
                        kind: 'lesson',
                        courseTitle: course.title,
                        lessonTitle: lesson.title,
                        skills: lesson.skills?.length ? lesson.skills : course.skills || [],
                    });
                }
            }
        } catch {
            setDrawingOutput('Failed to submit drawing.');
        } finally {
            setIsSubmittingDrawing(false);
        }
    };

    const selectLesson = useCallback((chapterIndex: number, lessonIndex: number) => {
        setCurrentChapterIndex(chapterIndex);
        setCurrentLessonIndex(lessonIndex);
    }, []);

    useLessonUrlSync({
        courseSlug: slug,
        chapters,
        currentChapterIndex,
        currentLessonIndex,
        onSelectLesson: selectLesson,
    });

    if (!course || chapters.length === 0) {
        return (
            <div className="flex h-screen w-full bg-slate-950 items-center justify-center text-slate-400">
                <div className="text-center">
                    {courseError ? (
                        <>
                            <p className="mb-4 text-rose-400">{courseError}</p>
                            {!isAuthenticated && (
                                <button
                                    onClick={() => setIsAuthModalOpen(true)}
                                    className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
                                >
                                    Sign in
                                </button>
                            )}
                        </>
                    ) : (
                        <>
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mx-auto mb-4"></div>
                            <p>Loading course...</p>
                        </>
                    )}
                </div>
                <WelcomeGate isOpen={isAuthModalOpen} onClose={() => navigate('/')} />
            </div>
        );
    }

    if (!currentChapter || currentChapter.lessons.length === 0) {
        return (
            <div className="flex h-screen w-full bg-slate-950 items-center justify-center text-slate-400">
                <div className="text-center">
                    <h2 className="text-xl font-semibold mb-2">{course.title}</h2>
                    <p>No lessons added yet.</p>
                </div>
            </div>
        );
    }

    const currentLang = lesson?.language || "python";
    const mainFilename = currentLang === "rust" ? "main.rs" : "main.py";
    const testsFilename = currentLang === "rust" ? "tests.rs" : "tests.py";
    // Students never see the answer-key assertions; authors (admins) still can.
    const testsEditorCode = isAuthorRole(user?.role)
        ? (lesson?.test_code || "")
        : studentTestsPlaceholder(currentLang);

    return (
        <div className="flex h-screen w-full bg-slate-950 text-slate-100 overflow-hidden font-sans">
            {/* Sidebar */}
            <div className="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 gap-4">
                <div
                    className="p-2 bg-emerald-600 rounded-lg shadow-lg shadow-emerald-500/20 cursor-pointer hover:bg-emerald-500 transition-colors"
                    onClick={() => navigate('/')}
                    title="Back to Courses"
                >
                    <FolderCode size={24} className="text-white" />
                </div>

                {/* Chapter Navigation */}
                <div className="flex flex-col gap-2 mt-4 w-full items-center">
                    {/* Previous Chapter Button */}
                    {chapters.length > 1 && (
                        <button
                            onClick={() => {
                                setCurrentChapterIndex(Math.max(0, currentChapterIndex - 1));
                                setCurrentLessonIndex(0);
                            }}
                            disabled={currentChapterIndex === 0}
                            className="p-2 rounded text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            title="Previous Chapter"
                        >
                            <ChevronLeft size={16} />
                        </button>
                    )}

                    {/* Chapter Name */}
                    {chapters.length > 1 && currentChapter && (
                        <div className="text-xs font-semibold text-slate-400 text-center px-2 py-1">
                            {currentChapter.name.replace('chapter', 'Ch ')}
                        </div>
                    )}

                    {/* Lesson Dots for Current Chapter */}
                    <div className="flex flex-col gap-2">
                        {currentChapter?.lessons.map((les, idx) => (
                            <div
                                key={les.slug}
                                onClick={() => setCurrentLessonIndex(idx)}
                                className={`
                            w-10 h-10 rounded-lg flex items-center justify-center cursor-pointer transition-colors font-bold text-sm
                            ${currentLessonIndex === idx ? 'bg-slate-700 text-white' : 'hover:bg-slate-800 text-slate-400'}
                        `}
                                title={les.title}
                            >
                                {idx + 1}
                            </div>
                        ))}
                    </div>

                    {/* Next Chapter Button */}
                    {chapters.length > 1 && (
                        <button
                            onClick={() => {
                                setCurrentChapterIndex(Math.min(chapters.length - 1, currentChapterIndex + 1));
                                setCurrentLessonIndex(0);
                            }}
                            disabled={currentChapterIndex === chapters.length - 1}
                            className="p-2 rounded text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors mt-2"
                            title="Next Chapter"
                        >
                            <ChevronRight size={16} />
                        </button>
                    )}
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">

                {/* Header */}
                <header className="h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <h1 className="font-semibold text-lg tracking-tight text-white">{lesson?.title}</h1>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            {currentLang === 'rust' ? 'Rust' : 'Python'}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
                            File Course
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => {
                                if (currentLessonIndex > 0) {
                                    setCurrentLessonIndex(currentLessonIndex - 1);
                                } else if (currentChapterIndex > 0) {
                                    setCurrentChapterIndex(currentChapterIndex - 1);
                                    const prevChapter = chapters[currentChapterIndex - 1];
                                    setCurrentLessonIndex(prevChapter.lessons.length - 1);
                                }
                            }}
                            disabled={currentChapterIndex === 0 && currentLessonIndex === 0}
                            className="p-2 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronLeft size={20} />
                        </button>
                        <span className="text-sm text-slate-400">
                            {currentChapter ? (
                                <>
                                    {currentLessonIndex + 1} / {currentChapter.lessons.length}
                                    {chapters.length > 1 && ` • ${currentChapter.name.replace('chapter', 'Ch ')}`}
                                </>
                            ) : (
                                '0 / 0'
                            )}
                        </span>
                        <button
                            onClick={() => {
                                if (currentChapter && currentLessonIndex < currentChapter.lessons.length - 1) {
                                    setCurrentLessonIndex(currentLessonIndex + 1);
                                } else if (currentChapterIndex < chapters.length - 1) {
                                    setCurrentChapterIndex(currentChapterIndex + 1);
                                    setCurrentLessonIndex(0);
                                }
                            }}
                            disabled={currentChapterIndex === chapters.length - 1 && currentChapter && currentLessonIndex === currentChapter.lessons.length - 1}
                            className="p-2 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronRight size={20} />
                        </button>
                        <div className="w-px h-6 bg-slate-800 mx-2" />
                        <button
                            onClick={() => setIsLearningGuideOpen(true)}
                            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800 border border-slate-700 transition-colors"
                            title="Learning Guide & AI Setup"
                        >
                            <Compass size={14} className="text-emerald-400" />
                            <span className="hidden md:inline">Learning Guide</span>
                        </button>
                        {onSwitchUi && (
                            <button
                                onClick={onSwitchUi}
                                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800 border border-slate-700 transition-colors"
                                title="Switch to the UX Light interface"
                            >
                                <Sparkles size={15} className="text-emerald-400" />
                                <span className="hidden md:inline">UX Light</span>
                            </button>
                        )}
                        {isAuthenticated ? (
                            <UserMenu />
                        ) : (
                            <div className="flex items-center gap-3">
                                <div className="hidden sm:flex items-center px-2 py-1 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 text-xs font-mono">
                                    v{APP_VERSION || 'dev'}
                                </div>
                                <button
                                    onClick={() => navigate('/login')}
                                    className="text-sm text-slate-400 hover:text-white font-medium transition-colors"
                                >
                                    Sign In
                                </button>
                                <button
                                    onClick={() => navigate('/signup')}
                                    className="text-sm bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded transition-colors"
                                >
                                    Join
                                </button>
                            </div>
                        )}
                    </div>
                </header>

                {/* Split View */}
                <div className="flex-1 flex overflow-hidden">
                    <Group orientation="horizontal" id="main-group" style={{ height: '100%', width: '100%' }}>
                        {/* Left: Instructions & AI (integrated) */}
                        <Panel defaultSize={40} minSize={20} id="left-panel" className="flex flex-col bg-slate-950 border-r border-slate-800 overflow-hidden">
                            <div 
                                id="instruction-scroll-container"
                                ref={instructionScrollRef} 
                                className="flex-1 overflow-y-auto custom-scrollbar flex flex-col min-h-0 bg-[#0b0e14]"
                            >
                                {/* Instructions Section */}
                                <div className="p-2 pt-4">
                                    {lesson && <MarkdownViewer content={lesson.description} />}
                                </div>

                                {/* Divider */}
                                <div className="mx-8 border-t border-slate-800/60 my-2" />

                                {/* AI Assistant — integrated into the same scroll flow */}
                                <div className="flex-1 flex flex-col">
                                    <AIChatPanel
                                        variant="integrated"
                                        lessonId={lesson?.slug ?? ''}
                                        context={buildTutorContext(lesson, code)}
                                    />
                                </div>
                            </div>
                        </Panel>

                        <Separator className="w-1.5 bg-slate-900 border-l border-slate-800 hover:bg-emerald-500 transition-colors cursor-col-resize flex items-center justify-center z-10" />

                        {/* Right: Code & Output or Spreadsheet or Drawing */}
                        <Panel defaultSize={50} minSize={20} id="code-output-panel" className="flex flex-col bg-[#1e1e1e]">
                            {lesson?.exercise_type === 'drawing' ? (
                                // Drawing Exercise
                                <div className="flex flex-col h-full">
                                    {/* Canvas + Solution area -- takes all remaining space */}
                                    <div className="flex-1 flex overflow-hidden min-h-0">
                                        {(() => {
                                            const imageAuthQuery = token ? `?token=${encodeURIComponent(token)}` : '';
                                            return (
                                                <>
                                                    <div className={`${showDrawingSolution ? 'w-1/2' : 'w-full'} border-r border-[#333] transition-all duration-300 min-h-0`}>
                                                        <DrawingCanvas
                                                            imageUrl={`${API_BASE_URL}/file-courses/${slug}/${lesson.slug}/image${imageAuthQuery}`}
                                                            strokeColor={lesson.stroke_color}
                                                            strokeWidth={lesson.stroke_width}
                                                            onCanvasRef={(ref) => { drawingCanvasRef.current = ref; }}
                                                        />
                                                    </div>
                                                    {showDrawingSolution && (
                                                        <div className="w-1/2 bg-slate-900/30 overflow-hidden flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
                                                            <div className="flex items-center justify-between px-4 py-2 shrink-0 border-b border-slate-700/40">
                                                                <h3 className="text-xs font-bold text-yellow-500 uppercase tracking-widest flex items-center gap-2">
                                                                    <Lightbulb size={14} className="fill-yellow-500/20" />
                                                                    Reference Solution
                                                                </h3>
                                                                <span className="text-[10px] text-slate-500 bg-slate-800/50 px-2 py-0.5 rounded border border-slate-700/30">
                                                                    Compare with your drawing
                                                                </span>
                                                            </div>
                                                            <div className="flex-1 overflow-hidden flex items-center justify-center p-3 min-h-0">
                                                                <img
                                                                    src={`${API_BASE_URL}/file-courses/${slug}/${lesson.slug}/solution${imageAuthQuery}`}
                                                                    alt="Solution"
                                                                    className="max-w-full max-h-full object-contain rounded-lg border border-yellow-700/30 shadow-2xl shadow-black/40"
                                                                />
                                                            </div>
                                                        </div>
                                                    )}
                                                </>
                                            );
                                        })()}
                                    </div>
                                    {/* Bottom section: Terminal-style feedback + Action buttons */}
                                    <div className="shrink-0 flex flex-col bg-[#1e1e1e] border-t border-[#333]">
                                        {/* AI Feedback terminal -- always visible, fixed height */}
                                        <div className="h-28 overflow-y-auto px-4 py-3 custom-scrollbar font-mono bg-[#1a1a2e] border-b border-[#333]">
                                            <div className="flex items-center gap-2 mb-1.5">
                                                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">AI Feedback</span>
                                                {drawingOutput && (
                                                    <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                                                        drawingOutput.toLowerCase().includes('pass') || drawingOutput.toLowerCase().includes('great job') || drawingOutput.toLowerCase().includes('correct')
                                                            ? 'bg-emerald-400'
                                                            : drawingOutput.includes('empty')
                                                                ? 'bg-yellow-400'
                                                                : 'bg-blue-400'
                                                    }`} />
                                                )}
                                            </div>
                                            {drawingOutput ? (
                                                <p className={`text-xs whitespace-pre-wrap leading-relaxed ${
                                                    drawingOutput.toLowerCase().includes('pass') || drawingOutput.toLowerCase().includes('great job') || drawingOutput.toLowerCase().includes('correct')
                                                        ? 'text-emerald-400'
                                                        : drawingOutput.includes('empty')
                                                            ? 'text-yellow-400'
                                                            : 'text-slate-300'
                                                }`}>{drawingOutput}</p>
                                            ) : (
                                                <p className="text-xs text-slate-600 italic">Submit your drawing to receive feedback...</p>
                                            )}
                                        </div>
                                        {/* Action bar: Show Solution + Submit */}
                                        <div className="h-12 flex items-center justify-between px-4 gap-3">
                                            <button
                                                onClick={() => setShowDrawingSolution(!showDrawingSolution)}
                                                className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-bold border transition-all shrink-0 ${
                                                    showDrawingSolution
                                                        ? 'bg-yellow-900/40 text-yellow-300 border-yellow-700/50 hover:bg-yellow-900/60'
                                                        : 'bg-[#2d2d2d] text-slate-300 border-[#444] hover:bg-[#3d3d3d] hover:text-white'
                                                }`}
                                            >
                                                <Lightbulb size={14} />
                                                {showDrawingSolution ? 'Hide Solution' : 'Show Solution'}
                                            </button>
                                            <button
                                                onClick={handleDrawingSubmit}
                                                disabled={isSubmittingDrawing}
                                                className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded shadow shadow-blue-900/30 transition-all disabled:opacity-50 shrink-0"
                                            >
                                                <Send size={15} />
                                                {isSubmittingDrawing ? 'Submitting...' : 'Submit Drawing'}
                                            </button>
                                        </div>
                                    </div>
                                </div>

                            ) : lesson?.exercise_type === 'spreadsheet' && lesson?.google_sheet_id ? (
                                // Spreadsheet Exercise - Google Sheets
                                <div className="flex-1 flex flex-col overflow-hidden">
                                    <div className="h-12 border-b border-[#333] flex items-center px-4 bg-[#252526] justify-between gap-4">
                                        <div className="flex items-center gap-3 flex-1 min-w-0">
                                            <span className="text-sm text-slate-400 whitespace-nowrap">📊 {isUsingPersonalCopy ? 'My Copy' : 'Template'}</span>

                                            <div className="flex-1 max-w-lg flex items-center gap-2 bg-[#1e1e1e] border border-[#444] rounded px-2 py-1">
                                                <Link size={14} className="text-slate-500" />
                                                <input
                                                    type="text"
                                                    placeholder="Paste your private copy link here..."
                                                    className="bg-transparent border-none text-xs text-slate-300 w-full focus:outline-none"
                                                    value={userSheetUrl}
                                                    onChange={(e) => setUserSheetUrl(e.target.value)}
                                                />
                                                {userSheetUrl && (
                                                    <button
                                                        onClick={() => setUserSheetUrl("")}
                                                        className="text-slate-500 hover:text-red-400 transition-colors"
                                                        title="Remove link"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                )}
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            {lesson.copy_on_open && (
                                                <button
                                                    onClick={() => window.open(`https://docs.google.com/spreadsheets/d/${lesson.google_sheet_id}/copy`, '_blank')}
                                                    className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded text-white text-xs font-bold transition-all shadow-lg shadow-emerald-900/20"
                                                >
                                                    <ExternalLink size={14} /> Make a private copy
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* If copy_on_open is true we encourage user to make a private copy; still embed the template for preview */}
                                    <div style={{ flex: 1, backgroundColor: '#fff' }}>
                                        {iframeUrl ? (
                                            <iframe
                                                src={iframeUrl}
                                                style={{
                                                    flex: 1,
                                                    border: 'none',
                                                    width: '100%',
                                                    height: '100%'
                                                }}
                                                title="Google Sheet Exercise"
                                                allow="autorepair;usercopy;useredit"
                                            />
                                        ) : (
                                            <div className="flex items-center justify-center h-full text-slate-500 italic">
                                                Sheet ID not found in metadata...
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                // Code Exercise
                                <Group orientation="vertical" id="editor-group" style={{ height: '100%', width: '100%' }}>
                                    {/* Editor */}
                                    <Panel defaultSize={70} minSize={20} id="editor-panel" className="flex flex-col">
                                        {/* Editor Toolbar */}
                                        <div className="h-10 border-b border-[#333] flex items-center px-4 justify-between bg-[#252526]">
                                            <div className="flex items-center gap-2 text-sm text-slate-400">
                                                <button
                                                    onClick={() => setEditorTab('main')}
                                                    className={`flex items-center gap-1.5 px-3 py-1 rounded border transition-colors ${editorTab === 'main'
                                                        ? 'bg-[#1e1e1e] text-slate-200 border-[#333]'
                                                        : 'border-transparent hover:bg-[#2d2d2d]'
                                                        }`}
                                                >
                                                    📄 {mainFilename}
                                                </button>
                                                <button
                                                    onClick={() => setEditorTab('tests')}
                                                    className={`flex items-center gap-1.5 px-3 py-1 rounded border transition-colors ${editorTab === 'tests'
                                                        ? 'bg-[#1e1e1e] text-slate-200 border-[#333]'
                                                        : 'border-transparent hover:bg-[#2d2d2d]'
                                                        }`}
                                                >
                                                    🧪 {testsFilename}
                                                </button>
                                                {lesson?.has_solution && (
                                                    <button
                                                        onClick={async () => {
                                                            if (!loadedSolution && slug && lesson && token) {
                                                                try {
                                                                    const text = await fetchSolutionCode(slug, lesson.slug, token);
                                                                    setLoadedSolution(text);
                                                                } catch {
                                                                    setLoadedSolution('Unable to load solution.');
                                                                }
                                                            }
                                                            setShowSolution(true);
                                                            setEditorTab('solution');
                                                        }}
                                                        className={`flex items-center gap-1.5 px-3 py-1 rounded border transition-colors ${editorTab === 'solution'
                                                            ? 'bg-yellow-900/40 text-yellow-300 border-yellow-700/50'
                                                            : 'border-transparent text-yellow-500/70 hover:bg-yellow-900/20 hover:text-yellow-400'
                                                            }`}
                                                    >
                                                        <Lightbulb size={13} /> Solution
                                                    </button>
                                                )}
                                            </div>
                                        </div>

                                        {/* Editor Area */}
                                        <div className="flex-1 min-h-0 relative">
                                            <div className="absolute inset-0" style={{ display: editorTab === 'main' ? 'block' : 'none' }}>
                                                <CodeEditor
                                                    key="editor-main"
                                                    code={code}
                                                    onChange={handleCodeChange}
                                                    language={currentLang}
                                                    filename={mainFilename}
                                                />
                                            </div>
                                            <div className="absolute inset-0" style={{ display: editorTab === 'tests' ? 'block' : 'none' }}>
                                                <CodeEditor
                                                    key="editor-tests"
                                                    code={testsEditorCode}
                                                    onChange={() => { }}
                                                    readOnly={true}
                                                    language={currentLang}
                                                    filename={testsFilename}
                                                />
                                            </div>
                                            {showSolution && (
                                                <div className="absolute inset-0" style={{ display: editorTab === 'solution' ? 'block' : 'none' }}>
                                                    <CodeEditor
                                                        key="editor-solution"
                                                        code={loadedSolution}
                                                        onChange={() => { }}
                                                        readOnly={true}
                                                        language={currentLang}
                                                        filename={lesson?.language === 'rust' ? 'solution.rs' : 'solution.py'}
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    </Panel>

                                    <Separator className="h-1.5 bg-[#252526] border-t border-[#333] hover:bg-emerald-500 transition-colors cursor-row-resize flex items-center justify-center z-10" />

                                    {/* Output / Console Panel */}
                                    <Panel defaultSize={30} minSize={10} id="console-panel" className="flex flex-col bg-[#1e1e1e]">
                                        <div className="h-10 flex items-center justify-between px-4 border-b border-[#333] bg-[#252526]">
                                            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Console Output</span>

                                            <div className="flex gap-2">
                                                <button
                                                    onClick={handleResetCode}
                                                    className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium rounded transition-colors"
                                                >
                                                    <RotateCw size={14} /> Reset
                                                </button>
                                                <button
                                                    onClick={() => handleRun(false)}
                                                    disabled={isRunning}
                                                    className="flex items-center gap-2 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded shadow shadow-emerald-900/20 transition-all disabled:opacity-50"
                                                >
                                                    <Play size={14} fill="currentColor" /> {isRunning ? 'Running...' : 'Run Code'}
                                                </button>
                                                <button
                                                    onClick={() => handleRun(true)}
                                                    disabled={isRunning}
                                                    className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded shadow shadow-blue-900/20 transition-all disabled:opacity-50"
                                                >
                                                    Submit
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
                                    </Panel>
                                </Group>
                            )}
                        </Panel>

                    </Group>
                </div>
            </div>
            <WelcomeGate
                isOpen={isLearningGuideOpen}
                onClose={() => setIsLearningGuideOpen(false)}
                initialTab="modalities"
            />
            {sharePayload && (
                <ShareAchievement payload={sharePayload} onClose={() => setSharePayload(null)} />
            )}
        </div>
    );
}
