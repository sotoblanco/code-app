import { useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Copy,
  FileText,
  Loader,
  MessageSquareText,
  Upload,
} from 'lucide-react';
import {
  getCourseBuildInstructions,
  importLearningCourse,
} from '../services/aiService';

interface ChatCourseImportProps {
  topic: string;
  referenceText: string;
  onTopicChange: (value: string) => void;
  onReferenceChange: (value: string) => void;
  onImported: (slug: string) => void;
}

const CHAT_STEPS = [
  {
    label: '1. Topic & notes',
    desc: 'Tell BaseLayer what you want to learn',
  },
  {
    label: '2. Copy the prompt',
    desc: 'Paste it into Gemini, ChatGPT, or Claude',
  },
  {
    label: '3. Paste the reply',
    desc: 'BaseLayer verifies it into a runnable course',
  },
];

/**
 * "No API key? Use any chat" wizard: generates a dead-simple instruction prompt
 * for the learner's topic, asks them to run it in any free chat, then imports
 * the model's reply as a verified BaseLayer course. No AI key is used anywhere.
 */
export default function ChatCourseImport({
  topic,
  referenceText,
  onTopicChange,
  onReferenceChange,
  onImported,
}: ChatCourseImportProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [instructions, setInstructions] = useState('');
  const [replyText, setReplyText] = useState('');
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const generatePrompt = async () => {
    if (!topic.trim()) {
      setError('Tell me what you want to learn first.');
      return;
    }
    setError('');
    setIsGenerating(true);
    try {
      const prompt = await getCourseBuildInstructions(topic, referenceText);
      setInstructions(prompt);
      setStep(2);
    } catch (generateError) {
      setError(
        generateError instanceof Error
          ? generateError.message
          : 'Could not generate the build instructions.',
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const copyInstructions = async () => {
    try {
      await navigator.clipboard.writeText(instructions);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Could not copy automatically - select the text and copy it manually.');
    }
  };

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setReplyText(String(reader.result ?? ''));
      setFileName(file.name);
    };
    reader.onerror = () => setError('Could not read that file.');
    reader.readAsText(file);
  };

  const doImport = async () => {
    if (!replyText.trim()) {
      setError('Paste the model\u2019s reply (or upload its .md/.json file) first.');
      return;
    }
    setError('');
    setIsImporting(true);
    try {
      const result = await importLearningCourse(topic, replyText);
      onImported(result.slug);
    } catch (importError) {
      setError(
        importError instanceof Error
          ? importError.message
          : 'Could not import the course. Is your reply the model\u2019s full course output?',
      );
    } finally {
      setIsImporting(false);
    }
  };

  const canGoNext = step === 1 && !isGenerating && topic.trim().length > 0;

  return (
    <div className="space-y-5">
      {/* Stepper */}
      <div className="flex items-center gap-2">
        {CHAT_STEPS.map((chatStep, idx) => {
          const number = idx + 1;
          const isActive = step === number;
          const isDone = step > number;
          return (
            <div
              key={chatStep.label}
              className={`flex-1 rounded-lg border px-2 py-1.5 text-center ${
                isActive
                  ? 'border-emerald-500/40 bg-emerald-500/10'
                  : isDone
                    ? 'border-emerald-500/20 bg-emerald-500/5'
                    : 'border-slate-800 bg-slate-950/40'
              }`}
            >
              <div
                className={`text-[10px] font-bold uppercase tracking-wide ${
                  isActive || isDone ? 'text-emerald-300' : 'text-slate-500'
                }`}
              >
                {isDone ? <Check size={11} className="inline" /> : <span>{number}.</span>}{' '}
                {chatStep.label}
              </div>
            </div>
          );
        })}
      </div>

      {step === 1 && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            generatePrompt();
          }}
          className="space-y-5"
        >
          <div>
            <label
              htmlFor="chat-course-topic"
              className="mb-2 block text-sm font-semibold text-slate-200"
            >
              What do you want to learn?
            </label>
            <input
              id="chat-course-topic"
              autoFocus
              value={topic}
              onChange={(event) => onTopicChange(event.target.value)}
              placeholder="e.g. numpy broadcasting and matrix multiplication"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none placeholder:text-slate-600 focus:border-emerald-500 text-sm"
            />
          </div>

          <div>
            <label
              htmlFor="chat-course-reference"
              className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"
            >
              <FileText size={15} /> Optional notes, code, or documentation
            </label>
            <textarea
              id="chat-course-reference"
              value={referenceText}
              onChange={(event) => onReferenceChange(event.target.value)}
              placeholder="Paste docs, formulas, or code you want the course to teach with..."
              rows={4}
              className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-xs text-white outline-none placeholder:text-slate-600 focus:border-emerald-500 font-mono"
            />
          </div>

          {error && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              {error}
            </p>
          )}

          <div className="flex items-center justify-between gap-3 pt-2">
            <p className="text-[11px] leading-relaxed text-slate-500 max-w-xs">
              Free forever: works with Gemini, ChatGPT, Claude, or any chat. No API key needed.
            </p>
            <button
              type="submit"
              disabled={!canGoNext}
              className="flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition-colors disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isGenerating ? (
                <>
                  <Loader size={15} className="animate-spin" /> Writing instructions...
                </>
              ) : (
                <>
                  Generate my prompt <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-400">
                  <MessageSquareText size={18} />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white">Your copy-paste prompt</h4>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">
                    Copy it below, paste it into Gemini / ChatGPT / Claude (any free chat), and let
                    the model reply with the course. Then paste that reply back on the next step.
                  </p>
                </div>
              </div>
              <button
                onClick={copyInstructions}
                className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-bold text-slate-100 hover:bg-slate-700 transition-colors"
              >
                {copied ? (
                  <>
                    <Check size={14} className="text-emerald-400" /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={14} /> Copy
                  </>
                )}
              </button>
            </div>

            <pre className="mt-4 max-h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-200 whitespace-pre-wrap custom-scrollbar">
              {instructions}
            </pre>
          </div>

          {error && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              {error}
            </p>
          )}

          <div className="flex justify-between gap-3 pt-1">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
            >
              <ArrowLeft size={14} /> Back
            </button>
            <button
              type="button"
              onClick={() => {
                setError('');
                setStep(3);
              }}
              className="flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition-colors"
            >
              I pasted it into a chat - next <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <div>
            <label
              htmlFor="chat-model-reply"
              className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"
            >
              <MessageSquareText size={15} /> Paste the model&apos;s reply here
            </label>
            <textarea
              id="chat-model-reply"
              value={replyText}
              onChange={(event) => {
                setReplyText(event.target.value);
                setFileName(null);
              }}
              rows={9}
              placeholder="Switch to your chat tab, copy the model's full reply (the ```json course block), and paste it here..."
              className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-xs text-white outline-none placeholder:text-slate-600 focus:border-emerald-500 font-mono"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors"
            >
              <Upload size={14} />
              {fileName ? `Replace ${fileName}` : 'Or upload a .md / .json file'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.markdown,.txt,.json,text/markdown,application/json,text/plain"
              className="hidden"
              onChange={(event) => handleFile(event.target.files?.[0])}
            />
            {fileName && (
              <span className="text-[11px] text-slate-400 truncate">Loaded {fileName}</span>
            )}
          </div>

          {error && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              {error}
            </p>
          )}

          <p className="text-[11px] leading-relaxed text-slate-500">
            BaseLayer runs every lesson in its sandbox before publishing: if a lesson doesn&apos;t
            actually run, the import is refused (nothing is written) and you&apos;ll see why.
          </p>

          <div className="flex justify-between gap-3 pt-1">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
            >
              <ArrowLeft size={14} /> Back
            </button>
            <button
              type="button"
              onClick={doImport}
              disabled={isImporting}
              className="flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-2.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isImporting ? (
                <>
                  <Loader size={15} className="animate-spin" /> Importing &amp; verifying lessons...
                </>
              ) : (
                <>
                  Import &amp; verify course <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
