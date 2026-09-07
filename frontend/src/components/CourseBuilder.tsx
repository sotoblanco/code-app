import { useState, useEffect } from 'react';
import {
  Sparkles,
  X,
  FileText,
  BookOpen,
  Loader,
  CheckCircle2,
  Layers,
  User,
  Wrench,
  GraduationCap,
  ArrowRight,
  MessageSquareText,
  AlertTriangle,
} from 'lucide-react';
import {
  buildLearningCourse,
  getAiStatus,
  type BuildCourseResult,
} from '../services/aiService';
import ChatCourseImport from './ChatCourseImport';

interface CourseBuilderProps {
  isOpen: boolean;
  onClose: () => void;
  onBuilt: (slug: string) => void;
}

type BuilderTab = 'agentic' | 'chat';

const AGENT_WORKFLOW_STEPS = [
  {
    tool_name: 'get_learning_intent',
    label: '1. Intent & Concepts',
    desc: 'Extracting core concepts and searching platform course anchors',
    icon: Layers,
  },
  {
    tool_name: 'get_context_learning',
    label: '2. Learner Profile',
    desc: 'Retrieving personal preferences, level, and modalities',
    icon: User,
  },
  {
    tool_name: 'get_platform_content_tools',
    label: '3. Platform Tools',
    desc: 'Querying Code Sandbox, Google Sheets, and Hand Drawing',
    icon: Wrench,
  },
  {
    tool_name: 'curate_solveit_course',
    label: '4. Solveit Curation',
    desc: 'Applying micro-steps (1-3 lines), toy data, and narrative arc',
    icon: GraduationCap,
  },
];

