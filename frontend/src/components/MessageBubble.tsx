import { User, Dna, Wrench, FileText, FileSpreadsheet, BarChart3, Download } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: any
}

interface Props {
  message: Message
}

// Detect report download links in the response
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
  const Icon = type.includes('PDF') ? FileText : type.includes('Excel') ? FileSpreadsheet : BarChart3
  const color = type.includes('PDF') ? 'var(--color-cryo-red)' : type.includes('Excel') ? 'var(--color-cryo-emerald)' : 'var(--color-cryo-amber)'

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      download={filename}
      className="flex items-center gap-3 px-4 py-3 mt-3 rounded-lg border border-[var(--color-cryo-border-bright)] bg-[var(--color-cryo-surface-2)] hover:bg-[var(--color-cryo-surface-3)] transition-colors group"
    >
      <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15`, border: `1px solid ${color}40` }}>
        <Icon className="w-5 h-5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--color-cryo-text)] truncate">{filename}</div>
        <div className="text-xs text-[var(--color-cryo-text-dim)]">{type} — Click to download</div>
      </div>
      <Download className="w-4 h-4 text-[var(--color-cryo-text-muted)] group-hover:text-[var(--color-cryo-accent)] transition-colors" />
    </a>
  )
}

export default function MessageBubble({ message }: Props) {
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
        w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
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
        max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed
        ${isUser ? 'msg-user' : 'msg-assistant'}
      `}>
        {message.content ? (
          <div className="prose prose-invert prose-sm max-w-none [&_pre]:bg-[var(--color-cryo-bg)] [&_pre]:rounded-lg [&_pre]:p-3 [&_code]:text-[var(--color-cryo-cyan)] [&_code]:text-xs [&_a]:text-[var(--color-cryo-accent)]">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        ) : (
          <span className="text-[var(--color-cryo-text-muted)] italic">No content</span>
        )}

        {/* File download cards */}
        {fileLinks.length > 0 && (
          <div className="mt-2 space-y-2">
            {fileLinks.map((link) => (
              <FileCard key={link.url} {...link} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
