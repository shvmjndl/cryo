/**
 * Shared chat message renderer — used by both ChatPage and WorkspaceNode.
 * Single source of truth for markdown rendering, file cards, and message styling.
 */

import { Dna, User, GitBranch, FileText, ExternalLink } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'

export interface ChatMsg {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string | null
}

interface Props {
  message: ChatMsg
  compact?: boolean          // smaller text for workspace nodes
  onBranch?: (content: string) => void  // if provided, shows branch button
}

// ─── File link detection ───

function extractFileLinks(content: string) {
  const links: { url: string; filename: string; type: string }[] = []
  const seen = new Set<string>()

  // Match both /api/reports/filename and bare report_*.ext filenames
  const patterns = [
    /\/api\/reports\/(report_[a-zA-Z0-9_\-]+\.(html|pdf|xlsx|png|csv))/g,
    /(?:^|\s|\()(report_[a-zA-Z0-9_\-]+\.(html|pdf|xlsx|png|csv))/gm,
  ]

  for (const pattern of patterns) {
    let m
    while ((m = pattern.exec(content)) !== null) {
      const filename = m[1]
      if (seen.has(filename)) continue
      seen.add(filename)
      const ext = m[2]
      const type = ext === 'html' ? 'Interactive Report' : ext === 'pdf' ? 'PDF Report' : ext === 'xlsx' ? 'Excel' : ext === 'png' ? 'Chart' : 'File'
      links.push({ url: `/api/reports/${filename}`, filename, type })
    }
  }
  return links
}

// ─── Markdown components ───

function getMarkdownComponents(compact: boolean): Components {
  const sz = compact ? 'text-xs' : 'text-sm'
  const hsz = compact ? 'text-sm' : 'text-lg'
  const h3sz = compact ? 'text-xs' : 'text-base'

  return {
    h1: ({ children }) => <h1 className={`${hsz} font-bold text-[var(--color-cryo-text)] mt-3 mb-1.5 pb-1 border-b border-[var(--color-cryo-border)]`}>{children}</h1>,
    h2: ({ children }) => <h2 className={`${hsz} font-semibold text-[var(--color-cryo-cyan)] mt-3 mb-1.5 pb-1 border-b border-[var(--color-cryo-border)]`}>{children}</h2>,
    h3: ({ children }) => <h3 className={`${h3sz} font-semibold text-[var(--color-cryo-accent)] mt-2 mb-1`}>{children}</h3>,
    h4: ({ children }) => <h4 className={`${sz} font-semibold text-[var(--color-cryo-text)] mt-2 mb-1`}>{children}</h4>,
    p: ({ children }) => <p className={`${sz} leading-relaxed text-[var(--color-cryo-text)] mb-2`}>{children}</p>,
    strong: ({ children }) => <strong className="font-semibold text-[var(--color-cryo-text)]">{children}</strong>,
    em: ({ children }) => <em className="italic text-[var(--color-cryo-text-dim)]">{children}</em>,
    ul: ({ children }) => <ul className="list-none space-y-1 my-1.5 ml-1">{children}</ul>,
    ol: ({ children }) => <ol className={`list-decimal list-inside space-y-1 my-1.5 ml-1 ${sz} text-[var(--color-cryo-text)]`}>{children}</ol>,
    li: ({ children }) => (
      <li className={`${sz} text-[var(--color-cryo-text)] flex items-start gap-1.5`}>
        <span className="text-[var(--color-cryo-accent)] mt-0.5 flex-shrink-0">•</span>
        <span className="flex-1">{children}</span>
      </li>
    ),
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noopener noreferrer"
        className="text-[var(--color-cryo-accent)] hover:text-[var(--color-cryo-cyan)] underline underline-offset-2 decoration-[var(--color-cryo-accent)]/30 transition-colors">
        {children}
      </a>
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-[var(--color-cryo-accent)] bg-[var(--color-cryo-accent)]/5 rounded-r-lg px-3 py-1.5 my-2 text-[var(--color-cryo-text-dim)] italic">
        {children}
      </blockquote>
    ),
    code: ({ className, children }) => {
      if (className?.includes('language-')) {
        return <code className={`block ${compact ? 'text-[10px]' : 'text-xs'} font-mono text-[var(--color-cryo-cyan)]`}>{children}</code>
      }
      return <code className={`${compact ? 'text-[10px]' : 'text-xs'} font-mono bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-cyan)] px-1 py-0.5 rounded`}>{children}</code>
    },
    pre: ({ children }) => <pre className="bg-[var(--color-cryo-bg)] border border-[var(--color-cryo-border)] rounded-lg p-2.5 my-2 overflow-x-auto">{children}</pre>,
    table: ({ children }) => (
      <div className="overflow-x-auto my-2 rounded-lg border border-[var(--color-cryo-border)]">
        <table className={`w-full ${compact ? 'text-[10px]' : 'text-xs'}`}>{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-[var(--color-cryo-surface-2)]">{children}</thead>,
    th: ({ children }) => <th className={`px-2.5 py-1.5 text-left font-semibold text-[var(--color-cryo-accent)] ${compact ? 'text-[9px]' : 'text-[10px]'} uppercase tracking-wider border-b border-[var(--color-cryo-border-bright)]`}>{children}</th>,
    td: ({ children }) => <td className="px-2.5 py-1.5 text-[var(--color-cryo-text-dim)] border-b border-[var(--color-cryo-border)]">{children}</td>,
    tr: ({ children }) => <tr className="hover:bg-[var(--color-cryo-surface-2)] transition-colors">{children}</tr>,
    hr: () => <hr className="border-[var(--color-cryo-border)] my-3" />,
  }
}

// ─── File Card ───

function FileCard({ url, filename, type }: { url: string; filename: string; type: string }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer"
      className="flex items-center gap-2 px-3 py-2 mt-2 rounded-lg border border-[var(--color-cryo-border-bright)] bg-[var(--color-cryo-surface-2)] hover:bg-[var(--color-cryo-surface-3)] hover:border-[var(--color-cryo-accent)]/40 transition-all group">
      <FileText className="w-4 h-4 text-[var(--color-cryo-accent)]" />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-[var(--color-cryo-text)] truncate">{filename}</div>
        <div className="text-[10px] text-[var(--color-cryo-text-dim)]">{type}</div>
      </div>
      <ExternalLink className="w-3 h-3 text-[var(--color-cryo-text-muted)] group-hover:text-[var(--color-cryo-accent)] transition-colors" />
    </a>
  )
}

// ─── Main Component ───

export default function ChatMessage({ message, compact = false, onBranch }: Props) {
  const isUser = message.role === 'user'
  const content = message.content || ''
  const fileLinks = extractFileLinks(content)
  const components = getMarkdownComponents(compact)

  return (
    <div className={`relative ${isUser ? 'chat-node-msg-user' : 'chat-node-msg-assistant'} chat-node-msg`}>
      <div className={`flex items-start gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* Avatar */}
        <div className={`${compact ? 'w-5 h-5' : 'w-7 h-7'} rounded flex items-center justify-center flex-shrink-0 mt-0.5 ${
          isUser ? 'bg-[var(--color-cryo-surface-3)]' : 'bg-[var(--color-cryo-accent)]/15'
        }`}>
          {isUser
            ? <User className={`${compact ? 'w-3 h-3' : 'w-3.5 h-3.5'} text-[var(--color-cryo-text-dim)]`} />
            : <Dna className={`${compact ? 'w-3 h-3' : 'w-3.5 h-3.5'} text-[var(--color-cryo-accent)]`} strokeWidth={1.5} />
          }
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0" style={{ userSelect: 'text' }}>
          <ReactMarkdown components={components}>{content}</ReactMarkdown>

          {/* File download cards */}
          {fileLinks.length > 0 && (
            <div className="space-y-1.5">
              {fileLinks.map(link => <FileCard key={link.url} {...link} />)}
            </div>
          )}
        </div>
      </div>

      {/* Branch button (workspace only) */}
      {onBranch && !isUser && (
        <button onClick={() => onBranch(content)} className="branch-btn" title="Branch into new node">
          <GitBranch className="w-3 h-3" /> Branch
        </button>
      )}
    </div>
  )
}
