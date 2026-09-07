import { useState, useEffect } from 'react';
import {
  User,
  Key,
  Layers,
  FolderPlus,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  ExternalLink,
  ArrowRight,
  ArrowLeft,
  X,
  Code2,
  Table,
  PenTool,
  Sparkles,
  RefreshCw,
  Zap,
  Download,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getAiStatus, configureAiKey, type AIStatus, type AIProviderInfo } from '../../services/aiService';

const FALLBACK_PROVIDERS: AIProviderInfo[] = [
  {
    id: 'gemini',
    name: 'Google Gemini',
    needs_key: true,
    default_model: 'gemini-3.5-flash-lite',
    default_base: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    docs_url: 'https://aistudio.google.com/app/apikey',
    blurb: 'Free key from Google AI Studio',
    group: 'free',
    suggested_models: ['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-3.1-flash-lite'],
  },
  {
    id: 'groq',
    name: 'Groq',
    needs_key: true,
    default_model: 'openai/gpt-oss-20b',
    default_base: 'https://api.groq.com/openai/v1',
    docs_url: 'https://console.groq.com/keys',
    blurb: 'Fast cloud models, free tier',
    group: 'free',
    suggested_models: ['openai/gpt-oss-20b', 'llama-3.3-70b-versatile', 'qwen/qwen3.8-27b', 'llama-3.1-8b-instant'],
  },
  {
    id: 'ollama',
    name: 'Ollama',
    needs_key: false,
    default_model: 'llama3.2',
    default_base: 'http://localhost:11434/v1',
    docs_url: 'https://ollama.com',
    blurb: 'Local models, no API key',
    group: 'free',
    suggested_models: ['llama3.2', 'qwen2.5-coder:7b', 'llama3.3'],
  },
  {
    id: 'lmstudio',
    name: 'LM Studio',
    needs_key: false,
    default_model: 'local-model',
    default_base: 'http://localhost:1234/v1',
    docs_url: 'https://lmstudio.ai',
    blurb: 'Local desktop app, no API key',
    group: 'free',
    suggested_models: ['local-model'],
  },
  {
    id: 'openai',
    name: 'OpenAI',
    needs_key: true,
    default_model: 'gpt-5.6-luna',
    default_base: 'https://api.openai.com/v1',
    docs_url: 'https://platform.openai.com/api-keys',
    blurb: 'GPT models',
    group: 'key',
    suggested_models: ['gpt-5.6-luna', 'gpt-5-mini', 'gpt-5.6-terra', 'gpt-6-astra'],
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    needs_key: true,
    default_model: 'openai/gpt-5.6-luna',
    default_base: 'https://openrouter.ai/api/v1',
    docs_url: 'https://openrouter.ai/keys',
    blurb: 'One key, many models',
    group: 'key',
    suggested_models: ['openai/gpt-5.6-luna', 'google/gemini-3.5-flash-lite', 'meta-llama/llama-4-scout', 'deepseek/deepseek-v4-flash-latest'],
  },
  {
    id: 'custom',
    name: 'Custom endpoint',
    needs_key: false,
    default_model: 'gpt-5.6-luna',
    default_base: null,
    docs_url: '',
    blurb: 'Any OpenAI-compatible URL',
    group: 'key',
    suggested_models: ['gpt-5.6-luna'],
  },
];

type ModalTab = 'profile' | 'ai' | 'modalities' | 'customization';

interface LocalWelcomeProps {
  isOpen: boolean;
  onClose: () => void;
  onForbidden?: () => void;
  initialTab?: ModalTab;
}

