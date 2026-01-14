import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User as UserIcon, Loader } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';
import { discussImplementation } from '../services/aiService';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface AIChatPanelProps {
    context: string;
}

export default function AIChatPanel({ context }: AIChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: "Greetings, Apprentice! I am **Boots**, the Master of Code and Casting. How may I assist you with your spell-casting (coding) today?" }
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setIsLoading(true);

        try {
            const response = await discussImplementation(userMessage, context);
            setMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
        } catch (error) {
            setMessages(prev => [...prev, { role: 'assistant', content: "My mana is low... I cannot respond right now." }]);
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-[#1e1e1e] border-t border-slate-800">
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 bg-slate-900/50 border-b border-slate-800">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center border border-blue-400 shadow shadow-blue-500/20">
                    {/* Bear/Wizard Icon Placeholder - using Bot for now */}
                    <Bot size={18} className="text-white" />
                </div>
                <div>
                    <h3 className="text-sm font-semibold text-slate-200">Boots the Wizard</h3>
                    <p className="text-xs text-blue-400">Master of Code & Casting</p>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 ${msg.role === 'user' ? 'bg-slate-700' : 'bg-blue-600/20 border border-blue-500/30'}`}>
                            {msg.role === 'user' ? <UserIcon size={16} /> : <Bot size={16} className="text-blue-400" />}
                        </div>

                        <div className={`rounded-xl px-4 py-3 text-sm max-w-[85%] shadow-sm ${msg.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : 'bg-[#252526] text-slate-200 border border-slate-700/50'
                            }`}>
                            {msg.role === 'user' ? (
                                <p>{msg.content}</p>
                            ) : (
                                <div className="markdown-prose space-y-3">
                                    <ReactMarkdown
                                        children={msg.content}
                                        remarkPlugins={[remarkGfm]}
                                        rehypePlugins={[rehypeHighlight]}
                                        components={{
                                            // Styling markdown elements
                                            code({ node, inline, className, children, ...props }: any) {
                                                const match = /language-(\w+)/.exec(className || '')
                                                return !inline && match ? (
                                                    <div className="rounded-lg overflow-hidden my-2 border border-slate-700">
                                                        <div className="bg-slate-900/50 px-3 py-1 text-xs text-slate-400 border-b border-slate-700 font-mono">
                                                            {match[1]}
                                                        </div>
                                                        <div className="bg-[#1e1e1e] p-3 overflow-x-auto">
                                                            <code className={className} {...props}>
                                                                {children}
                                                            </code>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <code className="bg-slate-800/80 px-1.5 py-0.5 rounded text-blue-300 font-mono text-xs border border-slate-700/50" {...props}>
                                                        {children}
                                                    </code>
                                                )
                                            },
                                            p: ({ children }) => <p className="leading-relaxed">{children}</p>,
                                            ul: ({ children }) => <ul className="list-disc pl-4 space-y-1">{children}</ul>,
                                            ol: ({ children }) => <ol className="list-decimal pl-4 space-y-1">{children}</ol>,
                                            h1: ({ children }) => <h1 className="text-lg font-bold text-slate-100">{children}</h1>,
                                            h2: ({ children }) => <h2 className="text-base font-semibold text-slate-100">{children}</h2>,
                                            h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-100">{children}</h3>,
                                            blockquote: ({ children }) => <blockquote className="border-l-2 border-blue-500 pl-3 italic text-slate-400">{children}</blockquote>,
                                            a: ({ href, children }) => <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer">{children}</a>
                                        }}
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                ))}
                {isLoading && (
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0">
                            <Bot size={16} className="text-blue-400" />
                        </div>
                        <div className="bg-slate-800 rounded-lg px-4 py-2 border border-slate-700 flex items-center">
                            <Loader size={16} className="animate-spin text-slate-400" />
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 bg-slate-900/30 border-t border-slate-800">
                <div className="relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder="Ask Boots a question..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-4 pr-10 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 placeholder:text-slate-600 transition-all"
                        disabled={isLoading}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isLoading}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-blue-400 disabled:opacity-50 disabled:hover:text-slate-400 transition-colors"
                    >
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
}
