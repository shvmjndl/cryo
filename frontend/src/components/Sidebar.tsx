import { Dna, Plus, MessageSquare, LogOut, GitBranch } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface Conversation {
  id: string
  title: string | null
  message_count: number
  updated_at: string
}

interface Props {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onLogout: () => void
  username: string
}

export default function Sidebar({ conversations, activeId, onSelect, onNew, onLogout, username }: Props) {
  const navigate = useNavigate()

  return (
    <div className="w-72 h-screen flex flex-col bg-[var(--color-cryo-surface)] border-r border-[var(--color-cryo-border)]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-cryo-border)]">
        <div className="flex items-center gap-2 mb-4">
          <Dna className="w-6 h-6 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
          <span className="text-xl font-bold font-mono tracking-widest text-[var(--color-cryo-accent)]">
            CRYO
          </span>
        </div>
        <div className="flex gap-2 mb-2">
          <button
            onClick={onNew}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-[var(--color-cryo-border)] hover:border-[var(--color-cryo-accent)] hover:bg-[var(--color-cryo-surface-2)] transition-all text-xs text-[var(--color-cryo-text-dim)] hover:text-[var(--color-cryo-accent)]"
          >
            <Plus className="w-3.5 h-3.5" />
            New Chat
          </button>
          <button
            onClick={() => navigate('/workspace')}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-[var(--color-cryo-border)] hover:border-[var(--color-cryo-purple)] hover:bg-[var(--color-cryo-surface-2)] transition-all text-xs text-[var(--color-cryo-text-dim)] hover:text-[var(--color-cryo-purple)]"
          >
            <GitBranch className="w-3.5 h-3.5" />
            Workspace
          </button>
        </div>
        <button
          onClick={onNew}
          className="hidden w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-[var(--color-cryo-border)] hover:border-[var(--color-cryo-accent)] hover:bg-[var(--color-cryo-surface-2)] transition-all text-sm text-[var(--color-cryo-text-dim)] hover:text-[var(--color-cryo-accent)]"
        >
          <Plus className="w-4 h-4" />
          New Research Chat
        </button>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto p-2">
        {conversations.map(c => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`
              w-full text-left px-3 py-2.5 rounded-lg mb-0.5 transition-all text-sm truncate
              flex items-center gap-2
              ${c.id === activeId
                ? 'bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-text)] border-l-2 border-[var(--color-cryo-accent)]'
                : 'text-[var(--color-cryo-text-dim)] hover:bg-[var(--color-cryo-surface-2)] hover:text-[var(--color-cryo-text)]'
              }
            `}
          >
            <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 opacity-50" />
            <span className="truncate">{c.title || 'New chat'}</span>
          </button>
        ))}

        {conversations.length === 0 && (
          <div className="text-center py-8 text-[var(--color-cryo-text-muted)] text-xs">
            No conversations yet
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-[var(--color-cryo-border)]">
        <div className="flex items-center justify-between">
          <span className="text-xs text-[var(--color-cryo-text-dim)] font-mono truncate">
            {username}
          </span>
          <button
            onClick={onLogout}
            className="p-1.5 rounded hover:bg-[var(--color-cryo-surface-2)] text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-red)] transition-colors"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