export function LocalWelcome({
  isOpen,
  onClose,
  onForbidden,
  initialTab,
}: LocalWelcomeProps) {
  const { localWelcome, user, isAuthenticated } = useAuth();
  const [name, setName] = useState(
    () => localStorage.getItem('baselayer_learner_name') || user?.username || ''
  );
  const [activeTab, setActiveTab] = useState<ModalTab>(() => {
    if (initialTab) return initialTab;
    const savedName = localStorage.getItem('baselayer_learner_name');
    return savedName ? 'modalities' : 'profile';
  });

  const [nameError, setNameError] = useState('');
  const [isNameSaving, setIsNameSaving] = useState(false);

  // AI Key state
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [loadingAiStatus, setLoadingAiStatus] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [selectedProvider, setSelectedProvider] = useState('gemini');
  const [modelInput, setModelInput] = useState('gemini-3.5-flash-lite');
  const [apiBaseInput, setApiBaseInput] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [keyFeedback, setKeyFeedback] = useState<{
    message: string;
    isError: boolean;
  } | null>(null);
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);
  const [activeOs, setActiveOs] = useState<'macos' | 'linux' | 'windows'>('macos');

  useEffect(() => {
    if (isOpen) {
      if (initialTab) {
        setActiveTab(initialTab);
      }
      loadAiStatus();
    }
  }, [isOpen, initialTab]);

  const loadAiStatus = async () => {
    setLoadingAiStatus(true);
    try {
      const status = await getAiStatus();
      setAiStatus(status);
      if (status.provider) {
        setSelectedProvider(status.provider);
      }
      if (status.model) {
        setModelInput(status.model);
      }
      if (status.api_base) {
        setApiBaseInput(status.api_base);
      }
      if (!status.configured) {
        setShowKeyInput(true);
      }
    } catch (err) {
      console.error('Failed to load AI status', err);
    } finally {
      setLoadingAiStatus(false);
    }
  };

  if (!isOpen) return null;

  const handleSaveName = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!name.trim()) return;
    setNameError('');
    setIsNameSaving(true);
    try {
      await localWelcome(name.trim());
      localStorage.setItem('baselayer_learner_name', name.trim());
      setActiveTab('ai');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not set name';
      if (message.toLowerCase().includes('disabled')) {
        onForbidden?.();
        return;
      }
      setNameError(message);
    } finally {
      setIsNameSaving(false);
    }
  };

  const providers: AIProviderInfo[] =
    aiStatus?.providers && aiStatus.providers.length > 0
      ? aiStatus.providers
      : FALLBACK_PROVIDERS;
  const currentProvider =
    providers.find((p) => p.id === selectedProvider) ?? providers[0];
  const needsKey = currentProvider?.needs_key ?? true;
  const showBaseField =
    selectedProvider === 'custom' ||
    selectedProvider === 'ollama' ||
    selectedProvider === 'lmstudio';
  const envSnippet = [
    `LLM_PROVIDER=${selectedProvider}`,
    `LLM_MODEL=${modelInput || currentProvider?.default_model || ''}`,
    needsKey ? 'LLM_API_KEY=your_api_key_here' : '# LLM_API_KEY is not required',
    showBaseField
      ? `LLM_API_BASE=${apiBaseInput || currentProvider?.default_base || ''}`
      : null,
  ]
    .filter(Boolean)
    .join('\n');

  const handleSaveKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (needsKey && !apiKeyInput.trim()) return;
    if (selectedProvider === 'custom' && !apiBaseInput.trim()) return;
    setSavingKey(true);
    setKeyFeedback(null);
    try {
      const res = await configureAiKey({
        provider: selectedProvider,
        api_key: apiKeyInput.trim(),
        model: modelInput.trim() || undefined,
        api_base: apiBaseInput.trim() || undefined,
      });
      setKeyFeedback({
        message: res.saved_to_file
          ? `${res.provider || selectedProvider} configured and saved to .env.`
          : 'Provider activated in runtime memory.',
        isError: false,
      });
      setApiKeyInput('');
      setShowKeyInput(false);
      await loadAiStatus();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to configure AI provider';
      setKeyFeedback({ message, isError: true });
    } finally {
      setSavingKey(false);
    }
  };

  const copyEnvSnippet = () => {
    navigator.clipboard.writeText(envSnippet);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  const copyCommand = (cmd: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCommand(cmd);
    setTimeout(() => setCopiedCommand(null), 2000);
  };

  const handleTestAndActivateOllama = async () => {
    setTestingConnection(true);
    setKeyFeedback(null);
    try {
      const res = await configureAiKey({
        provider: 'ollama',
        model: modelInput.trim() || 'llama3.2',
        api_base: apiBaseInput.trim() || undefined,
        test_connection: true,
      });
      setKeyFeedback({
        message:
          res.message ||
          'Ollama connection verified! Activated and saved to .env.',
        isError: false,
      });
      setShowKeyInput(false);
      await loadAiStatus();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Could not reach Ollama';
      setKeyFeedback({ message, isError: true });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleProviderChange = (providerId: string) => {
    setSelectedProvider(providerId);
    const spec = providers.find((p) => p.id === providerId);
    if (spec) {
      setModelInput(spec.default_model);
      setApiBaseInput(spec.default_base || '');
    }
    setShowKeyInput(true);
    setKeyFeedback(null);
  };

  const tabs: { id: ModalTab; label: string; icon: typeof User }[] = [
    { id: 'profile', label: 'Learner', icon: User },
    { id: 'ai', label: 'AI Features', icon: Key },
    { id: 'modalities', label: 'Learning Modalities', icon: Layers },
    { id: 'customization', label: 'Custom Learning', icon: FolderPlus },
  ];

  const currentTabIndex = tabs.findIndex((t) => t.id === activeTab);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
              <Sparkles size={18} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                BaseLayer Local Studio
              </h2>
              <p className="text-xs text-slate-400">
                Configure your local workspace and explore learning options
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            title="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 border-b border-slate-800 bg-slate-950/50 flex gap-2 overflow-x-auto custom-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-3 px-3.5 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
                  isActive
                    ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                <Icon size={14} />
                <span>{tab.label}</span>
                {tab.id === 'ai' && aiStatus && (
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      aiStatus.configured ? 'bg-emerald-400' : 'bg-amber-400'
                    }`}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-6">
          {/* TAB 1: Profile */}
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-5">
                <h3 className="text-base font-semibold text-white mb-1">
                  Local Learner Profile
                </h3>
                <p className="text-sm text-slate-400 mb-4 leading-relaxed">
                  Enter your name or handle. BaseLayer runs locally without requiring
                  external authentication; your name is used to personalize hints,
                  code reviews, and remember your progress on this device.
                </p>

                {nameError && (
                  <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm rounded-lg flex items-center gap-2">
                    <AlertCircle size={16} />
                    <span>{nameError}</span>
                  </div>
                )}

                <form onSubmit={handleSaveName} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5">
                      Your First Name or Handle
                    </label>
                    <input
                      type="text"
                      required
                      minLength={1}
                      maxLength={40}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. Alex"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 text-sm"
                    />
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs text-slate-500">
                      {isAuthenticated
                        ? 'Profile initialized for this local session.'
                        : 'Stored locally in your browser.'}
                    </span>
                    <button
                      type="submit"
                      disabled={isNameSaving || !name.trim()}
                      className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                      <span>{isNameSaving ? 'Saving...' : 'Save & Continue'}</span>
                      <ArrowRight size={14} />
                    </button>
                  </div>
                </form>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 text-xs text-slate-400 space-y-1">
                <p className="font-semibold text-slate-300">Local Privacy Note</p>
                <p>
                  Your code runs directly inside your local environment or isolated
                  containers. No course progress is sent to third-party databases.
                </p>
              </div>
            </div>
          )}

          {/* TAB 2: AI Provider Setup */}
          {activeTab === 'ai' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-semibold text-white mb-1">
                  Pick a model — Gemini is one option, not the only one
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  AI is optional. Coding and spreadsheets work with nothing configured.
                  Fastest free cloud path is a Gemini key from AI Studio. Or run Ollama
                  locally, use Groq&apos;s free tier, or plug in OpenAI / OpenRouter.
                </p>
              </div>

              <div
                className={`p-4 rounded-xl border flex items-start gap-3.5 ${
                  aiStatus?.configured
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                    : 'bg-slate-900/80 border-slate-700 text-slate-300'
                }`}
              >
                {aiStatus?.configured ? (
                  <CheckCircle2 size={20} className="text-emerald-400 mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle size={20} className="text-slate-400 mt-0.5 shrink-0" />
                )}
                <div className="space-y-1 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-white">
                      {aiStatus?.configured
                        ? `AI active · ${aiStatus.provider} · ${aiStatus.model}`
                        : 'No provider yet — skip this tab if you just want to code'}
                    </p>
                    <button
                      onClick={loadAiStatus}
                      disabled={loadingAiStatus}
                      className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition-colors shrink-0"
                      title="Refresh status"
                    >
                      <RefreshCw size={12} className={loadingAiStatus ? 'animate-spin' : ''} />
                      <span>Refresh</span>
                    </button>
                  </div>
                  {aiStatus?.configured && !showKeyInput && (
                    <button
                      onClick={() => setShowKeyInput(true)}
                      className="text-xs text-emerald-400 hover:text-emerald-300 underline font-medium"
                    >
                      Change provider
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Free to start
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {providers
                    .filter((p) => p.group === 'free')
                    .map((p) => {
                      const selected = selectedProvider === p.id;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => handleProviderChange(p.id)}
                          className={`text-left rounded-xl border p-3.5 transition-colors ${
                            selected
                              ? 'border-emerald-500/50 bg-emerald-500/10'
                              : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'
                          }`}
                        >
                          <p className="text-sm font-semibold text-white">{p.name}</p>
                          <p className="text-xs text-slate-400 mt-0.5">{p.blurb}</p>
                        </button>
                      );
                    })}
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Bring your own key
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {providers
                    .filter((p) => p.group !== 'free')
                    .map((p) => {
                      const selected = selectedProvider === p.id;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => handleProviderChange(p.id)}
                          className={`text-left rounded-xl border p-3.5 transition-colors ${
                            selected
                              ? 'border-emerald-500/50 bg-emerald-500/10'
                              : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'
                          }`}
                        >
                          <p className="text-sm font-semibold text-white">{p.name}</p>
                          <p className="text-xs text-slate-400 mt-0.5">{p.blurb}</p>
                        </button>
                      );
                    })}
                </div>
              </div>

              {keyFeedback && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                    keyFeedback.isError
                      ? 'bg-rose-500/10 border border-rose-500/20 text-rose-300'
                      : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300'
                  }`}
                >
                  {keyFeedback.isError ? (
                    <AlertCircle size={15} />
                  ) : (
                    <CheckCircle2 size={15} />
                  )}
                  <span>{keyFeedback.message}</span>
                </div>
              )}

              {(showKeyInput || !aiStatus?.configured) && (
                selectedProvider === 'ollama' ? (
                  <div className="border border-slate-800 bg-slate-950/70 rounded-xl p-5 space-y-5">
                    {/* Header & Quick Intro */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800/80">
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                          <Zap size={16} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-white">
                            Ollama Setup: 100% Free &amp; Local AI
                          </h4>
                          <p className="text-xs text-slate-400">
                            Zero API keys, completely private, runs entirely on your machine.
                          </p>
                        </div>
                      </div>
                      <a
                        href="https://github.com/sotoblanco/BaseLayer/blob/main/docs/ollama_setup.md"
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 shrink-0 font-medium transition-colors"
                      >
                        <span>Full Setup Guide (docs/ollama_setup.md)</span>
                        <ExternalLink size={12} />
                      </a>
                    </div>

                    {/* Step 1: Install Ollama */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-bold">
                            1
                          </span>
                          <span className="text-xs font-semibold text-slate-200">
                            Install Ollama
                          </span>
                        </div>
                        <div className="flex items-center gap-1 bg-slate-900 p-0.5 rounded-lg border border-slate-800 text-[11px]">
                          {(['macos', 'linux', 'windows'] as const).map((os) => (
                            <button
                              key={os}
                              type="button"
                              onClick={() => setActiveOs(os)}
                              className={`px-2 py-0.5 rounded capitalize font-medium transition-colors ${
                                activeOs === os
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                  : 'text-slate-400 hover:text-slate-200'
                              }`}
                            >
                              {os === 'macos' ? 'macOS' : os === 'linux' ? 'Linux' : 'Windows'}
                            </button>
                          ))}
                        </div>
                      </div>

                      {activeOs === 'macos' && (
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between bg-slate-900/90 border border-slate-800 rounded-lg px-3 py-2 font-mono text-xs text-emerald-400">
                            <span>brew install ollama</span>
                            <button
                              type="button"
                              onClick={() => copyCommand('brew install ollama')}
                              className="text-slate-400 hover:text-white flex items-center gap-1 text-[11px] transition-colors ml-2"
                            >
                              {copiedCommand === 'brew install ollama' ? (
                                <Check size={12} className="text-emerald-400" />
                              ) : (
                                <Copy size={12} />
                              )}
                              <span>{copiedCommand === 'brew install ollama' ? 'Copied' : 'Copy'}</span>
                            </button>
                          </div>
                          <p className="text-[11px] text-slate-400">
                            Or download the macOS desktop app from{' '}
                            <a
                              href="https://ollama.com/download"
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-400 hover:underline inline-flex items-center gap-0.5"
                            >
                              ollama.com/download <ExternalLink size={10} />
                            </a>
                          </p>
                        </div>
                      )}

                      {activeOs === 'linux' && (
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between bg-slate-900/90 border border-slate-800 rounded-lg px-3 py-2 font-mono text-xs text-emerald-400">
                            <span className="truncate">curl -fsSL https://ollama.com/install.sh | sh</span>
                            <button
                              type="button"
                              onClick={() => copyCommand('curl -fsSL https://ollama.com/install.sh | sh')}
                              className="text-slate-400 hover:text-white flex items-center gap-1 text-[11px] transition-colors ml-2 shrink-0"
                            >
                              {copiedCommand === 'curl -fsSL https://ollama.com/install.sh | sh' ? (
                                <Check size={12} className="text-emerald-400" />
                              ) : (
                                <Copy size={12} />
                              )}
                              <span>{copiedCommand === 'curl -fsSL https://ollama.com/install.sh | sh' ? 'Copied' : 'Copy'}</span>
                            </button>
                          </div>
                          <p className="text-[11px] text-slate-400">
                            Auto-detects NVIDIA CUDA and AMD ROCm GPUs for hardware acceleration.
                          </p>
                        </div>
                      )}

                      {activeOs === 'windows' && (
                        <div className="space-y-1.5">
                          <div className="bg-slate-900/90 border border-slate-800 rounded-lg px-3 py-2 flex items-center justify-between">
                            <span className="text-xs text-slate-300">Download Windows installer from ollama.com</span>
                            <a
                              href="https://ollama.com/download"
                              target="_blank"
                              rel="noreferrer"
                              className="text-emerald-400 hover:text-emerald-300 text-xs font-semibold flex items-center gap-1 transition-colors"
                            >
                              <Download size={13} />
                              <span>Download (.exe)</span>
                            </a>
                          </div>
                          <p className="text-[11px] text-slate-400">
                            Also works inside WSL2 with GPU passthrough.
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Step 2: Pull a recommended model */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-bold">
                          2
                        </span>
                        <span className="text-xs font-semibold text-slate-200">
                          Pull a recommended model
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Run one of these commands in your terminal:
                      </p>

                      <div className="grid grid-cols-1 gap-2">
                        {/* Model 1: Llama 3.2 */}
                        <div
                          className={`p-2.5 rounded-lg border transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                            modelInput === 'llama3.2'
                              ? 'border-emerald-500/50 bg-emerald-500/10'
                              : 'border-slate-800 bg-slate-900/70 hover:border-slate-700'
                          }`}
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-white">llama3.2</span>
                              <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-medium">
                                Default · 3B (~4GB RAM)
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400">
                              Fast, lightweight, ideal for laptops and SocratiQ tutoring hints.
                            </p>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center">
                            <button
                              type="button"
                              onClick={() => copyCommand('ollama pull llama3.2')}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-mono flex items-center gap-1 transition-colors"
                              title="Copy command"
                            >
                              {copiedCommand === 'ollama pull llama3.2' ? (
                                <Check size={11} className="text-emerald-400" />
                              ) : (
                                <Copy size={11} />
                              )}
                              <span>ollama pull llama3.2</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => setModelInput('llama3.2')}
                              className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                                modelInput === 'llama3.2'
                                  ? 'bg-emerald-500/30 text-emerald-200 border border-emerald-500/40'
                                  : 'bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200'
                              }`}
                            >
                              {modelInput === 'llama3.2' ? 'Selected' : 'Use'}
                            </button>
                          </div>
                        </div>

                        {/* Model 2: Qwen 2.5 Coder 7B */}
                        <div
                          className={`p-2.5 rounded-lg border transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                            modelInput === 'qwen2.5-coder:7b'
                              ? 'border-emerald-500/50 bg-emerald-500/10'
                              : 'border-slate-800 bg-slate-900/70 hover:border-slate-700'
                          }`}
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-white">qwen2.5-coder:7b</span>
                              <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-medium">
                                Best for Coding · 7B (~8GB RAM)
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400">
                              Tailored for programming intuition, unit tests, and course creation.
                            </p>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center">
                            <button
                              type="button"
                              onClick={() => copyCommand('ollama pull qwen2.5-coder:7b')}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-mono flex items-center gap-1 transition-colors"
                              title="Copy command"
                            >
                              {copiedCommand === 'ollama pull qwen2.5-coder:7b' ? (
                                <Check size={11} className="text-emerald-400" />
                              ) : (
                                <Copy size={11} />
                              )}
                              <span>ollama pull qwen2.5-coder:7b</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => setModelInput('qwen2.5-coder:7b')}
                              className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                                modelInput === 'qwen2.5-coder:7b'
                                  ? 'bg-emerald-500/30 text-emerald-200 border border-emerald-500/40'
                                  : 'bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200'
                              }`}
                            >
                              {modelInput === 'qwen2.5-coder:7b' ? 'Selected' : 'Use'}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Step 3: Run Ollama */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-bold">
                          3
                        </span>
                        <span className="text-xs font-semibold text-slate-200">
                          Run Ollama &amp; Connect
                        </span>
                      </div>

                      <div className="flex items-center justify-between bg-slate-900/90 border border-slate-800 rounded-lg px-3 py-2 font-mono text-xs text-emerald-400">
                        <span>ollama serve</span>
                        <button
                          type="button"
                          onClick={() => copyCommand('ollama serve')}
                          className="text-slate-400 hover:text-white flex items-center gap-1 text-[11px] transition-colors ml-2"
                        >
                          {copiedCommand === 'ollama serve' ? (
                            <Check size={12} className="text-emerald-400" />
                          ) : (
                            <Copy size={12} />
                          )}
                          <span>{copiedCommand === 'ollama serve' ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Starts the server on <code className="font-mono text-slate-300">http://localhost:11434/v1</code>. (The desktop app runs automatically in the background).
                      </p>
                    </div>

                    {/* Endpoint & Model Details (Editable) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
                      <div>
                        <label className="block text-[11px] font-medium text-slate-300 mb-1">
                          Active Model
                        </label>
                        <input
                          type="text"
                          value={modelInput}
                          onChange={(e) => setModelInput(e.target.value)}
                          placeholder="llama3.2"
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-slate-300 mb-1">
                          API Base URL
                        </label>
                        <input
                          type="text"
                          value={apiBaseInput}
                          onChange={(e) => setApiBaseInput(e.target.value)}
                          placeholder="http://localhost:11434/v1"
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                        />
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between pt-2 gap-2.5">
                      <span className="text-[11px] text-slate-400">
                        Docker / remote? Set <code className="font-mono text-slate-300">OLLAMA_ORIGINS=&quot;*&quot;</code>
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleSaveKey}
                          disabled={savingKey || testingConnection}
                          className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          {savingKey ? 'Saving...' : 'Save without testing'}
                        </button>
                        <button
                          type="button"
                          onClick={handleTestAndActivateOllama}
                          disabled={testingConnection || savingKey}
                          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-lg shadow-emerald-950/40"
                        >
                          {testingConnection ? (
                            <RefreshCw size={13} className="animate-spin" />
                          ) : (
                            <Zap size={13} />
                          )}
                          <span>{testingConnection ? 'Testing...' : 'Test connection & Activate Ollama'}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-5 space-y-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                      Connect {currentProvider?.name || 'provider'}
                    </h4>

                    <form onSubmit={handleSaveKey} className="space-y-3">
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <label className="block text-xs font-medium text-slate-300">
                            Model
                          </label>
                          {currentProvider?.default_model && (
                            <span className="text-[11px] text-slate-400">
                              Default: <span className="font-mono text-emerald-400">{currentProvider.default_model}</span> (recommended best value)
                            </span>
                          )}
                        </div>
                        <input
                          type="text"
                          value={modelInput}
                          onChange={(e) => setModelInput(e.target.value)}
                          placeholder={currentProvider?.default_model || 'model name'}
                          className="w-full px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                        />
                        {currentProvider?.suggested_models && currentProvider.suggested_models.length > 0 && (
                          <div className="mt-2 space-y-1.5">
                            <span className="text-[11px] text-slate-400 block">
                              Suggested models:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {currentProvider.suggested_models.map((m) => {
                                const isSelected = modelInput === m;
                                const isDefault = m === currentProvider.default_model;
                                return (
                                  <button
                                    key={m}
                                    type="button"
                                    onClick={() => setModelInput(m)}
                                    className={`px-2.5 py-1 rounded text-xs font-mono transition-colors flex items-center gap-1.5 ${
                                      isSelected
                                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                        : 'bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800'
                                    }`}
                                  >
                                    <span>{m}</span>
                                    {isDefault && (
                                      <span className="text-[9px] uppercase tracking-wide px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-sans font-medium">
                                        Best Value
                                      </span>
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>

                      {showBaseField && (
                        <div>
                          <label className="block text-xs font-medium text-slate-300 mb-1.5">
                            API base URL
                          </label>
                          <input
                            type="text"
                            value={apiBaseInput}
                            onChange={(e) => setApiBaseInput(e.target.value)}
                            placeholder={currentProvider?.default_base || 'https://.../v1'}
                            className="w-full px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                          />
                        </div>
                      )}

                      {needsKey && (
                        <div>
                          <label className="block text-xs font-medium text-slate-300 mb-1.5">
                            API key
                          </label>
                          <input
                            type="password"
                            autoComplete="off"
                            value={apiKeyInput}
                            onChange={(e) => setApiKeyInput(e.target.value)}
                            placeholder={
                              selectedProvider === 'gemini'
                                ? 'Paste your Gemini API key'
                                : 'Paste your API key'
                            }
                            className="w-full px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                          />
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-1 gap-3">
                        {currentProvider?.docs_url ? (
                          <a
                            href={currentProvider.docs_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
                          >
                            <span>
                              {selectedProvider === 'gemini'
                                ? 'Get a free key from Google AI Studio'
                                : needsKey
                                  ? `Get a ${currentProvider.name} key`
                                  : `Install ${currentProvider.name}`}
                            </span>
                            <ExternalLink size={12} />
                          </a>
                        ) : (
                          <span className="text-xs text-slate-500">Any OpenAI-compatible server</span>
                        )}

                        <button
                          type="submit"
                          disabled={
                            savingKey ||
                            (needsKey && !apiKeyInput.trim()) ||
                            (selectedProvider === 'custom' && !apiBaseInput.trim())
                          }
                          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors disabled:opacity-50 flex items-center gap-1.5 shrink-0"
                        >
                          <Key size={13} />
                          <span>{savingKey ? 'Saving...' : 'Save to .env'}</span>
                        </button>
                      </div>
                    </form>
                  </div>
                )
              )}

              <div className="border border-slate-800 bg-slate-950/40 rounded-xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Or set it in .env
                  </h4>
                  <button
                    onClick={copyEnvSnippet}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
                  >
                    {copiedSnippet ? (
                      <Check size={13} className="text-emerald-400" />
                    ) : (
                      <Copy size={13} />
                    )}
                    <span>{copiedSnippet ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                  {envSnippet}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 3: Learning Modalities */}
          {activeTab === 'modalities' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-semibold text-white mb-1">
                  How You Learn: Three Core Modalities
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  BaseLayer combines practical programming, tactile mathematical intuition,
                  and visual verification into one cohesive learning environment.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Modality 1 */}
                <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-4 flex flex-col justify-between space-y-3">
                  <div className="space-y-2.5">
                    <div className="p-2 w-fit bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400">
                      <Code2 size={20} />
                    </div>
                    <h4 className="text-sm font-bold text-white">Coding Studio</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Write real Python or Rust code in a full Monaco editor. Run tests
                      instantly with Docker sandboxing.
                    </p>
                  </div>
                  <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-blue-400" />
                      <span>Isolated Docker execution</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-blue-400" />
                      <span>Automated unit assertions</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-blue-400" />
                      <span>Reference solution reveals</span>
                    </div>
                  </div>
                </div>

                {/* Modality 2 */}
                <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-4 flex flex-col justify-between space-y-3">
                  <div className="space-y-2.5">
                    <div className="p-2 w-fit bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
                      <Table size={20} />
                    </div>
                    <h4 className="text-sm font-bold text-white">Spreadsheet Workspace</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Build physical intuition for tensors and matrices using embedded
                      Google Sheets formulas before coding.
                    </p>
                  </div>
                  <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-emerald-400" />
                      <span>Matrix math (MMULT, broadcasting)</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-emerald-400" />
                      <span>Direct 2D/3D visual layout</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-emerald-400" />
                      <span>Interactive formula calculations</span>
                    </div>
                  </div>
                </div>

                {/* Modality 3 */}
                <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-4 flex flex-col justify-between space-y-3">
                  <div className="space-y-2.5">
                    <div className="p-2 w-fit bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400">
                      <PenTool size={20} />
                    </div>
                    <h4 className="text-sm font-bold text-white">Hand Drawing Verification</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Draw data flows, weights, and layer connections directly over diagrams.
                      Graded visually by your connected LLM.
                    </p>
                  </div>
                  <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-rose-400" />
                      <span>Integrated drawing canvas</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-rose-400" />
                      <span>Multimodal AI visual grading</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <CheckCircle2 size={12} className="text-rose-400" />
                      <span>Focus on conceptual intent</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* SocratiQ Callout */}
              <div className="border border-slate-800 bg-slate-950/50 rounded-xl p-4 flex items-center gap-4">
                <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 shrink-0">
                  <Sparkles size={22} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    SocratiQ AI Tutor
                  </h4>
                  <p className="text-xs text-slate-400 leading-relaxed mt-0.5">
                    Available in the right-hand panel of coding exercises. Ask for guidance,
                    syntax explanations, or debugging tips. SocratiQ guides you with
                    questions rather than giving away code answers.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: Custom Learning */}
          {activeTab === 'customization' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-semibold text-white mb-1">
                  Customize & Author Your Own Learning
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  BaseLayer is not limited to built-in courses. The file-based architecture
                  lets you design custom curricula, exercises, and study notes by simply
                  creating folders on your disk.
                </p>
              </div>

              {/* Architecture Explanation */}
              <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-5 space-y-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  File-Based Course Structure
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Add a new folder inside <code>courses/</code>. The backend dynamically
                  discovers your exercises without any database migration:
                </p>

                <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 space-y-1">
                  <p className="text-slate-500"># Inside the courses/ directory:</p>
                  <p className="text-emerald-400">courses/your-topic/</p>
                  <p className="text-slate-300">├── README.md &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Course overview</p>
                  <p className="text-emerald-400">└── lesson-01-introduction/</p>
                  <p className="text-slate-300">&nbsp;&nbsp;&nbsp;&nbsp;├── README.md &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Lesson instructions</p>
                  <p className="text-slate-300">&nbsp;&nbsp;&nbsp;&nbsp;├── main.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Starter code in editor</p>
                  <p className="text-slate-300">&nbsp;&nbsp;&nbsp;&nbsp;├── test.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Automated tests</p>
                  <p className="text-slate-300">&nbsp;&nbsp;&nbsp;&nbsp;└── solution.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# (Optional) Reference solution</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-slate-400 pt-1">
                  <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg space-y-1">
                    <p className="font-semibold text-slate-200">For Rust Exercises</p>
                    <p>
                      Use <code>main.rs</code>, <code>test.rs</code>, and{' '}
                      <code>solution.rs</code>. BaseLayer automatically detects Rust syntax.
                    </p>
                  </div>
                  <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg space-y-1">
                    <p className="font-semibold text-slate-200">For Google Sheets Exercises</p>
                    <p>
                      Include <code>metadata.json</code> containing{' '}
                      <code>&quot;exercise_type&quot;: &quot;spreadsheet&quot;</code> and your Sheet ID.
                    </p>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 text-xs text-slate-400 space-y-1">
                <p className="font-semibold text-slate-300">Live Reloading</p>
                <p>
                  As soon as you save or edit files in <code>courses/</code>, refreshing the
                  courses page or exercise view immediately reflects your changes.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900 flex items-center justify-between">
          <div>
            {currentTabIndex > 0 ? (
              <button
                onClick={() => setActiveTab(tabs[currentTabIndex - 1].id)}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-3 py-2 rounded-lg border border-slate-800 hover:bg-slate-800 transition-colors"
              >
                <ArrowLeft size={13} />
                <span>Previous</span>
              </button>
            ) : (
              <span className="text-xs text-slate-500">Local Studio Mode</span>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            {currentTabIndex < tabs.length - 1 ? (
              <button
                onClick={() => setActiveTab(tabs[currentTabIndex + 1].id)}
                className="flex items-center gap-1.5 text-xs font-bold text-white bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg transition-colors border border-slate-700"
              >
                <span>Next</span>
                <ArrowRight size={13} />
              </button>
            ) : null}

            <button
              onClick={onClose}
              className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors shadow-md"
            >
              Start Learning
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

