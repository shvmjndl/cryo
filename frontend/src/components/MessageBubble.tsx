import { User, Dna, Wrench, FileText, FileSpreadsheet, BarChart3, Download, ExternalLink } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: any
}

interface Props {
  message: Message
  bionicMode?: boolean
}

// Bionic reading: bold the first ~half of each word, skip HTML tags
function toBionic(text: string): string {
  // Split on HTML tags — process only text parts, leave tags untouched
  return text.replace(/(<[^>]+>)|(\b[a-zA-Z]+\b)/g, (match, tag, word) => {
    if (tag) return tag // Leave HTML tags as-is
    if (!word) return match
    if (word.length <= 1) return `<b>${word}</b>`
    const boldLen = word.length <= 3 ? 1 : Math.ceil(word.length * 0.5)
    return `<b>${word.slice(0, boldLen)}</b>${word.slice(boldLen)}`
  })
}

function extractFileLinks(content: string): { url: string; filename: string; type: string }[] {
  const links: { url: string; filename: string; type: string }[] = []
  const pattern = /\/api\/reports\/([a-zA-Z0-9_\-]+\.(pdf|xlsx|png|csv|html))/g
  let match
  while ((match = pattern.exec(content)) !== null) {
    const filename = match[1]
    const ext = match[2]
    const type = ext === 'pdf' ? 'PDF Report' : ext === 'html' ? 'Interactive Report' : ext === 'xlsx' ? 'Excel Spreadsheet' : ext === 'png' ? 'Chart Image' : 'File'
    links.push({ url: `/api/reports/${filename}`, filename, type })
  }
  return links
}