export default function CourseBuilder({ isOpen, onClose, onBuilt }: CourseBuilderProps) {
  const [activeTab, setActiveTab] = useState<BuilderTab>('agentic');
  const [topic, setTopic] = useState('');
  const [referenceText, setReferenceText] = useState('');
  const [error, setError] = useState('');
  const [isBuilding, setIsBuilding] = useState(false);
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [completedResult, setCompletedResult] = useState<BuildCourseResult | null>(null);
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    if (isBuilding && !completedResult) {
      timer = setInterval(() => {
        setActiveStepIndex((prev) => (prev < 3 ? prev + 1 : prev));
      }, 1200);
    }
    return () => clearInterval(timer);
  }, [isBuilding, completedResult]);

  // On every open: refresh AI status and pick the tab that actually works for
  // this learner (no key configured -> default to the copy-paste chat path).
  useEffect(() => {
    if (!isOpen) return;
    setError('');
    setCompletedResult(null);
    setIsBuilding(false);
    setActiveStepIndex(0);
    setAiLoading(true);
    getAiStatus()
      .then((status) => {
        setAiConfigured(status.configured);
        setActiveTab(status.configured ? 'agentic' : 'chat');
      })
      .catch(() => {
        // Status unknown: the copy-paste path needs no key, so default to it.
        setAiConfigured(false);
        setActiveTab('chat');
      })
      .finally(() => setAiLoading(false));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!topic.trim()) {
      setError('Tell me what you want to learn.');
      return;
    }

    if (aiConfigured === false) {
      setError(
        'No AI provider is configured here, so the agentic builder cannot run. Use the "No API key?" tab instead: paste a short prompt into any free chat and import the result.',
      );
      setActiveTab('chat');
      return;
    }

    setError('');
    setIsBuilding(true);
    setActiveStepIndex(0);
    setCompletedResult(null);

    try {
      const result = await buildLearningCourse(topic, referenceText);
      setCompletedResult(result);
      setActiveStepIndex(4);
    } catch (buildError) {
      setError(buildError instanceof Error ? buildError.message : 'Could not build the course.');
      setIsBuilding(false);
    }
  };

  const handleLaunchCourse = () => {
    if (completedResult) {
      onBuilt(completedResult.slug);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-start justify-between border-b border-slate-800 p-6 bg-slate-900/90">
          <div className="flex gap-3">
            <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-400">
              <Sparkles size={20} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Build a course</h2>
              <p className="mt-1 text-xs text-slate-400">
                {activeTab === 'agentic'
                  ? 'Agentic 4-step builder (needs an AI key configured here)'
                  : 'Copy one prompt into any chat - no API key required'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-2 border-b border-slate-800 bg-slate-950/60 px-6 pt-3">
          <button
            onClick={() => setActiveTab('agentic')}
            className={`flex items-center gap-2 rounded-t-lg px-4 py-2 text-xs font-bold transition-colors ${
              activeTab === 'agentic'
                ? 'border border-b-0 border-slate-700 bg-slate-900 text-emerald-300'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <Sparkles size={14} className="text-emerald-400" />
            With an AI key
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-semibold text-slate-400 uppercase">
              agentic
            </span>
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 rounded-t-lg px-4 py-2 text-xs font-bold transition-colors ${
              activeTab === 'chat'
                ? 'border border-b-0 border-slate-700 bg-slate-900 text-emerald-300'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <MessageSquareText size={14} className="text-blue-400" />
            No API key? Use any chat
            <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-400 uppercase">
              free
            </span>
          </button>
        </div>

        <div className="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-5">
          {aiLoading && activeTab === 'agentic' && aiConfigured === null ? (
            <div className="flex items-center justify-center gap-2 py-16 text-xs text-slate-400">
              <Loader size={16} className="animate-spin text-emerald-400" /> Checking your AI setup...
            </div>
          ) : activeTab === 'chat' ? (
            <ChatCourseImport
              topic={topic}
              referenceText={referenceText}
              onTopicChange={setTopic}
              onReferenceChange={setReferenceText}
              onImported={onBuilt}
            />
          ) : (
            <>
              {aiConfigured === false && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-400" />
                    <div className="space-y-2">
                      <p className="text-xs font-bold text-amber-300">
                        No AI provider is configured here.
                      </p>
                      <p className="text-[11px] leading-relaxed text-amber-200/80">
                        The agentic builder needs an API key on this device. The
                        &ldquo;No API key?&rdquo; tab works with any free chat (Gemini, ChatGPT,
                        Claude) and needs nothing installed.
                      </p>
                      <button
                        onClick={() => {
                          setError('');
                          setActiveTab('chat');
                        }}
                        className="flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-1.5 text-[11px] font-bold text-slate-950 hover:bg-emerald-400 transition-colors"
                      >
                        Use any chat instead <ArrowRight size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {!isBuilding && !completedResult ? (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div>
                    <label
                      htmlFor="course-topic"
                      className="mb-2 block text-sm font-semibold text-slate-200"
                    >
                      What do you want to learn?
                    </label>
                    <input
                      id="course-topic"
                      autoFocus
                      value={topic}
                      onChange={(event) => setTopic(event.target.value)}
                      placeholder="e.g. NumPy broadcasting and matrix multiplication"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none placeholder:text-slate-600 focus:border-emerald-500 text-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="course-reference"
                      className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"
                    >
                      <FileText size={15} /> Optional notes, code, or documentation
                    </label>
                    <textarea
                      id="course-reference"
                      value={referenceText}
                      onChange={(event) => setReferenceText(event.target.value)}
                      placeholder="Paste relevant documentation excerpts, formulas, or code snippets to ground your lessons..."
                      rows={4}
                      className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-xs text-white outline-none placeholder:text-slate-600 focus:border-emerald-500 font-mono"
                    />
                  </div>

                  {/* Agentic workflow step preview */}
                  <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 space-y-2.5 text-xs text-slate-400">
                    <div className="flex items-center gap-2 font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
                      <Sparkles size={13} className="text-emerald-400" />
                      <span>Agent Workflow Pipeline (4 Tool Calls)</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-emerald-400 font-bold">1. Learning Intent</span>
                        <p className="text-slate-500 mt-0.5">Extracts concepts & course anchors</p>
                      </div>
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-blue-400 font-bold">2. Learner Profile</span>
                        <p className="text-slate-500 mt-0.5">Personalizes level & preferred modality</p>
                      </div>
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-amber-400 font-bold">3. Platform Tools</span>
                        <p className="text-slate-500 mt-0.5">Code, Sheets, and Hand Drawing</p>
                      </div>
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-purple-400 font-bold">4. Solveit Curation</span>
                        <p className="text-slate-500 mt-0.5">Toy data, 1-3 line tasks, live inspect</p>
                      </div>
                    </div>
                  </div>

                  {error && (
                    <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
                      {error}
                    </p>
                  )}

                  <div className="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={onClose}
                      className="rounded-lg px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition-colors"
                    >
                      <Sparkles size={15} />
                      <span>Build my course</span>
                    </button>
                  </div>
                </form>
              ) : isBuilding && !completedResult ? (
                /* Active Agentic Workflow Progress View */
                <div className="py-4 space-y-6">
                  <div className="text-center space-y-1">
                    <h3 className="text-base font-bold text-white">Agent is Crafting Your Course</h3>
                    <p className="text-xs text-slate-400">
                      Running tool calls to ground and personalize your curriculum...
                    </p>
                  </div>

                  <div className="space-y-3">
                    {AGENT_WORKFLOW_STEPS.map((step, idx) => {
                      const Icon = step.icon;
                      const isDone = activeStepIndex > idx;
                      const isCurrent = activeStepIndex === idx;

                      return (
                        <div
                          key={step.tool_name}
                          className={`p-3.5 rounded-xl border flex items-center gap-3.5 transition-all ${
                            isDone
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                              : isCurrent
                                ? 'border-blue-500/40 bg-blue-500/10 text-white animate-pulse'
                                : 'border-slate-800 bg-slate-950/40 text-slate-500'
                          }`}
                        >
                          <div
                            className={`p-2 rounded-lg ${
                              isDone
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : isCurrent
                                  ? 'bg-blue-500/20 text-blue-400'
                                  : 'bg-slate-900 text-slate-600'
                            }`}
                          >
                            {isDone ? (
                              <CheckCircle2 size={16} className="text-emerald-400" />
                            ) : isCurrent ? (
                              <Loader size={16} className="animate-spin text-blue-400" />
                            ) : (
                              <Icon size={16} />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold">{step.label}</span>
                              <span className="text-[10px] font-mono opacity-70 font-semibold">
                                {isDone ? 'COMPLETED' : isCurrent ? 'EXECUTING...' : 'QUEUED'}
                              </span>
                            </div>
                            <p className="text-[11px] opacity-80 mt-0.5 truncate">{step.desc}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-center text-xs text-slate-400">
                    <BookOpen size={14} className="inline mr-1.5 text-emerald-400" />
                    Solveit ensures no 50-line code dumps: each lesson is a 1-3 line micro-step verified on toy data.
                  </div>
                </div>
              ) : (
                /* Completed Course Ready View */
                <div className="py-2 space-y-5">
                  <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 space-y-2">
                    <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                      <CheckCircle2 size={18} />
                      <span>Course Successfully Built & Materialized!</span>
                    </div>
                    <h3 className="text-lg font-extrabold text-white">{completedResult?.title}</h3>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {completedResult?.narrative_arc || completedResult?.description}
                    </p>
                    <div className="pt-2 flex items-center gap-3 text-xs text-emerald-300 font-mono">
                      <span>{completedResult?.lesson_count} Micro-Lessons</span>
                      <span>•</span>
                      <span>Solveit Verified</span>
                    </div>
                  </div>

                  {completedResult?.tool_traces && completedResult.tool_traces.length > 0 && (
                    <div className="border border-slate-800 bg-slate-950/50 rounded-xl p-4 space-y-2">
                      <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                        Agent Execution Trace
                      </h4>
                      <div className="space-y-1.5 text-[11px] font-mono">
                        {completedResult.tool_traces.map((trace, i) => (
                          <div key={i} className="p-2 rounded bg-slate-900/80 border border-slate-800 flex items-start gap-2">
                            <span className="text-emerald-400 font-bold shrink-0">{trace.tool_name}:</span>
                            <span className="text-slate-300 truncate">{trace.output_summary}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={onClose}
                      className="rounded-lg px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                    >
                      Back to Courses
                    </button>
                    <button
                      type="button"
                      onClick={handleLaunchCourse}
                      className="flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-2.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition-colors"
                    >
                      <span>Start Learning</span>
                      <ArrowRight size={14} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
