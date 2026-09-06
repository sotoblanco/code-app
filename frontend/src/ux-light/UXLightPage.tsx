import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import confetti from 'canvas-confetti';
import { BookOpen, Code2, Terminal } from 'lucide-react';
import { Header } from './components/Header';
import { InstructionsPane } from './components/InstructionsPane';
import { CodeEditorPane } from './components/CodeEditorPane';
import { ConsolePane } from './components/ConsolePane';
import { ChapterBar } from './components/ChapterBar';
import { HorizontalSplit, VerticalSplit } from './components/SplitPane';
import { AuthorStudioView } from './components/AuthorStudioView';
import { EmbedModal } from './components/EmbedModal';
import { FlagReportModal } from './components/FlagReportModal';
import { DrawingPane } from './components/DrawingPane';
import { SpreadsheetPane } from './components/SpreadsheetPane';
import { ShareAchievement } from './components/ShareAchievement';
import { groupLessonsIntoChapters, flattenLessons } from './courseLoader';
import { emitLearnerEvent, fetchMyProgress } from '../services/profileService';
import { findLessonPosition, useLessonUrlSync } from '../lessonUrl';
import type {
  FileCourse,
  FileLesson,
  UXLightChapter,
  ConsoleTab,
  MobileTab,
  EditorTab,
  OutputMessage,
  GradingResult,
  DrawingFeedback,
  SpreadsheetVerification,
} from './types';
import type { ShareKind, SharePayload } from './shareCard';
import { API_BASE_URL } from '../config';
import { messageForRunStatus } from '../runErrors';
import { testsToRun } from '../testsToRun';
import { useAuth } from '../context/AuthContext';
import { WelcomeGate } from '../components/auth/WelcomeGate';
import { fetchSolutionCode } from '../solutionApi';
import { isAuthorRole } from '../testVisibility';

