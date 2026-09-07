import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Terminal, ChevronRight, FolderCode, Database, Compass, Sliders, CheckCircle2, Upload, Share2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL, APP_VERSION } from '../config';
import { UserMenu } from '../components/UserMenu';
import { WelcomeGate } from '../components/auth/WelcomeGate';
import CourseBuilder from '../components/CourseBuilder';
import { LearningProfileModal } from '../components/LearningProfileModal';
import { ShareModal } from '../components/ShareModal';
import { ImportModal } from '../components/ImportModal';
import { getLearningProfile, fetchMyProgress, type CourseProgressSummary } from '../services/profileService';
import { isLocalHost } from '../isLocalHost';

interface FileCourse {
  slug: string;
  title: string;
  description: string;
  lesson_count: number;
  skills?: string[];
}

interface DbCourse {
  id: number;
  title: string;
  description: string;
  exercises?: { id: number }[];
}

interface UnifiedCourse {
  id: string;
  type: 'file' | 'db';
  title: string;
  description: string;
  lesson_count: number;
  navigatePath: string;
  skills?: string[];
  progress?: CourseProgressSummary | null;
}

export default function CoursesPage() {
  const [courses, setCourses] = useState<UnifiedCourse[]>([]);
  const [progressBySlug, setProgressBySlug] = useState<Record<string, CourseProgressSummary>>({});
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isLearningGuideOpen, setIsLearningGuideOpen] = useState(false);
  const [isCourseBuilderOpen, setIsCourseBuilderOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [profileInitialMode, setProfileInitialMode] = useState<'preview' | 'edit' | 'customize'>('customize');
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importInitialData, setImportInitialData] = useState<string | null>(null);
  const [shareModalData, setShareModalData] = useState<{
    courseSlug: string;
    lessonSlug?: string | null;
    title: string;
  } | null>(null);
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    const hash = window.location.hash;
    if (hash && (hash.includes('#import=') || hash.includes('#share='))) {
      setImportInitialData(hash);
      setIsImportModalOpen(true);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated && isLocalHost()) {
      setIsAuthModalOpen(true);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      const hasCompleted = localStorage.getItem('baselayer_diagnostic_completed');
      if (hasCompleted !== 'true') {
        getLearningProfile()
          .then((data) => {
            const isDefault =
              data.parsed.signals.length <= 1 &&
              !data.markdown.includes('intake_preference') &&
              !data.markdown.includes('explanation_length: thorough') &&
              !data.markdown.includes('exercise_format: macro_challenges') &&
              !data.markdown.includes('exercise_format: guided_completion');
            if (isDefault) {
              setProfileInitialMode('customize');
              setIsProfileModalOpen(true);
            } else {
              localStorage.setItem('baselayer_diagnostic_completed', 'true');
            }
          })
          .catch(() => {
            // Silently ignore if offline
          });
      }
    }
  }, [isAuthenticated]);

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        const [fileRes, dbRes] = await Promise.allSettled([
          fetch(`${API_BASE_URL}/file-courses/`),
          fetch(`${API_BASE_URL}/courses/`),
        ]);

        const unified: UnifiedCourse[] = [];

        if (fileRes.status === 'fulfilled' && fileRes.value.ok) {
          const files: FileCourse[] = await fileRes.value.json();
          unified.push(
            ...files.map((c) => {
              const progress = progressBySlug[c.slug];
              const resume = progress && !progress.completed && progress.resume_lesson;
              return {
                id: `file-${c.slug}`,
                type: 'file' as const,
                title: c.title,
                description: c.description,
                lesson_count: c.lesson_count,
                navigatePath: resume
                  ? `/file-course/${c.slug}/${progress!.resume_lesson}`
                  : `/file-course/${c.slug}`,
                skills: c.skills,
                progress: progress ?? null,
              };
            })
          );
        }

        if (dbRes.status === 'fulfilled' && dbRes.value.ok) {
          const dbs: DbCourse[] = await dbRes.value.json();
          unified.push(
            ...dbs.map((c) => ({
              id: `db-${c.id}`,
              type: 'db' as const,
              title: c.title,
              description: c.description,
              lesson_count: c.exercises?.length ?? 0,
              navigatePath: `/course/${c.id}`,
            }))
          );
        }

        setCourses(unified);
      } catch (err) {
        console.error('Failed to fetch courses', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCourses();
  }, [progressBySlug]);

  useEffect(() => {
    let active = true;
    if (!isAuthenticated) {
      setProgressBySlug({});
      return;
    }
    fetchMyProgress().then((list) => {
      if (!active) return;
      const bySlug: Record<string, CourseProgressSummary> = {};
      list.forEach((p) => {
        bySlug[p.course_slug] = p;
      });
      setProgressBySlug(bySlug);
    });
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  const hasNoCourses = courses.length === 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col">
      <header className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-8">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600 rounded-lg">
            <Terminal size={20} className="text-white" />
          </div>
          <h1 className="font-bold text-xl tracking-tight">BaseLayer App</h1>
        </div>
        <div className="flex items-center gap-3">
          {isAuthenticated && (
            <button
              onClick={() => {
                setProfileInitialMode('customize');
                setIsProfileModalOpen(true);
              }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
              title="Calibrate your personal learning style"
            >
              <Sliders size={14} className="text-blue-400" />
              <span>Learning Style</span>
            </button>
          )}
          <button
            onClick={() => setIsLearningGuideOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/90 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
            title="Learning Guide & AI Setup"
          >
            <Compass size={14} className="text-emerald-400" />
            <span>Learning Guide</span>
          </button>
          {isAuthenticated ? (
            <UserMenu
              onOpenProfile={() => {
                setProfileInitialMode('preview');
                setIsProfileModalOpen(true);
              }}
            />
          ) : (
            <div className="flex items-center gap-4 text-sm font-medium">
              <div className="hidden sm:flex items-center px-2 py-1 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 text-xs font-mono">
                v{APP_VERSION || 'dev'}
              </div>
              <button
                onClick={() => setIsAuthModalOpen(true)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                Sign In
              </button>
              <button
                onClick={() => setIsAuthModalOpen(true)}
                className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-colors shadow-lg shadow-blue-500/20"
              >
                Get Started
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full p-8">
        <div className="mb-8">
          <div className="flex flex-col gap-5 rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-slate-900 p-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-emerald-400">Learn by building</p>
              <h2 className="mb-2 text-3xl font-bold">What do you want to learn?</h2>
              <p className="max-w-xl text-slate-400">Ask for a topic and optionally add notes. BaseLayer will create a runnable course using tiny Solveit steps.</p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <button
                onClick={() => (isAuthenticated ? setIsImportModalOpen(true) : setIsAuthModalOpen(true))}
                className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/90 px-4 py-3 text-sm font-semibold text-slate-200 transition-colors hover:bg-slate-700 hover:text-white"
                title="Import a shared course or lesson bundle"
              >
                <Upload size={16} className="text-blue-400" />
                <span>Import Course</span>
              </button>
              <button
                onClick={() => (isAuthenticated ? setIsCourseBuilderOpen(true) : setIsAuthModalOpen(true))}
                className="rounded-lg bg-emerald-500 px-5 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-400"
              >
                Build a course
              </button>
            </div>
          </div>
          <div className="mt-8 flex items-end justify-between">
            <div>
              <h3 className="text-2xl font-bold">Available Courses</h3>
              <p className="text-slate-400">Select a course to start coding.</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {hasNoCourses ? (
              <div className="col-span-full text-center py-20 text-slate-500 bg-slate-900/50 rounded-xl border border-dashed border-slate-800">
                <p>No courses available right now.</p>
              </div>
            ) : (
              courses.map((course) => (
                <div
                  key={course.id}
                  className={`bg-slate-900 border border-slate-800 rounded-xl overflow-hidden transition-all duration-300 group cursor-pointer flex flex-col ${
                    course.type === 'file'
                      ? 'hover:border-emerald-500/50 hover:shadow-lg hover:shadow-emerald-500/10'
                      : 'hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/10'
                  }`}
                  onClick={() => {
                    if (isAuthenticated) {
                      navigate(course.navigatePath);
                    } else {
                      setIsAuthModalOpen(true);
                    }
                  }}
                >
                  <div
                    className={`h-2 bg-gradient-to-r ${
                      course.type === 'file'
                        ? 'from-emerald-600 to-teal-600'
                        : 'from-blue-600 to-indigo-600'
                    }`}
                  />
                  <div className="p-6 flex-1 flex flex-col">
                    <div className="flex items-start justify-between mb-4">
                      <div
                        className={`p-3 bg-slate-800 rounded-lg transition-colors ${
                          course.type === 'file'
                            ? 'group-hover:bg-emerald-500/10 group-hover:text-emerald-400'
                            : 'group-hover:bg-blue-500/10 group-hover:text-blue-400'
                        }`}
                      >
                        {course.type === 'file' ? <FolderCode size={24} /> : <Database size={24} />}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {course.type === 'file' && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              const cleanSlug = course.id.replace(/^file-/, '');
                              setShareModalData({
                                courseSlug: cleanSlug,
                                title: course.title,
                              });
                            }}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors border border-transparent hover:border-slate-700"
                            title="Share or export this course"
                          >
                            <Share2 size={14} />
                          </button>
                        )}
                        <span
                          className={`text-xs px-2 py-1 rounded-full font-medium border ${
                            course.type === 'file'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                          }`}
                        >
                          {course.type === 'file' ? 'File' : 'Database'}
                        </span>
                      </div>
                    </div>

                    <h3
                      className={`text-xl font-bold mb-2 transition-colors ${
                        course.type === 'file'
                          ? 'group-hover:text-emerald-400'
                          : 'group-hover:text-blue-400'
                      }`}
                    >
                      {course.title}
                    </h3>

                    {course.description && (
                      <p className="text-slate-400 text-sm mb-4 line-clamp-2">{course.description}</p>
                    )}

                    {course.skills && course.skills.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-4">
                        {course.skills.slice(0, 4).map((skill) => (
                          <span
                            key={skill}
                            className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    )}

                    {course.progress && course.type === 'file' && (
                      <div className="mb-3">
                        <div className="flex items-center justify-between text-[11px] mb-1.5">
                          {course.progress.completed ? (
                            <span className="flex items-center gap-1 font-semibold text-emerald-400">
                              <CheckCircle2 size={12} /> Completed
                            </span>
                          ) : course.progress.resume_order ? (
                            <span className="font-semibold text-emerald-300/90">
                              Continue {course.title} — lesson {course.progress.resume_order}
                            </span>
                          ) : (
                            <span className="font-medium text-slate-400">In progress</span>
                          )}
                          <span className="text-slate-500 font-mono">
                            {course.progress.done_count}/{course.lesson_count} done
                          </span>
                        </div>
                        <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              course.progress.completed ? 'bg-emerald-500' : 'bg-emerald-500/70'
                            }`}
                            style={{
                              width: `${Math.min(
                                100,
                                Math.round(
                                  (course.progress.done_count / Math.max(1, course.lesson_count)) * 100
                                )
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="mt-auto pt-4 flex items-center justify-between text-sm text-slate-400">
                      <span>
                        {course.lesson_count} {course.type === 'file' ? 'Lessons' : 'Exercises'}
                      </span>
                      <span
                        className={`flex items-center gap-1 group-hover:translate-x-1 transition-transform opacity-0 group-hover:opacity-100 font-medium ${
                          course.type === 'file' ? 'text-emerald-400' : 'text-blue-400'
                        }`}
                      >
                        {course.progress
                          ? course.progress.completed
                            ? 'Review'
                            : 'Continue'
                          : 'Start'}{' '}
                        <ChevronRight size={16} />
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>

      <WelcomeGate
        isOpen={isAuthModalOpen || isLearningGuideOpen}
        onClose={() => {
          setIsAuthModalOpen(false);
          setIsLearningGuideOpen(false);
        }}
        initialTab={isLearningGuideOpen ? 'modalities' : undefined}
      />
      <CourseBuilder
        isOpen={isCourseBuilderOpen}
        onClose={() => setIsCourseBuilderOpen(false)}
        onBuilt={(slug) => {
          setIsCourseBuilderOpen(false);
          navigate(`/file-course/${slug}`);
        }}
      />
      <LearningProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        initialMode={profileInitialMode}
      />
      {shareModalData && (
        <ShareModal
          isOpen={true}
          onClose={() => setShareModalData(null)}
          courseSlug={shareModalData.courseSlug}
          lessonSlug={shareModalData.lessonSlug}
          title={shareModalData.title}
        />
      )}
      <ImportModal
        isOpen={isImportModalOpen}
        onClose={() => {
          setIsImportModalOpen(false);
          setImportInitialData(null);
          if (window.location.hash.includes('#import') || window.location.hash.includes('#share')) {
            window.history.replaceState(null, '', window.location.pathname);
          }
        }}
        initialData={importInitialData}
      />
    </div>
  );
}
