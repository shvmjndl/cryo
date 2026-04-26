/**
 * Shared chat message renderer — used by both ChatPage and WorkspaceNode.
 * Single source of truth for markdown rendering, file cards, and message styling.
 */

import { Dna, User, GitBranch, FileText, ExternalLink, PanelRight } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { StructureViewer } from './StructureViewer'

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

// ─── Strip :::block syntax from chat display ───
// These blocks (:::chart, :::diagram, etc.) are for the HTML report renderer only.
// In chat, replace with a clean icon + title line so the message stays readable.

const BLOCK_ICONS: Record<string, string> = {
  chart: '📊', diagram: '🔀', callout: '💡',
  timeline: '📅', progress: '📈', table: '📋',
}

function cleanBlockSyntax(content: string): string {
  // Multiline: :::type optional-title\ncontent\n:::
  content = content.replace(/:::(\w+)[^\n]*\n([\s\S]*?):::/g, (_, type, inner) => {
    const icon = BLOCK_ICONS[type] || '📄'
    const firstLine = inner.trim().split('\n')[0].trim()
    return firstLine ? `*${icon} ${firstLine}*` : ''
  })
  // Inline prefix on a list item: :::type rest of content :::
  content = content.replace(/:::(chart|diagram|callout|timeline|progress|table)\s+/gi, (_, type) =>
    `${BLOCK_ICONS[type.toLowerCase()] || '📄'} `
  )
  // Remove any remaining closing ::: markers
  content = content.replace(/\s*:::\s*/g, ' ')
  // Collapse triple+ newlines left by removed blocks
  return content.replace(/\n{3,}/g, '\n\n')
}

// ─── 3D structure tag extraction ───

function extractStructures(content: string): { pdbId: string; title?: string }[] {
  const pattern = /\[3D:([A-Z0-9]{4})(?:\|([^\]]+))?\]/gi
  const seen = new Set<string>()
  const results: { pdbId: string; title?: string }[] = []
  let m
  while ((m = pattern.exec(content)) !== null) {
    const id = m[1].toUpperCase()
    if (seen.has(id)) continue
    seen.add(id)
    results.push({ pdbId: id, title: m[2]?.trim() })
  }
  return results
}

function stripStructureTags(content: string): string {
  return content.replace(/\[3D:[A-Z0-9]{4}(?:\|[^\]]+)?\]/gi, '').replace(/\n{3,}/g, '\n\n').trim()
}

// ─── File link detection ───

function extractFileLinks(content: string) {
  const links: { url: string; filename: string; type: string }[] = []
  const seen = new Set<string>()

  const addLink = (filename: string) => {
    if (!filename || seen.has(filename)) return
    seen.add(filename)
    const ext = filename.split('.').pop()?.toLowerCase() || ''
    const type = ext === 'html' ? 'Interactive Report' : ext === 'pdf' ? 'PDF Report' : ext === 'xlsx' ? 'Excel' : ext === 'png' ? 'Chart' : ext === 'md' ? 'Markdown Report' : 'File'
    links.push({ url: `/api/reports/${filename}`, filename, type })
  }

  // Match report filenames anywhere in the content — works for links, code spans, plain text
  const pat = /(report_[a-zA-Z0-9_\-]+\.(html|pdf|xlsx|png|csv|md))/g
  let m
  while ((m = pat.exec(content)) !== null) {
    addLink(m[1])
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
    a: ({ href, children }) => {
      const isHtmlReport = !!href && /\/api\/reports\/.*\.html/.test(href)
      const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
        if (!isHtmlReport || !href) return
        e.preventDefault()
        const filename = href.split('/').pop() || href
        window.dispatchEvent(new CustomEvent('cryo:open-report', { detail: { url: href, filename } }))
      }
      return (
        <a
          href={href}
          onClick={isHtmlReport ? handleClick : undefined}
          target={isHtmlReport ? undefined : '_blank'}
          rel="noopener noreferrer"
          className={`underline underline-offset-2 transition-colors ${
            isHtmlReport
              ? 'text-[var(--color-cryo-cyan)] hover:text-[var(--color-cryo-accent)] decoration-[var(--color-cryo-cyan)]/40 cursor-pointer'
              : 'text-[var(--color-cryo-accent)] hover:text-[var(--color-cryo-cyan)] decoration-[var(--color-cryo-accent)]/30'
          }`}
        >
          {children}
        </a>
      )
    },
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-[var(--color-cryo-accent)] bg-[var(--color-cryo-accent)]/5 rounded-r-lg px-3 py-1.5 my-2 text-[var(--color-cryo-text-dim)] italic">
        {children}
      </blockquote>
    ),
    code: ({ className, children }) => {
      const text = String(children ?? '')
      // Inline report filename — make it clickable to open panel
      if (!className && /^report_[a-zA-Z0-9_\-]+\.html$/.test(text.trim())) {
        const filename = text.trim()
        const url = `/api/reports/${filename}`
        return (
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('cryo:open-report', { detail: { url, filename } }))}
            className={`${compact ? 'text-[10px]' : 'text-xs'} font-mono bg-[var(--color-cryo-cyan)]/10 text-[var(--color-cryo-cyan)] px-1.5 py-0.5 rounded border border-[var(--color-cryo-cyan)]/20 hover:bg-[var(--color-cryo-cyan)]/20 transition-colors cursor-pointer underline underline-offset-2`}
            title="Click to view report"
          >
            {text}
          </button>
        )
      }
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