export default function UXLightPage({ onSwitchUi }: { onSwitchUi?: () => void }) {
  const { slug, lessonSlug } = useParams<{ slug: string; lessonSlug?: string }>();
  const navigate = useNavigate();
  const { token, isAuthenticated, logout, user } = useAuth();

  const [course, setCourse] = useState<FileCourse | null>(null);
  const [chapters, setChapters] = useState<UXLightChapter[]>([]);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(0);
  const [currentLessonIndex, setCurrentLessonIndex] = useState(0);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [courseError, setCourseError] = useState<string | null>(null);

  const [code, setCode] = useState('');
  const [lessonOverrideMd, setLessonOverrideMd] = useState<Record<string, string>>({});
  const [activeEditorTab, setActiveEditorTab] = useState<EditorTab>('script');
  const [isShowingSolution, setIsShowingSolution] = useState(false);
  const [loadedSolution, setLoadedSolution] = useState('');
  const [editorTheme, setEditorTheme] = useState<'dark' | 'light'>('dark');

  const [activeConsoleTab, setActiveConsoleTab] = useState<ConsoleTab>('shell');
  const [outputs, setOutputs] = useState<OutputMessage[]>([]);
  const [gradingResult, setGradingResult] = useState<GradingResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [totalXp, setTotalXp] = useState(0);
  const [xpPenalty, setXpPenalty] = useState(0);

  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [isEmbedOpen, setIsEmbedOpen] = useState(false);
  const [isFlagOpen, setIsFlagOpen] = useState(false);
  const [sharePayload, setSharePayload] = useState<SharePayload | null>(null);

  const [userSheetUrl, setUserSheetUrl] = useState('');
  const [drawingFeedback, setDrawingFeedback] = useState<DrawingFeedback | null>(null);
  const [isSubmittingDrawing, setIsSubmittingDrawing] = useState(false);
  const [showDrawingSolution, setShowDrawingSolution] = useState(false);
  const [sheetVerification, setSheetVerification] = useState<SpreadsheetVerification | null>(null);
  const [sheetVerifyError, setSheetVerifyError] = useState<string | null>(null);
  const [isVerifyingSheet, setIsVerifyingSheet] = useState(false);
  const drawingCanvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isMobile, setIsMobile] = useState(false);
  const [mobileTab, setMobileTab] = useState<MobileTab>('instructions');

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const apply = () => setIsMobile(mq.matches);
    apply();
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, []);

  useEffect(() => {
    const fetchCourse = async () => {
      setCourseError(null);
      try {
        const [res, progress] = await Promise.all([
          fetch(`${API_BASE_URL}/file-courses/${slug}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
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
          const data: FileCourse = await res.json();
          const grouped = groupLessonsIntoChapters(data.lessons);
          setCourse(data);
          setChapters(grouped);

          const courseProgress = progress.find((p) => p.course_slug === slug);
          const knownSlugs = new Set(grouped.flatMap((ch) => ch.lessons.map((l) => l.slug)));
          setCompletedIds(
            new Set((courseProgress?.completed_lessons ?? []).filter((s) => knownSlugs.has(s)))
          );
          setTotalXp(courseProgress?.xp ?? 0);

          // Prefer the lesson named in the URL, else the learner's last lesson, else lesson 1.
          const target =
            findLessonPosition(grouped, lessonSlug) ??
            findLessonPosition(grouped, courseProgress?.resume_lesson ?? null);
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
    };

    if (!isAuthenticated) {
      setIsAuthModalOpen(true);
      return;
    }
    fetchCourse();
  }, [slug, isAuthenticated, token, logout]);

  const currentChapter = chapters[currentChapterIndex];
  const lesson: FileLesson | undefined = currentChapter?.lessons[currentLessonIndex];

  const allLessons = useMemo(() => flattenLessons(chapters), [chapters]);
  const currentGlobalIndex = useMemo(() => {
    const idx = allLessons.findIndex(
      (item) => item.chapterIndex === currentChapterIndex && item.lessonIndex === currentLessonIndex
    );
    return idx >= 0 ? idx : 0;
  }, [allLessons, currentChapterIndex, currentLessonIndex]);

  useEffect(() => {
    if (!lesson || !slug) return;
    const storageKey = `uxlight_code_${slug}_${lesson.slug}`;
    const legacyKey = `code_draft_${slug}_${lesson.slug}`;
    const saved = localStorage.getItem(storageKey) ?? localStorage.getItem(legacyKey);
    setCode(saved !== null ? saved : lesson.initial_code || '');
    setActiveEditorTab('script');
    setIsShowingSolution(false);
    setLoadedSolution('');
    setShowDrawingSolution(false);
    setXpPenalty(0);
    setGradingResult(null);
    setOutputs([]);
    setDrawingFeedback(null);
    setSheetVerification(null);
    setSheetVerifyError(null);
    setActiveConsoleTab('shell');
    setMobileTab('instructions');
    const savedUrl = localStorage.getItem(`spreadsheet_copy_${slug}_${lesson.slug}`);
    setUserSheetUrl(savedUrl || '');

    // Record lesson opened in learner profile
    emitLearnerEvent('lesson_opened', {
      course_slug: slug,
      lesson_slug: lesson.slug,
      ui: 'light',
    });
  }, [lesson?.slug, slug]);

  useEffect(() => {
    if (!lesson || !slug) return;
    if (userSheetUrl) localStorage.setItem(`spreadsheet_copy_${slug}_${lesson.slug}`, userSheetUrl);
    else localStorage.removeItem(`spreadsheet_copy_${slug}_${lesson.slug}`);
  }, [userSheetUrl, lesson, slug]);

  const handleCodeChange = (newCode: string) => {
    setCode(newCode);
    if (lesson && slug) {
      localStorage.setItem(`uxlight_code_${slug}_${lesson.slug}`, newCode);
      localStorage.setItem(`code_draft_${slug}_${lesson.slug}`, newCode);
    }
  };

  const handleSelectLesson = (chapterIndex: number, lessonIndex: number) => {
    setCurrentChapterIndex(chapterIndex);
    setCurrentLessonIndex(lessonIndex);
  };

  const handlePrevious = () => {
    if (currentGlobalIndex > 0) {
      const prev = allLessons[currentGlobalIndex - 1];
      handleSelectLesson(prev.chapterIndex, prev.lessonIndex);
    }
  };

  const handleNext = () => {
    if (currentGlobalIndex < allLessons.length - 1) {
      const next = allLessons[currentGlobalIndex + 1];
      handleSelectLesson(next.chapterIndex, next.lessonIndex);
    }
  };

  const handleResetCode = () => {
    if (!lesson) return;
    if (window.confirm("Are you sure you want to reset your code to the starter code? Current edits will be lost.")) {
      setCode(lesson.initial_code || '');
      if (slug) {
        localStorage.setItem(`uxlight_code_${slug}_${lesson.slug}`, lesson.initial_code || '');
        localStorage.setItem(`code_draft_${slug}_${lesson.slug}`, lesson.initial_code || '');
      }
      emitLearnerEvent('reset', {
        course_slug: slug,
        lesson_slug: lesson.slug,
      });
    }
  };

  const pushOutput = (msg: Omit<OutputMessage, 'id' | 'timestamp'>) => {
    setOutputs((prev) => [...prev, { ...msg, id: `${Date.now()}-${Math.random()}`, timestamp: Date.now() }]);
  };

  const recordLessonPass = (modality: 'code' | 'spreadsheet' | 'drawing') => {
    if (!lesson || !slug) return;
    if (completedIds.has(lesson.slug)) return; // persist only the first completion
    const earned = Math.max(5, 35 - xpPenalty);
    emitLearnerEvent('lesson_passed', {
      course_slug: slug,
      lesson_slug: lesson.slug,
      modality,
      xp: earned,
    });
  };

  const handleRunCode = async (customCommand?: string, isSubmit = false) => {
    if (!lesson) return;
    const codeToRun = customCommand || code;
    if (!codeToRun.trim() && !isSubmit) return;

    if (isSubmit) setIsSubmitting(true);
    else setIsRunning(true);
    setActiveConsoleTab('shell');
    if (isMobile) setMobileTab('console');

    pushOutput({
      type: 'prompt',
      text: customCommand || (isSubmit ? 'submit answer' : `run ${lesson.language === 'rust' ? 'main.rs' : 'script.py'}`),
    });

    try {
      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = `Bearer ${token}`;

      const language = lesson.language || 'python';
      const body = customCommand
        ? { code: customCommand, language }
        : {
            code,
            test_code: testsToRun(lesson.test_code || '', language, isSubmit),
            language,
          };

      const res = await fetch(`${API_BASE_URL}/run`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      const runError = messageForRunStatus(res.status);
      if (runError) {
        if (res.status === 401) {
          logout();
          setIsAuthModalOpen(true);
        }
        pushOutput({ type: 'error', text: runError });
        if (isSubmit) triggerFailure(runError);
        return;
      }
      const data = await res.json();

      if (data.stdout) pushOutput({ type: 'stdout', text: data.stdout });
      if (data.stderr) pushOutput({ type: 'stderr', text: data.stderr });
      if (!data.stdout && !data.stderr) {
        pushOutput({ type: 'stdout', text: 'Process finished with return code 0.' });
      }

      if (isSubmit) {
        if (data.exit_code === 0) {
          recordLessonPass('code');
          triggerSuccess(data.stdout || 'All tests passed.');
        } else triggerFailure(data.stderr || data.stdout || `Exited with code ${data.exit_code}`);
      }
    } catch {
      pushOutput({ type: 'error', text: 'Failed to connect to execution server.' });
      if (isSubmit) triggerFailure('Failed to connect to execution server.');
    } finally {
      setIsRunning(false);
      setIsSubmitting(false);
    }
  };

  const triggerSuccess = (message: string) => {
    if (!lesson || !course) return;
    const earned = Math.max(5, 35 - xpPenalty);
    const firstTime = !completedIds.has(lesson.slug);
    const nextCompleted = firstTime ? new Set([...completedIds, lesson.slug]) : completedIds;
    if (firstTime) {
      setCompletedIds(nextCompleted);
      setTotalXp((prev) => prev + earned);
    }
    setGradingResult({ passed: true, xpEarned: earned, message });
    setActiveConsoleTab('feedback');
    confetti({ particleCount: 120, spread: 70, origin: { y: 0.6 }, colors: ['#03ef62', '#05192d', '#ffb800'] });
    if (firstTime) {
      const courseDone = nextCompleted.size >= allLessons.length && allLessons.length > 0;
      openShare(courseDone ? 'course' : 'lesson');
    }
  };

  const openShare = (kind: ShareKind) => {
    if (!course || !lesson) return;
    const lessonSkills = lesson.skills || [];
    const courseSkills = course.skills || [];
    setSharePayload({
      kind,
      courseTitle: course.title,
      lessonTitle: lesson.title,
      skills: kind === 'course' ? courseSkills : lessonSkills.length ? lessonSkills : courseSkills,
    });
  };

  const triggerFailure = (errorDetail: string) => {
    setGradingResult({
      passed: false,
      xpEarned: 0,
      message: 'Submission did not pass all checks.',
      errorDetail,
    });
    setActiveConsoleTab('feedback');
  };

  const handleDrawingSubmit = async () => {
    if (!lesson || !drawingCanvasRef.current || !slug) return;
    setIsSubmittingDrawing(true);
    setDrawingFeedback(null);
    try {
      const imageData = drawingCanvasRef.current.toDataURL('image/png');
      const response = await fetch(`${API_BASE_URL}/file-courses/${slug}/${lesson.slug}/submit-drawing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ image_data: imageData, xp: Math.max(5, 35 - xpPenalty) }),
      });
      if (response.status === 401) {
        logout();
        setIsAuthModalOpen(true);
        setDrawingFeedback({ passed: false, message: 'Your session has expired. Please sign in again.' });
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setDrawingFeedback({
          passed: false,
          message: data.detail || 'Drawing evaluation failed. Please try again.',
        });
        return;
      }
      const feedback: DrawingFeedback = {
        passed: !!data.passed,
        score: data.score,
        message: data.message || (data.passed ? 'Your drawing passed.' : 'Your drawing needs work.'),
        checks: Array.isArray(data.checks) ? data.checks : undefined,
      };
      setDrawingFeedback(feedback);
      if (feedback.passed) triggerSuccess(feedback.message);
    } catch {
      setDrawingFeedback({ passed: false, message: 'Failed to submit drawing.' });
    } finally {
      setIsSubmittingDrawing(false);
    }
  };

  const handleSheetVerify = async (sheetUrl: string) => {
    if (!lesson || !slug) return;
    setSheetVerification(null);
    setSheetVerifyError(null);
    setIsVerifyingSheet(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/file-courses/${slug}/${lesson.slug}/verify-sheet`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ sheet_id: sheetUrl, xp: Math.max(5, 35 - xpPenalty) }),
        }
      );
      if (response.status === 401) {
        logout();
        setIsAuthModalOpen(true);
        setSheetVerifyError('Your session has expired. Please sign in again.');
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setSheetVerifyError(data.detail || 'Could not verify your sheet. Please try again.');
        return;
      }
      const verification = data as SpreadsheetVerification;
      setSheetVerification(verification);
      if (verification.passed) triggerSuccess(verification.message);
    } catch {
      setSheetVerifyError('Failed to reach the verification service.');
    } finally {
      setIsVerifyingSheet(false);
    }
  };

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const isCtrlOrCmd = e.ctrlKey || e.metaKey;
      if (isCtrlOrCmd && e.shiftKey && e.key === 'Enter') {
        e.preventDefault();
        handleRunCode(undefined, true);
      } else if (isCtrlOrCmd && e.key === 'Enter') {
        e.preventDefault();
        handleRunCode();
      }
    },
    [code, lesson, token]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useLessonUrlSync({
    courseSlug: slug,
    chapters,
    currentChapterIndex,
    currentLessonIndex,
    onSelectLesson: handleSelectLesson,
  });

  if (!isAuthenticated || !course || chapters.length === 0 || !lesson) {
    return (
      <div className="flex h-screen w-full bg-[#f4f6f8] items-center justify-center text-[#5b6b7b]">
        <div className="text-center">
          {courseError ? <p className="text-red-500">{courseError}</p> : (
            <>
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#03ef62] mx-auto mb-4" />
              <p>Loading course...</p>
            </>
          )}
        </div>
        <WelcomeGate isOpen={isAuthModalOpen} onClose={() => navigate('/')} />
      </div>
    );
  }

  const displayLesson: FileLesson = lessonOverrideMd[lesson.slug]
    ? { ...lesson, description: lessonOverrideMd[lesson.slug] }
    : lesson;

  const currentLang = lesson.language || 'python';
  const filename = currentLang === 'rust' ? 'main.rs' : 'script.py';
  const exerciseType = lesson.exercise_type || 'code';

  const instructions = (
    <InstructionsPane
      lesson={displayLesson}
      lessonNumber={currentLessonIndex + 1}
      totalInChapter={currentChapter.lessons.length}
      isShowingSolution={isShowingSolution}
      onToggleSolution={async () => {
        const next = !isShowingSolution;
        if (next && exerciseType !== 'drawing' && !loadedSolution && slug && token) {
          try {
            setLoadedSolution(await fetchSolutionCode(slug, lesson.slug, token));
          } catch {
            setLoadedSolution('Unable to load solution.');
          }
        }
        setIsShowingSolution(next);
        if (next) {
          if (exerciseType === 'drawing') setShowDrawingSolution(true);
          else setActiveEditorTab('solution');
        } else {
          setShowDrawingSolution(false);
          setActiveEditorTab('script');
        }
      }}
      xpPenalty={xpPenalty}
      onTakeHint={() => setXpPenalty((p) => Math.min(p + 10, 25))}
      code={code}
    />
  );

  const workspace =
    exerciseType === 'drawing' ? (
      <DrawingPane
        courseSlug={slug || ''}
        lesson={lesson}
        showSolution={showDrawingSolution}
        onToggleSolution={() => setShowDrawingSolution(!showDrawingSolution)}
        onCanvasRef={(ref) => {
          drawingCanvasRef.current = ref;
        }}
        onSubmit={handleDrawingSubmit}
        isSubmitting={isSubmittingDrawing}
        feedback={drawingFeedback}
      />
    ) : exerciseType === 'spreadsheet' && lesson.google_sheet_id ? (
      <SpreadsheetPane
        lesson={lesson}
        userSheetUrl={userSheetUrl}
        onChangeUrl={setUserSheetUrl}
        onVerify={handleSheetVerify}
        isVerifying={isVerifyingSheet}
        verification={sheetVerification}
        verifyError={sheetVerifyError}
        onMarkComplete={() => {
          recordLessonPass('spreadsheet');
          triggerSuccess('Spreadsheet lesson marked complete.');
        }}
        isComplete={completedIds.has(lesson.slug)}
      />
    ) : (
      <CodeEditorPane
        code={code}
        onChange={handleCodeChange}
        testCode={lesson.test_code || ''}
        testsVisible={isAuthorRole(user?.role)}
        solutionCode={loadedSolution}
        activeTab={activeEditorTab}
        onSelectTab={setActiveEditorTab}
        isShowingSolution={isShowingSolution}
        theme={editorTheme}
        onToggleTheme={() => setEditorTheme(editorTheme === 'dark' ? 'light' : 'dark')}
        language={currentLang}
        filename={filename}
        onReset={handleResetCode}
        onRunCode={() => handleRunCode()}
        onSubmitAnswer={() => handleRunCode(undefined, true)}
        isRunning={isRunning}
        isSubmitting={isSubmitting}
      />
    );

  const consolePane = (
    <ConsolePane
      activeTab={activeConsoleTab}
      onSelectTab={setActiveConsoleTab}
      outputs={outputs}
      plots={[]}
      gradingResult={gradingResult}
      onClearConsole={() => setOutputs([])}
      onExecuteReplCommand={(cmd) => handleRunCode(cmd)}
      onNextLesson={handleNext}
      isNextDisabled={currentGlobalIndex === allLessons.length - 1}
      onShare={() => openShare('lesson')}
    />
  );

  return (
    <div className="h-screen w-screen flex flex-col bg-[#f4f6f8] text-[#1a2733] font-sans overflow-hidden">
      <Header
        course={course}
        chapters={chapters}
        currentLesson={displayLesson}
        currentChapterIndex={currentChapterIndex}
        currentLessonIndex={currentLessonIndex}
        totalLessons={allLessons.length}
        currentGlobalIndex={currentGlobalIndex}
        completedIds={completedIds}
        totalXp={totalXp}
        onSelectLesson={handleSelectLesson}
        onPrevious={handlePrevious}
        onNext={handleNext}
        onOpenEmbed={() => setIsEmbedOpen(true)}
        onOpenStudio={() => setIsStudioOpen(true)}
        onOpenFlag={() => setIsFlagOpen(true)}
        onSwitchUi={onSwitchUi}
        onShare={() => openShare(completedIds.size >= allLessons.length ? 'course' : 'lesson')}
        canShare={completedIds.has(displayLesson.slug)}
      />

      <main className="flex-1 overflow-hidden min-h-0">
        {isMobile ? (
          <div className="h-full flex flex-col">
            <div className="h-10 min-h-[40px] bg-white border-b border-[#e2e8ee] flex">
              {([
                ['instructions', BookOpen, 'Instructions'],
                ['workspace', Code2, exerciseType === 'drawing' ? 'Canvas' : exerciseType === 'spreadsheet' ? 'Sheet' : 'Editor'],
                ['console', Terminal, 'Console'],
              ] as const).map(([id, Icon, label]) => (
                <button
                  key={id}
                  onClick={() => setMobileTab(id)}
                  className={`flex-1 flex items-center justify-center gap-1.5 text-xs font-bold ${
                    mobileTab === id
                      ? 'text-[#05192d] border-b-2 border-[#03ef62]'
                      : 'text-[#5b6b7b]'
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              {mobileTab === 'instructions' && instructions}
              {mobileTab === 'workspace' && workspace}
              {mobileTab === 'console' && consolePane}
            </div>
          </div>
        ) : (
          <HorizontalSplit
            leftDefaultSize="42%"
            left={instructions}
            right={
              exerciseType === 'code' ? (
                <VerticalSplit topDefaultSize="56%" top={workspace} bottom={consolePane} />
              ) : (
                workspace
              )
            }
          />
        )}
      </main>

      <ChapterBar
        chapters={chapters}
        currentChapterIndex={currentChapterIndex}
        completedIds={completedIds}
        onSelectChapter={(cIdx) => handleSelectLesson(cIdx, 0)}
      />

      {isStudioOpen && (
        <AuthorStudioView
          initialMarkdown={displayLesson.description}
          onApply={(md) => setLessonOverrideMd((prev) => ({ ...prev, [lesson.slug]: md }))}
          onClose={() => setIsStudioOpen(false)}
        />
      )}
      {isEmbedOpen && (
        <EmbedModal lesson={lesson} currentCode={code} solutionCode={loadedSolution} onClose={() => setIsEmbedOpen(false)} />
      )}
      {isFlagOpen && <FlagReportModal lesson={lesson} onClose={() => setIsFlagOpen(false)} />}
      {sharePayload && (
        <ShareAchievement
          payload={sharePayload}
          onClose={() => setSharePayload(null)}
          onNext={
            sharePayload.kind === 'course'
              ? () => {
                  setSharePayload(null);
                  navigate('/');
                }
              : currentGlobalIndex < allLessons.length - 1
                ? () => {
                    setSharePayload(null);
                    handleNext();
                  }
                : undefined
          }
          nextLabel={sharePayload.kind === 'course' ? 'Back to courses' : 'Next Exercise'}
        />
      )}
      <WelcomeGate isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </div>
  );
}
