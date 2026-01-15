import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';

interface MarkdownViewerProps {
    content: string;
}

const InteractiveCheckbox = (props: any) => {
    const [checked, setChecked] = React.useState(props.checked);

    return (
        <input
            {...props}
            type="checkbox"
            checked={checked}
            disabled={false} // Force enable
            onChange={(e) => setChecked(e.target.checked)}
            className="interactive-checkbox mr-2 w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-900 cursor-pointer"
        />
    );
};

const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ content }) => {
    return (
        <div className="prose prose-invert prose-blue max-w-none p-8 font-sans interactive-markdown">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                    input: (props) => {
                        if (props.type === 'checkbox') {
                            return <InteractiveCheckbox {...props} />;
                        }
                        return <input {...props} />;
                    },
                    li: ({ children, className, ...props }) => {
                        // Check if this list item contains a checkbox
                        // React components structure might be complex, but usually the checkbox is the first child
                        // We can rely on CSS :has() for the strikethrough, so strict filtering here strictly for styling inputs might not be needed
                        // But we pass props through.
                        return <li className={className} {...props}>{children}</li>
                    }
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}

export default MarkdownViewer;
