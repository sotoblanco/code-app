import Editor from "@monaco-editor/react";

interface CodeEditorProps {
  code: string;
  onChange: (value: string | undefined) => void;
  language?: string;
}

export function CodeEditor({ code, onChange, language = "python" }: CodeEditorProps) {
  return (
    <div className="h-full w-full bg-[#1e1e1e] overflow-hidden rounded-lg shadow-xl border border-gray-800">
      <div className="flex items-center justify-between px-4 py-2 bg-[#252526] text-gray-400 text-sm border-b border-gray-800">
        <span className="font-mono">main.py</span>
        <div className="flex gap-2">
           {/* Add run button here later */}
        </div>
      </div>
      <Editor
        height="100%"
        defaultLanguage={language}
        language={language}
        theme="vs-dark"
        value={code}
        onChange={onChange}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          scrollBeyondLastLine: false,
          padding: { top: 16 },
        }}
      />
    </div>
  );
}
