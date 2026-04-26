import { useState, useEffect, useRef, useCallback } from 'react'
import { Dna, Eye, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import Sidebar from '../components/Sidebar'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'
import ReportPanel from '../components/ReportPanel'
import { chat } from '../lib/api'

interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  role: string
}

interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: any
}

interface Conversation {
  id: string
  title: string | null
  message_count: number
  created_at: string
  updated_at: string
}

interface Props {
  user: User
  onLogout: () => void
}

export default function ChatPage({ user, onLogout }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvoId, setActiveConvoId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [bionicMode, setBionicMode] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [reportPanel, setReportPanel] = useState<{ url: string; filename: string } | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Listen for report open events from FileCard (deep in message tree)
  useEffect(() => {
    const handler = (e: Event) => {
      const { url, filename } = (e as CustomEvent).detail
      setReportPanel({ url, filename })
    }
    window.addEventListener('cryo:open-report', handler)
    return () => window.removeEventListener('cryo:open-report', handler)
  }, [])

  // Load conversations
  useEffect(() => {
    chat.conversations().then(setConversations).catch(console.error)
  }, [])

  // Load messages when switching conversations
  useEffect(() => {
    if (activeConvoId) {
      chat.messages(activeConvoId).then(setMessages).catch(console.error)
    } else {
      setMessages([])
    }
  }, [activeConvoId])

  // Scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamText])

  const handleSend = useCallback(async (message: string) => {
    const tempUserMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
    }
    setMessages(prev => [...prev, tempUserMsg])
    setStreaming(true)
    setStreamText('')

    try {
      const response = await chat.sendStream(message, activeConvoId || undefined)
      if (!response.body) throw new Error('No response body')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullText = ''
      let convoId = activeConvoId

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = JSON.parse(line.slice(6))

          if (data.type === 'delta') {
            fullText += data.text
            setStreamText(fullText)
          } else if (data.type === 'done') {
            convoId = data.conversation_id
          }
        }
      }

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: fullText,
      }
      setMessages(prev => [...prev, assistantMsg])
      setStreamText('')

      if (convoId && convoId !== activeConvoId) {
        setActiveConvoId(convoId)
      }
      chat.conversations().then(setConversations).catch(console.error)
    } catch (err) {
      console.error('Stream error:', err)
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Connection failed'}`,
      }])
    } finally {
      setStreaming(false)
    }
  }, [activeConvoId])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar — slides in/out */}
      <div
        className="flex-shrink-0 overflow-hidden transition-all duration-200"
        style={{ width: sidebarOpen ? 288 : 0 }}
      >
        <div style={{ width: 288 }}>
          <Sidebar
            conversations={conversations}
            activeId={activeConvoId}
            onSelect={setActiveConvoId}
            onNew={() => { setActiveConvoId(null); setMessages([]) }}
            onLogout={onLogout}
            username={user.username}
          />
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="px-4 py-3 border-b border-[var(--color-cryo-border)] flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            {/* Sidebar toggle */}
            <button
              onClick={() => setSidebarOpen(v => !v)}
              className="p-1.5 rounded-lg transition-colors hover:bg-[var(--color-cryo-surface-2)] text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text)]"
              title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {sidebarOpen
                ? <PanelLeftClose className="w-4 h-4" />
                : <PanelLeftOpen className="w-4 h-4" />
              }
            </button>
            <div className="flex items-center gap-2">
              <Dna className="w-4 h-4 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
              <span className="text-sm font-mono text-[var(--color-cryo-text-dim)] truncate">
                {activeConvoId
                  ? conversations.find(c => c.id === activeConvoId)?.title || 'Research Chat'
                  : 'New Research Chat'
                }
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {import.meta.env.VITE_BIONIC_READING !== 'false' && (
              <button
                onClick={() => setBionicMode(!bionicMode)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  bionicMode
                    ? 'bg-[var(--color-cryo-accent)]/15 text-[var(--color-cryo-accent)] border border-[var(--color-cryo-accent)]/30'
                    : 'text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text-dim)] border border-transparent hover:border-[var(--color-cryo-border)]'
                }`}
                title="Bionic Reading — bolds first half of each word for faster reading"
              >
                <Eye className="w-3.5 h-3.5" />
                Bionic
              </button>
            )}
            <span className="text-xs font-mono text-[var(--color-cryo-text-muted)]">
              LLM powered
            </span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !streaming && (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <Dna className="w-16 h-16 text-[var(--color-cryo-accent)] mb-6 opacity-30" strokeWidth={1} />
              <h2 className="text-2xl font-light text-[var(--color-cryo-text)] mb-2">
                What would you like to research?
              </h2>
              <p className="text-sm text-[var(--color-cryo-text-dim)] mb-8 max-w-md">
                Ask biology questions, search literature, analyze proteins, explore drug targets,
                or interpret genomic variants.
              </p>
              <div className="grid grid-cols-2 gap-2 max-w-lg">
                {[
                  'What are the key drug targets for glioblastoma?',
                  '/protein TP53',
                  '/pubmed CRISPR-Cas9 gene therapy 2024',
                  '/variant rs28934578',
                ].map(q => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="text-left px-3 py-2 rounded-lg text-xs font-mono text-[var(--color-cryo-text-dim)] bg-[var(--color-cryo-surface)] border border-[var(--color-cryo-border)] hover:border-[var(--color-cryo-accent)] hover:text-[var(--color-cryo-accent)] transition-colors truncate"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} bionicMode={bionicMode} />
          ))}

          {streaming && streamText && (
            <MessageBubble
              message={{ id: 'streaming', role: 'assistant', content: streamText + '...' }}
              bionicMode={bionicMode}
            />
          )}

          {streaming && !streamText && (
            <div className="flex items-center gap-3 px-7 py-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-cryo-accent)]/20 to-[var(--color-cryo-emerald)]/10 border border-[var(--color-cryo-accent)]/30 flex items-center justify-center">
                <Dna className="w-4 h-4 text-[var(--color-cryo-accent)] animate-helix" strokeWidth={1.5} />
              </div>
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-[var(--color-cryo-accent)] animate-pulse-glow"
                    style={{ animationDelay: `${i * 0.2}s` }}
                  />
                ))}
              </div>
              <span className="text-xs text-[var(--color-cryo-text-muted)] font-mono">analyzing</span>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-[var(--color-cryo-border)] flex-shrink-0">
          <ChatInput onSend={handleSend} disabled={streaming} />
        </div>
      </div>

      {/* Right-side report panel — rendered at top level so it overlays everything */}
      {reportPanel && (
        <ReportPanel
          url={reportPanel.url}
          filename={reportPanel.filename}
          onClose={() => setReportPanel(null)}
        />
      )}
    </div>
  )
}
