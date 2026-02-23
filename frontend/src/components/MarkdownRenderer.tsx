import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { CSSProperties } from "react";

interface Props {
  content: string;
  className?: string;
  fontSize?: number;
}

const inlineCodeStyle: CSSProperties = {
  background: "rgba(0,0,0,0.06)",
  padding: "2px 6px",
  borderRadius: 4,
  fontSize: "0.9em",
  fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
  wordBreak: "break-all",
};

export default function MarkdownRenderer({
  content,
  className = "",
  fontSize = 14,
}: Props) {
  return (
    <div
      className={`md-body ${className}`}
      style={{ fontSize, lineHeight: 1.7 }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className: codeClass, children, ...props }) {
            const match = /language-(\w+)/.exec(codeClass || "");
            const codeStr = String(children).replace(/\n$/, "");
            if (!match) {
              return (
                <code style={inlineCodeStyle} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <SyntaxHighlighter
                language={match[1]}
                style={oneDark}
                customStyle={{
                  fontSize: 13,
                  borderRadius: 8,
                  padding: "14px 16px",
                  margin: "12px 0",
                }}
                showLineNumbers={codeStr.split("\n").length > 4}
              >
                {codeStr}
              </SyntaxHighlighter>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
          table({ children }) {
            return (
              <div style={{ overflowX: "auto", margin: "12px 0" }}>
                <table className="md-table">{children}</table>
              </div>
            );
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#1677ff", textDecoration: "none" }}
              >
                {children}
              </a>
            );
          },
          blockquote({ children }) {
            return (
              <blockquote className="md-blockquote">{children}</blockquote>
            );
          },
          hr() {
            return <hr className="md-hr" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
