import { useState, useEffect } from 'react';
import { X, Copy, Check, Download, Share2, Link as LinkIcon, AlertCircle, Loader, FileCode } from 'lucide-react';
import {
  fetchCourseExport,
  fetchLessonExport,
  compressToUrlSafe,
  downloadJsonFile,
  MAX_SHARE_URL_CHARS,
  type AnyShareBundle,
} from '../shareUtils';

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  courseSlug: string;
  lessonSlug?: string | null;
  title: string;
}

export function ShareModal({
  isOpen,
  onClose,
  courseSlug,
  lessonSlug,
  title,
}: ShareModalProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [bundle, setBundle] = useState<AnyShareBundle | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [urlTooLong, setUrlTooLong] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  const isSingleLesson = Boolean(lessonSlug);

  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;
    setLoading(true);
    setError('');
    setBundle(null);
    setShareUrl(null);
    setUrlTooLong(false);
    setCopiedLink(false);
    setCopiedJson(false);

    const loadData = async () => {
      try {
        let exportData: AnyShareBundle;
        if (lessonSlug) {
          exportData = await fetchLessonExport(courseSlug, lessonSlug);
        } else {
          exportData = await fetchCourseExport(courseSlug);
        }

        if (!mounted) return;
        setBundle(exportData);

        // Try to generate compressed share URL
        const jsonStr = JSON.stringify(exportData);
        const compressed = await compressToUrlSafe(jsonStr);

        if (compressed.length <= MAX_SHARE_URL_CHARS) {
          const generatedUrl = `${window.location.origin}/#import=${compressed}`;
          setShareUrl(generatedUrl);
          setUrlTooLong(false);
        } else {
          setShareUrl(null);
          setUrlTooLong(true);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to export bundle');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, [isOpen, courseSlug, lessonSlug]);

  if (!isOpen) return null;

  const handleCopyLink = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      setError('Could not copy link to clipboard');
    }
  };

  const handleCopyJson = async () => {
    if (!bundle) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(bundle, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 2000);
    } catch {
      setError('Could not copy JSON to clipboard');
    }
  };

  const handleDownload = () => {
    if (!bundle) return;
    const filename = isSingleLesson
      ? `lesson-${lessonSlug || 'export'}.baselayer.json`
      : `${courseSlug}.baselayer.json`;
    downloadJsonFile(filename, bundle);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Share2 size={18} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">
                Share {isSingleLesson ? 'Lesson' : 'Course'}
              </h3>
              <p className="text-xs text-slate-400 truncate max-w-xs">{title}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader size={24} className="animate-spin text-emerald-400" />
              <span className="text-xs">Preparing shareable bundle...</span>
            </div>
          ) : (
            <>
              {/* One-Click Share Link Section */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-200 uppercase tracking-wider block flex items-center gap-1.5">
                  <LinkIcon size={14} className="text-emerald-400" />
                  <span>One-Click Share Link</span>
                </label>

                {shareUrl ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={shareUrl}
                      className="flex-1 text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 select-all focus:outline-none"
                    />
                    <button
                      onClick={handleCopyLink}
                      className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                        copiedLink
                          ? 'bg-emerald-600 text-white'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20'
                      }`}
                    >
                      {copiedLink ? <Check size={14} /> : <Copy size={14} />}
                      <span>{copiedLink ? 'Copied!' : 'Copy Link'}</span>
                    </button>
                  </div>
                ) : urlTooLong ? (
                  <p className="text-xs text-slate-400 bg-slate-950/60 border border-slate-800/80 p-3 rounded-lg">
                    This bundle is comprehensive and exceeds safe URL lengths. Share it instantly via the file download or JSON export below.
                  </p>
                ) : null}
              </div>

              {/* Alternative Sharing Options */}
              <div className="pt-3 border-t border-slate-800 space-y-3">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Export & Share Directly
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <button
                    onClick={handleDownload}
                    className="flex items-center justify-center gap-2 p-3 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-slate-700 text-slate-200 hover:text-white text-xs font-medium transition-all group"
                  >
                    <Download size={16} className="text-blue-400 group-hover:scale-110 transition-transform" />
                    <span>Download .json Bundle</span>
                  </button>

                  <button
                    onClick={handleCopyJson}
                    className="flex items-center justify-center gap-2 p-3 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-slate-700 text-slate-200 hover:text-white text-xs font-medium transition-all group"
                  >
                    {copiedJson ? (
                      <Check size={16} className="text-emerald-400" />
                    ) : (
                      <FileCode size={16} className="text-emerald-400 group-hover:scale-110 transition-transform" />
                    )}
                    <span>{copiedJson ? 'JSON Copied!' : 'Copy Raw JSON'}</span>
                  </button>
                </div>
              </div>

              {/* Bundle summary */}
              {bundle && (
                <div className="text-[11px] text-slate-500 pt-2 flex items-center justify-between">
                  <span>
                    Format: BaseLayer Bundle (v{bundle.version})
                  </span>
                  <span>
                    {bundle.kind === 'course'
                      ? `${bundle.lessons.length} lessons`
                      : 'Single lesson'}
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
