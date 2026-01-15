import { useState } from 'react';
import { X, Save, Edit3, Eye, Play, RotateCw } from 'lucide-react';
import { Panel, Group, Separator } from 'react-resizable-panels';
import { CodeEditor } from './CodeEditor';
import MarkdownViewer from './MarkdownViewer';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import confetti from 'canvas-confetti';

interface ExercisePreviewProps {
    title: string;
    description: string;
    initialCode: string;
    testCode: string;
    language: string;
    passingRule?: string; // New prop
    onSave?: (data: { description: string; initialCode: string; testCode: string; passingRule: string }) => void;
    onClose?: () => void;
}

export default function ExercisePreview({
    title,
    description,
    initialCode,
    testCode,
    language,
    passingRule = "tests_pass",
    onSave,
    onClose
}: ExercisePreviewProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editedDescription, setEditedDescription] = useState(description);
    const [editedCode, setEditedCode] = useState(initialCode);
    const [editedTestCode, setEditedTestCode] = useState(testCode);
    const [editedPassingRule, setEditedPassingRule] = useState(passingRule);
    const [editorTab, setEditorTab] = useState<'main' | 'tests'>('main');

    // Code execution state
    const [output, setOutput] = useState<string>('');
    const [isRunning, setIsRunning] = useState(false);
    const { token } = useAuth();

    const currentLang = language || 'python';
    const mainFilename = currentLang === 'rust' ? 'main.rs' : 'main.py';
    const testsFilename = currentLang === 'rust' ? 'tests.rs' : 'tests.py';

    const handleSave = () => {
        if (onSave) {
            onSave({
                description: editedDescription,
                initialCode: editedCode,
                testCode: editedTestCode,
                passingRule: editedPassingRule
            });
        }
        setIsEditing(false);
    };

    const handleCancel = () => {
        setEditedDescription(description);
        setEditedCode(initialCode);
        setEditedTestCode(testCode);
        setEditedPassingRule(passingRule);
        setIsEditing(false);
    };

    const handleRun = async () => {
        setIsRunning(true);
        setOutput("Running...");

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
                    code: editedCode + "\n\n" + editedTestCode,
                    language: currentLang
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

    const handleReset = () => {
        setEditedCode(initialCode);
        setOutput('');
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="w-[95vw] h-[90vh] bg-slate-950 rounded-xl border border-slate-700 shadow-2xl flex flex-col overflow-hidden">

                {/* Header */}
                <header className="h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6 shrink-0">
                    <div className="flex items-center gap-4">
                        <h1 className="font-semibold text-lg tracking-tight text-white">{title}</h1>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            {currentLang === 'rust' ? 'Rust' : currentLang === 'javascript' ? 'JavaScript' : 'Python'}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                            Preview Mode
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        {isEditing ? (
                            <>
                                <select
                                    value={editedPassingRule}
                                    onChange={(e) => setEditedPassingRule(e.target.value)}
                                    className="bg-slate-900 border border-slate-700 text-slate-300 text-xs rounded px-2 py-1 outline-none focus:ring-1 focus:ring-blue-500 mr-2"
                                >
                                    <option value="tests_pass">Tests Pass</option>
                                    <option value="ai_eval">AI Evaluation</option>
                                    <option value="manual">Manual Approval</option>
                                </select>
                                <button
                                    onClick={handleCancel}
                                    className="px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleSave}
                                    className="flex items-center gap-2 px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm font-medium rounded transition-colors"
                                >
                                    <Save size={16} /> Save Changes
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={() => setIsEditing(true)}
                                className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors"
                            >
                                <Edit3 size={16} /> Edit
                            </button>
                        )}
                        <div className="w-px h-6 bg-slate-800 mx-2" />
                        <button
                            onClick={onClose}
                            className="p-2 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                            title="Close Preview"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </header>

                {/* Main Content - Split View */}
                <div className="flex-1 flex overflow-hidden">
                    <Group orientation="horizontal" id="preview-main-group" style={{ height: '100%', width: '100%' }}>

                        {/* Left: Instructions */}
                        <Panel defaultSize={40} minSize={20} id="preview-left-panel" className="flex flex-col bg-slate-950/50">
                            <div className="h-10 border-b border-slate-800 flex items-center px-4 bg-slate-900">
                                <span className="text-sm font-medium text-slate-400 flex items-center gap-2">
                                    {isEditing ? <Edit3 size={14} /> : <Eye size={14} />}
                                    {isEditing ? 'Edit Description' : 'Description Preview'}
                                </span>
                            </div>

                            <div className="flex-1 overflow-y-auto custom-scrollbar border-r border-slate-800">
                                {isEditing ? (
                                    <div className="h-full flex flex-col">
                                        <textarea
                                            className="flex-1 w-full bg-slate-950 text-slate-200 p-4 font-mono text-sm resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 border-b border-slate-800"
                                            value={editedDescription}
                                            onChange={(e) => setEditedDescription(e.target.value)}
                                            placeholder="Enter markdown description..."
                                        />
                                        <div className="h-1/3 overflow-y-auto border-t border-slate-700 bg-slate-900/50">
                                            <div className="p-2 text-xs text-slate-500 border-b border-slate-800 bg-slate-900">
                                                Live Preview
                                            </div>
                                            <MarkdownViewer content={editedDescription} />
                                        </div>
                                    </div>
                                ) : (
                                    <MarkdownViewer content={editedDescription} />
                                )}
                            </div>
                        </Panel>

                        <Separator className="w-1.5 bg-slate-900 border-l border-slate-800 hover:bg-blue-500 transition-colors cursor-col-resize flex items-center justify-center z-10" />

                        {/* Right: Code & Output */}
                        <Panel defaultSize={60} minSize={20} id="preview-code-panel" className="flex flex-col bg-[#1e1e1e]">
                            <Group orientation="vertical" id="preview-editor-group" style={{ height: '100%', width: '100%' }}>

                                {/* Editor */}
                                <Panel defaultSize={70} minSize={20} id="preview-editor" className="flex flex-col">
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
                                        </div>
                                        {isEditing && (
                                            <span className="text-xs text-green-400 flex items-center gap-1">
                                                <Edit3 size={12} /> Editing
                                            </span>
                                        )}
                                    </div>

                                    {/* Editor Area */}
                                    <div className="flex-1 min-h-0 relative">
                                        <div className="absolute inset-0" style={{ display: editorTab === 'main' ? 'block' : 'none' }}>
                                            <CodeEditor
                                                key="preview-editor-main"
                                                code={editedCode}
                                                onChange={(val) => setEditedCode(val || "")}
                                                language={currentLang}
                                                filename={mainFilename}
                                            />
                                        </div>
                                        <div className="absolute inset-0" style={{ display: editorTab === 'tests' ? 'block' : 'none' }}>
                                            <CodeEditor
                                                key="preview-editor-tests"
                                                code={editedTestCode}
                                                onChange={(val) => isEditing && setEditedTestCode(val || "")}
                                                language={currentLang}
                                                filename={testsFilename}
                                                readOnly={!isEditing}
                                            />
                                        </div>
                                    </div>
                                </Panel>

                                <Separator className="h-1.5 bg-[#252526] border-t border-[#333] hover:bg-blue-500 transition-colors cursor-row-resize flex items-center justify-center z-10" />

                                {/* Output / Console Panel */}
                                <Panel defaultSize={30} minSize={10} id="preview-console" className="flex flex-col bg-[#1e1e1e]">
                                    <div className="h-10 flex items-center justify-between px-4 border-b border-[#333] bg-[#252526]">
                                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Console Output</span>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={handleReset}
                                                className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium rounded transition-colors"
                                            >
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
                                            <span className="text-slate-600 italic">
                                                Run your code to see output...
                                            </span>
                                        )}
                                    </div>
                                </Panel>
                            </Group>
                        </Panel>
                    </Group>
                </div>
            </div>
        </div>
    );
}
