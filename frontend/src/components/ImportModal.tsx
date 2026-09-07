import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  Upload,
  FileCode,
  CheckCircle2,
  AlertCircle,
  Loader,
  BookOpen,
  Sparkles,
  Layers,
} from 'lucide-react';
import {
  postImportBundle,
  decompressFromUrlSafe,
  type ImportBundleRequest,
  type ImportBundleResponse,
} from '../shareUtils';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialData?: string | null;
  onImportSuccess?: (result: ImportBundleResponse) => void;
}

export function ImportModal({
  isOpen,
  onClose,
  initialData,
  onImportSuccess,
}: ImportModalProps) {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [rawInput, setRawInput] = useState('');
  const [parsedBundle, setParsedBundle] = useState<ImportBundleRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  const [successResult, setSuccessResult] = useState<ImportBundleResponse | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    setError('');
    setSuccessResult(null);

    if (initialData) {
      handleParseIncomingData(initialData);
    } else {
      setRawInput('');
      setParsedBundle(null);
    }
  }, [isOpen, initialData]);

  const handleParseIncomingData = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) {
      setParsedBundle(null);
      return;
    }

    setLoading(true);
    setError('');

    try {
      let jsonString = trimmed;

      // Check if it's a URL with #import= or #share=
      if (trimmed.includes('#import=')) {
        const token = trimmed.split('#import=')[1].split('&')[0];
        jsonString = await decompressFromUrlSafe(token);
      } else if (trimmed.includes('#share=')) {
        const token = trimmed.split('#share=')[1].split('&')[0];
        jsonString = await decompressFromUrlSafe(token);
      } else if (trimmed.startsWith('c:') || trimmed.startsWith('u:')) {
        jsonString = await decompressFromUrlSafe(trimmed);
      }

      const parsed = JSON.parse(jsonString);

      // Validate bundle shape
      if (!parsed || typeof parsed !== 'object') {
        throw new Error('Invalid bundle format');
      }

      if (parsed.kind === 'course' && (!parsed.lessons || !Array.isArray(parsed.lessons))) {
        throw new Error('Course bundle must contain a lessons array.');
      }

      if (parsed.kind === 'lesson' && !parsed.lesson && (!parsed.lessons || !parsed.lessons.length)) {
        throw new Error('Lesson bundle must contain lesson data.');
      }

      setParsedBundle(parsed as ImportBundleRequest);
      setRawInput(trimmed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid course or lesson bundle format');
      setParsedBundle(null);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      handleParseIncomingData(content);
    };
    reader.onerror = () => {
      setError('Failed to read file');
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!parsedBundle) return;

    setImporting(true);
    setError('');

    try {
      const result = await postImportBundle(parsedBundle);
      setSuccessResult(result);
      if (onImportSuccess) {
        onImportSuccess(result);
      }

      // Navigate after 1.2s to newly imported course/lesson
      setTimeout(() => {
        onClose();
        if (result.lesson_slug) {
          navigate(`/file-course/${result.course_slug}/${result.lesson_slug}`);
        } else {
          navigate(`/file-course/${result.course_slug}`);
        }
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Upload size={18} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Import Course or Lesson</h3>
              <p className="text-xs text-slate-400">Load a shared bundle into your local platform</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}

          {successResult ? (
            <div className="py-8 flex flex-col items-center justify-center gap-3 text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <CheckCircle2 size={24} />
              </div>
              <h4 className="text-sm font-bold text-white">{successResult.message}</h4>
              <p className="text-xs text-slate-400">Opening course in editor...</p>
            </div>
          ) : !parsedBundle ? (
            <>
              {/* Dropzone & Upload */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-800 hover:border-blue-500/50 rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer bg-slate-950/40 hover:bg-slate-950/80 transition-all group text-center"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".json,.txt"
                  className="hidden"
                />
                <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-blue-400 transition-colors">
                  <FileCode size={20} />
                </div>
                <div>
                  <span className="text-xs font-semibold text-slate-200 group-hover:text-white transition-colors">
                    Click to upload .json file
                  </span>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Supports BaseLayer course and lesson bundles
                  </p>
                </div>
              </div>

              {/* Paste Text / URL input */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                  Or Paste JSON / Share Link
                </label>
                <textarea
                  value={rawInput}
                  onChange={(e) => handleParseIncomingData(e.target.value)}
                  placeholder="Paste raw bundle JSON or a https://...#import= link here"
                  rows={4}
                  className="w-full text-xs font-mono bg-slate-950 border border-slate-800 rounded-xl p-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </>
          ) : (
            /* Live Preview Card */
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 capitalize">
                    {parsedBundle.kind === 'course' ? (
                      <>
                        <BookOpen size={12} /> Course Bundle
                      </>
                    ) : (
                      <>
                        <Layers size={12} /> Single Lesson
                      </>
                    )}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {parsedBundle.kind === 'course'
                      ? `${parsedBundle.lessons?.length || 0} Lessons`
                      : '1 Lesson'}
                  </span>
                </div>

                <div>
                  <h4 className="text-sm font-bold text-white">
                    {parsedBundle.title || parsedBundle.lesson?.title || 'Untitled'}
                  </h4>
                  {(parsedBundle.description || parsedBundle.lesson?.description) && (
                    <p className="text-xs text-slate-400 line-clamp-2 mt-1">
                      {parsedBundle.description || parsedBundle.lesson?.description}
                    </p>
                  )}
                </div>

                {/* Skills tags */}
                {((parsedBundle.skills && parsedBundle.skills.length > 0) ||
                  (parsedBundle.lesson?.skills && parsedBundle.lesson.skills.length > 0)) && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {(parsedBundle.skills || parsedBundle.lesson?.skills || []).map((skill) => (
                      <span
                        key={skill}
                        className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setParsedBundle(null);
                    setRawInput('');
                  }}
                  className="px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  Choose Different Bundle
                </button>

                <button
                  type="button"
                  onClick={handleImport}
                  disabled={importing || loading}
                  className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 transition-all shrink-0 shadow-lg shadow-blue-500/10"
                >
                  {importing ? (
                    <Loader size={14} className="animate-spin" />
                  ) : (
                    <Sparkles size={14} />
                  )}
                  <span>Import & Start Learning</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