function FileCard({ url, filename, type }: { url: string; filename: string; type: string }) {
  const Icon = type.includes('Report') ? FileText : type.includes('Excel') ? FileSpreadsheet : BarChart3
  const color = type.includes('PDF') ? 'var(--color-cryo-red)' : type.includes('Interactive') ? 'var(--color-cryo-accent)' : type.includes('Excel') ? 'var(--color-cryo-emerald)' : 'var(--color-cryo-amber)'

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 px-4 py-3 mt-3 rounded-lg border border-[var(--color-cryo-border-bright)] bg-[var(--color-cryo-surface-2)] hover:bg-[var(--color-cryo-surface-3)] hover:border-[var(--color-cryo-accent)]/40 transition-all group"
    >
      <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15`, border: `1px solid ${color}40` }}>
        <Icon className="w-5 h-5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--color-cryo-text)] truncate">{filename}</div>
        <div className="text-xs text-[var(--color-cryo-text-dim)]">{type}</div>
      </div>
      <ExternalLink className="w-4 h-4 text-[var(--color-cryo-text-muted)] group-hover:text-[var(--color-cryo-accent)] transition-colors" />
    </a>
  )
}

// Wrap text content with bionic spans
function BionicText({ children, active }: { children: React.ReactNode; active: boolean }) {
  if (!active || typeof children !== 'string') return <>{children}</>

  const parts = children.split(/(\s+)/)
  return (
    <>
      {parts.map((part, i) => {
        if (/^\s+$/.test(part)) return part
        if (part.length <= 1) return <span key={i}><b className="bionic-bold">{part}</b></span>
        const boldLen = part.length <= 3 ? 1 : Math.ceil(part.length * 0.45)
        return (
          <span key={i}>
            <b className="bionic-bold">{part.slice(0, boldLen)}</b>
            <span className="bionic-light">{part.slice(boldLen)}</span>
          </span>
        )
      })}
    </>
  )
}

// Build markdown components with bionic awareness
function getMarkdownComponents(bionic: boolean): Components {
  const B = ({ children }: { children: React.ReactNode }) => <BionicText active={bionic}>{children}</BionicText>

  return {
  h1: ({ children }) => (
    <h1 className="text-xl font-bold text-[var(--color-cryo-text)] mt-4 mb-2 pb-1 border-b border-[var(--color-cryo-border)]">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-[var(--color-cryo-cyan)] mt-4 mb-2 pb-1 border-b border-[var(--color-cryo-border)]">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold text-[var(--color-cryo-accent)] mt-3 mb-1.5">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-semibold text-[var(--color-cryo-text)] mt-2 mb-1">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="text-sm leading-relaxed text-[var(--color-cryo-text)] mb-2.5">
      {typeof children === 'string' ? <B>{children}</B> : children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[var(--color-cryo-text)]">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-[var(--color-cryo-text-dim)]">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="list-none space-y-1 my-2 ml-1">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside space-y-1 my-2 ml-1 text-sm text-[var(--color-cryo-text)] marker:text-[var(--color-cryo-accent)]">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="text-sm text-[var(--color-cryo-text)] flex items-start gap-2">
      <span className="text-[var(--color-cryo-accent)] mt-1 flex-shrink-0">•</span>
      <span className="flex-1">{typeof children === 'string' ? <B>{children}</B> : children}</span>
    </li>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[var(--color-cryo-accent)] hover:text-[var(--color-cryo-cyan)] underline underline-offset-2 decoration-[var(--color-cryo-accent)]/30 hover:decoration-[var(--color-cryo-cyan)] transition-colors"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-3 border-[var(--color-cryo-accent)] bg-[var(--color-cryo-accent)]/5 rounded-r-lg px-4 py-2 my-3 text-sm text-[var(--color-cryo-text-dim)] italic">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes('language-')
    if (isBlock) {
      return (
        <code className="block text-xs font-mono text-[var(--color-cryo-cyan)]">
          {children}
        </code>
      )
    }
    return (
      <code className="text-xs font-mono bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-cyan)] px-1.5 py-0.5 rounded">
        {children}
      </code>
    )
  },
  pre: ({ children }) => (
    <pre className="bg-[var(--color-cryo-bg)] border border-[var(--color-cryo-border)] rounded-lg p-3 my-3 overflow-x-auto text-xs">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-[var(--color-cryo-border)]">
      <table className="w-full text-xs">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[var(--color-cryo-surface-2)]">
      {children}
    </thead>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-semibold text-[var(--color-cryo-accent)] text-[10px] uppercase tracking-wider border-b border-[var(--color-cryo-border-bright)]">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-[var(--color-cryo-text-dim)] border-b border-[var(--color-cryo-border)]">
      {children}
    </td>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-[var(--color-cryo-surface-2)] transition-colors">
      {children}
    </tr>
  ),
  hr: () => (
    <hr className="border-[var(--color-cryo-border)] my-4" />
  ),
  sup: ({ children }) => (
    <sup className="text-[var(--color-cryo-accent)] text-[9px] font-semibold">{children}</sup>
  ),
}}

export default function MessageBubble({ message, bionicMode = false }: Props) {
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'

  if (isTool) {
    return (
      <div className="tool-indicator rounded-lg px-4 py-2 mx-4 my-1 text-xs font-mono text-[var(--color-cryo-text-dim)]">
        <Wrench className="w-3 h-3 inline mr-2 text-[var(--color-cryo-purple)]" />
        Tool execution
      </div>
    )
  }

  const fileLinks = message.content ? extractFileLinks(message.content) : []

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`
        w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5
        ${isUser
          ? 'bg-[var(--color-cryo-surface-3)]'
          : 'bg-gradient-to-br from-[var(--color-cryo-accent)]/20 to-[var(--color-cryo-emerald)]/10 border border-[var(--color-cryo-accent)]/30'
        }
      `}>
        {isUser
          ? <User className="w-4 h-4 text-[var(--color-cryo-text-dim)]" />
          : <Dna className="w-4 h-4 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
        }
      </div>

      {/* Content */}
      <div className={`
        max-w-[80%] rounded-xl px-5 py-3.5 text-sm leading-relaxed
        ${isUser ? 'msg-user' : 'msg-assistant'}
      `}>
        {message.content ? (
          <div className="cryo-markdown">
            <ReactMarkdown components={getMarkdownComponents(bionicMode && !isUser)}>
              {message.content}
            </ReactMarkdown>
          </div>
        ) : (
          <span className="text-[var(--color-cryo-text-muted)] italic">No content</span>
        )}

        {fileLinks.length > 0 && (
          <div className="mt-3 space-y-2 pt-2 border-t border-[var(--color-cryo-border)]">
            {fileLinks.map((link) => (
              <FileCard key={link.url} {...link} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