// ─── File Card — fires custom event to open right-side panel ───

function FileCard({ url, filename, type }: { url: string; filename: string; type: string }) {
  const isHtml = type === 'Interactive Report'

  const openPanel = () => {
    window.dispatchEvent(new CustomEvent('cryo:open-report', { detail: { url, filename } }))
  }

  return (
    <div
      className={`mt-2 flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--color-cryo-border-bright)] bg-[var(--color-cryo-surface-2)] transition-all group ${
        isHtml ? 'cursor-pointer hover:bg-[var(--color-cryo-cyan)]/5 hover:border-[var(--color-cryo-cyan)]/40' : 'hover:bg-[var(--color-cryo-surface-3)] hover:border-[var(--color-cryo-accent)]/40'
      }`}
      onClick={isHtml ? openPanel : undefined}
      title={isHtml ? 'Click to view report' : undefined}
    >
      <FileText className={`w-4 h-4 flex-shrink-0 ${isHtml ? 'text-[var(--color-cryo-cyan)]' : 'text-[var(--color-cryo-accent)]'}`} />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-[var(--color-cryo-text)] truncate">{filename}</div>
        <div className="text-[10px] text-[var(--color-cryo-text-dim)]">{isHtml ? 'Click to view · ' : ''}{type}</div>
      </div>
      <div className="flex items-center gap-1">
        {isHtml && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--color-cryo-cyan)] opacity-60 group-hover:opacity-100 transition-opacity">
            <PanelRight className="w-3 h-3" /> View
          </span>
        )}
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => e.stopPropagation()}
          className="p-1 rounded hover:bg-[var(--color-cryo-surface-3)] transition-colors"
          title="Open in new tab"
        >
          <ExternalLink className="w-3.5 h-3.5 text-[var(--color-cryo-text-muted)] group-hover:text-[var(--color-cryo-accent)] transition-colors" />
        </a>
      </div>
    </div>
  )
}

// ─── Main Component ───

export default function ChatMessage({ message, compact = false, onBranch }: Props) {
  const isUser = message.role === 'user'
  const rawContent = message.content || ''
  // Clean :::block syntax before any further processing
  const content = isUser ? rawContent : cleanBlockSyntax(rawContent)
  const structures = isUser ? [] : extractStructures(content)
  const displayContent = structures.length > 0 ? stripStructureTags(content) : content
  const fileLinks = extractFileLinks(rawContent) // scan raw content for links (before block stripping removes urls)
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
          <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>

          {/* 3D structure viewers */}
          {structures.map(s => (
            <StructureViewer key={s.pdbId} pdbId={s.pdbId} title={s.title} compact={compact} />
          ))}

          {/* File cards with inline viewer for HTML reports */}
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
