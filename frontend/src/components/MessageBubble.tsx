import { User, Dna, Wrench } from 'lucide-react'
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
      </div>
    </div>
  )
}
