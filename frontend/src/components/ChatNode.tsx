import { useState, useRef, useEffect, useCallback } from 'react'
import { Handle, Position, NodeResizer, type NodeProps } from '@xyflow/react'
import { Send, Dna, Minimize2, Maximize2, X, User, Microscope } from 'lucide-react'
import { chat, collections, type UploadRecord, type CollectionFileRecord } from '../lib/api'
import ChatMessage from './ChatMessage'
import { CELL_LINES, GEM_MODELS, type GemModel } from './SlashMenu'
import FileMentionMenu from './FileMentionMenu'
import FileUploadButton from './FileUploadButton'

function extractFileLinks(content: string) {
  const links: { url: string; filename: string }[] = []
  const pattern = /\/api\/reports\/([a-zA-Z0-9_\-]+\.(html|pdf|xlsx|png))/g
  let m
  while ((m = pattern.exec(content)) !== null) {
    links.push({ url: `/api/reports/${m[1]}`, filename: m[1] })
  }
  return links
}

const SLASH_COMMANDS = [
  { command: '/pubmed',      description: 'Search PubMed' },
  { command: '/protein',     description: 'Protein/gene info' },
  { command: '/drug',        description: 'Drug/compound info' },
  { command: '/variant',     description: 'Variant significance' },
  { command: '/vep',         description: 'Variant effect prediction' },
  { command: '/targets',     description: 'Disease-target associations' },
  { command: '/structure',   description: 'Protein 3D structures' },
  { command: '/digital_twin',description: 'Metabolic drug simulation —cell_line MCF7' },
  { command: '/simulate',    description: 'Alias for /digital_twin' },
  { command: '/ppi',         description: 'Protein-protein interactions' },
  { command: '/kegg',        description: 'KEGG pathway search' },
  { command: '/reactome',    description: 'Reactome enrichment' },
  { command: '/deseq',       description: 'Differential expression (PyDESeq2)' },
  { command: '/scrna',       description: 'scRNA-seq analysis (Scanpy)' },
  { command: '/annotate',    description: 'Cell type annotation (CellTypist)' },
  { command: '/atac',        description: 'ATAC-seq peak calling' },
  { command: '/chip',        description: 'ChIP-seq peak calling' },
  { command: '/meta',        description: 'Metagenomics pipeline' },
  { command: '/ms',          description: 'Mass-spec proteomics' },
  { command: '/sec',         description: 'SEC chromatography' },
  { command: '/gem',         description: 'GEM metabolic graph query' },
  { command: '/collections', description: 'Search/read uploaded PDF or image documents' },
  { command: '/novelty',     description: 'Research novelty check' },
  { command: '/paper',       description: 'Manuscript pipeline' },
  { command: '/report',      description: 'Generate research report' },
  { command: '/chart',       description: 'Generate visualization' },
  { command: '/export',      description: 'Export to Excel' },
  { command: '/compare',     description: 'Compare genes/drugs' },
  { command: '/repurpose',   description: 'Drug repurposing' },
]

function detectCellLineMode(val: string): { active: boolean; filter: string } {
  const isDigitalTwin = val.startsWith('/digital_twin') || val.startsWith('/simulate')
  if (!isDigitalTwin) return { active: false, filter: '' }
  const match = val.match(/--cell[_\-]?line\s+(\S*)$/)
  if (match) return { active: true, filter: match[1] }
  if (/--cell[_\-]?line$/.test(val.trimEnd())) return { active: true, filter: '' }
  return { active: false, filter: '' }
}

function detectModelMode(val: string): { active: boolean; filter: string } {
  const isDigitalTwinOrGem = val.startsWith('/digital_twin') || val.startsWith('/simulate') || val.startsWith('/gem')
  if (!isDigitalTwinOrGem) return { active: false, filter: '' }
  const match = val.match(/--(?:model|backbone)\s+(\S*)$/)
  if (match) return { active: true, filter: match[1] }
  if (/--(?:model|backbone)$/.test(val.trimEnd())) return { active: true, filter: '' }
  return { active: false, filter: '' }
}

function detectMentionMode(val: string): { active: boolean; filter: string } {
  const match = val.match(/@(\w*)$/)
  if (match) return { active: true, filter: match[1] }
  return { active: false, filter: '' }
}

interface MentionedFile { id: string; name: string }

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface ChatNodeData {
  title: string
  conversationId: string | null
  messages: ChatMessage[]
  initialMessage?: string
  branchContext?: string
  minimized: boolean
  onBranch: (nodeId: string, messageContent: string) => void
  onClose: (nodeId: string) => void
  onTitleUpdate: (nodeId: string, title: string) => void
  onConversationUpdate: (nodeId: string, conversationId: string) => void
}

export default function ChatNode({ id, data }: NodeProps & { data: ChatNodeData }) {
  const [messages, setMessages] = useState<ChatMessage[]>(data.messages || [])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(data.conversationId)
  const [minimized, setMinimized] = useState(data.minimized)
  const [title, setTitle] = useState(data.title)
  const [mentionedFiles, setMentionedFiles] = useState<MentionedFile[]>([])
  const [availableFiles, setAvailableFiles] = useState<CollectionFileRecord[]>([])
  const [mentionSelectedIdx, setMentionSelectedIdx] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const sentInitial = useRef(false)

  const mentionMode = detectMentionMode(input)

  useEffect(() => {
    if (!mentionMode.active) return
    collections.listFiles(conversationId || undefined).then(setAvailableFiles).catch(() => setAvailableFiles([]))
  }, [mentionMode.active, conversationId])

  // Use refs for values needed in handleSend to avoid stale closures
  const conversationIdRef = useRef(conversationId)
  const messagesRef = useRef(messages)
  const streamingRef = useRef(streaming)
  const titleRef = useRef(title)

  useEffect(() => { conversationIdRef.current = conversationId }, [conversationId])
  useEffect(() => { messagesRef.current = messages }, [messages])
  useEffect(() => { streamingRef.current = streaming }, [streaming])
  useEffect(() => { titleRef.current = title }, [title])

  // Load messages from DB if node has a conversation_id (after reload)
  useEffect(() => {
    if (data.conversationId && messages.length === 0) {
      import('../lib/api').then(({ chat: chatApi }) => {
        chatApi.messages(data.conversationId!).then((msgs: any[]) => {
          if (msgs?.length > 0) {
            const loaded: ChatMessage[] = msgs
              .filter((m: any) => m.role === 'user' || m.role === 'assistant')
              .map((m: any) => ({ id: m.id, role: m.role, content: m.content || '' }))
            setMessages(loaded)
          }
        }).catch(console.error)
      })
    }
  }, [data.conversationId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streamText])

  useEffect(() => {
    if (sentInitial.current) return
    if (data.initialMessage) {
      sentInitial.current = true
      setTimeout(() => handleSend(data.initialMessage!), 100)
    }
  }, [])

  async function handleSend(msg?: string) {
    const text = msg || input.trim()
    if (!text || streamingRef.current) return

    const fileIds = mentionedFiles.map(f => f.id)
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setMentionedFiles([])
    setStreaming(true)
    setStreamText('')

    if (messagesRef.current.length === 0 && titleRef.current === 'New Research') {
      const newTitle = text.length > 40 ? text.slice(0, 40) + '...' : text
      setTitle(newTitle)
      data.onTitleUpdate(id, newTitle)
    }

    try {
      let fullMessage = text
      if (data.branchContext && messagesRef.current.length === 0) {
        fullMessage = `Context from previous research:\n${data.branchContext.slice(0, 500)}\n\nNew question: ${text}`
      }

      const response = await chat.sendStream(fullMessage, conversationIdRef.current || undefined, fileIds.length ? fileIds : undefined)
      if (!response.body) throw new Error('No response')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'delta') {
              fullText += event.text
              setStreamText(fullText)
            } else if (event.type === 'done' && event.conversation_id) {
              setConversationId(event.conversation_id)
              data.onConversationUpdate(id, event.conversation_id)
            }
          } catch {}
        }
      }

      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: fullText }])
      setStreamText('')
    } catch (err) {
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `Error: ${err}` }])
    } finally {
      setStreaming(false)
    }
  }

  if (minimized) {
    return (
      <div className="chat-node-minimized">
        <Handle type="target" position={Position.Left} className="!bg-transparent !w-0 !h-0 !border-0 !opacity-0" />
        <div className="flex items-center gap-2 px-3 py-2 cursor-pointer" onClick={() => setMinimized(false)}>
          <Dna className="w-3 h-3 text-[var(--color-cryo-accent)]" strokeWidth={2} />
          <span className="text-xs font-medium text-[var(--color-cryo-text)] truncate max-w-[140px]">{title}</span>
          <span className="text-[9px] text-[var(--color-cryo-text-muted)]">{messages.length}msg</span>
          <Maximize2 className="w-3 h-3 text-[var(--color-cryo-text-muted)] ml-auto" />
        </div>
        <Handle type="source" position={Position.Right} className="!bg-transparent !w-0 !h-0 !border-0 !opacity-0" />
      </div>
    )
  }

  return (
    <div className="chat-node">
      <NodeResizer
        minWidth={320} minHeight={250}
        lineClassName="!border-transparent"
        handleClassName="!bg-transparent !border-0 !w-3 !h-3"
      />
      <Handle type="target" position={Position.Left} className="!bg-transparent !w-0 !h-0 !border-0 !opacity-0" />

      {/* Header — draggable */}
      <div className="chat-node-header">
        <Dna className="w-3.5 h-3.5 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
        <span className="flex-1 text-xs font-medium truncate">{title}</span>
        <button onClick={() => setMinimized(true)} className="node-btn"><Minimize2 className="w-3 h-3" /></button>
        <button onClick={() => data.onClose(id)} className="node-btn hover:!text-[var(--color-cryo-red)]"><X className="w-3 h-3" /></button>
      </div>

      {/* Messages — nodrag nopan nowheel allows scroll/select/copy inside */}
      <div
        ref={scrollRef}
        className="chat-node-messages nodrag nopan nowheel"
        style={{ userSelect: 'text', cursor: 'auto' }}
      >
        {messages.length === 0 && !streaming && (
          <div className="text-center py-6 text-[var(--color-cryo-text-muted)] text-xs">
            Start your research...
          </div>
        )}

        {messages.map(msg => (
          <ChatMessage
            key={msg.id}
            message={msg}
            compact
            onBranch={msg.role === 'assistant' ? (content) => data.onBranch(id, content) : undefined}
          />
        ))}

        {streaming && streamText && (
          <ChatMessage
            message={{ id: 'stream', role: 'assistant', content: streamText }}
            compact
          />
        )}

        {streaming && !streamText && (
          <div className="flex items-center gap-2 py-3 px-2">
            <Dna className="w-3.5 h-3.5 text-[var(--color-cryo-accent)] animate-spin" strokeWidth={1.5} />
            <span className="text-[10px] text-[var(--color-cryo-text-muted)]">researching...</span>
          </div>
        )}
      </div>

      {/* Input with slash/model/cell-line/@ menus — nodrag nopan so typing works */}
      <div className="chat-node-input nodrag nopan nowheel relative">
        {/* @ file mention menu */}
        <FileMentionMenu
          files={availableFiles}
          filter={mentionMode.filter}
          selectedIndex={mentionSelectedIdx}
          onSelect={file => {
            setInput(prev => prev.replace(/@\w*$/, `@${file.original_filename} `))
            setMentionedFiles(prev => prev.some(f => f.id === file.id) ? prev : [...prev, { id: file.id, name: file.original_filename }])
            setMentionSelectedIdx(0)
          }}
          visible={mentionMode.active}
        />

        {/* Model sub-menu */}
        {!mentionMode.active && detectModelMode(input).active && (() => {
          const { filter } = detectModelMode(input)
          const models = GEM_MODELS.filter(m =>
            m.key.toLowerCase().includes(filter.toLowerCase()) ||
            m.label.toLowerCase().includes(filter.toLowerCase()) ||
            m.organism.toLowerCase().includes(filter.toLowerCase())
          )
          return models.length > 0 ? (
            <div className="absolute bottom-full left-0 right-0 mb-1 bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border-bright)] rounded-lg max-h-48 overflow-y-auto shadow-lg" style={{ zIndex: 9999 }}>
              <div className="px-3 py-1 text-[9px] text-[var(--color-cryo-accent)] font-mono uppercase tracking-wider border-b border-[var(--color-cryo-border)] flex items-center gap-1">
                <Dna className="w-2.5 h-2.5" /> Metabolic Model
              </div>
              {models.map(m => (
                <button key={m.key}
                  onClick={() => setInput(input.replace(/--(?:model|backbone)\s*\S*$/, `--model ${m.key}`))}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-[var(--color-cryo-surface-3)] flex items-center gap-2 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[var(--color-cryo-text)]">{m.label}</span>
                      <span className="text-[9px] text-[var(--color-cryo-cyan)] bg-[var(--color-cryo-surface-3)] px-1 py-0.5 rounded font-mono">{m.organism}</span>
                    </div>
                    <div className="text-[9px] text-[var(--color-cryo-text-muted)]">{m.description}</div>
                  </div>
                </button>
              ))}
            </div>
          ) : null
        })()}

        {/* Cell line sub-menu */}
        {!mentionMode.active && !detectModelMode(input).active && detectCellLineMode(input).active && (() => {
          const { filter } = detectCellLineMode(input)
          const lines = CELL_LINES.filter(cl => cl.toLowerCase().includes(filter.toLowerCase()))
          return lines.length > 0 ? (
            <div className="absolute bottom-full left-0 right-0 mb-1 bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border-bright)] rounded-lg max-h-40 overflow-y-auto shadow-lg" style={{ zIndex: 9999 }}>
              <div className="px-3 py-1 text-[9px] text-[var(--color-cryo-cyan)] font-mono uppercase tracking-wider border-b border-[var(--color-cryo-border)] flex items-center gap-1">
                <Microscope className="w-2.5 h-2.5" /> Cell Lines
              </div>
              {lines.map(cl => (
                <button key={cl}
                  onClick={() => setInput(input.replace(/--cell[_\-]?line\s*\S*$/, `--cell_line ${cl}`))}
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-cryo-surface-3)] flex items-center gap-2 transition-colors"
                >
                  <span className="font-mono text-[var(--color-cryo-text)]">{cl}</span>
                </button>
              ))}
            </div>
          ) : null
        })()}

        {/* Slash command menu */}
        {!mentionMode.active && !detectModelMode(input).active && !detectCellLineMode(input).active && /^\/\w*$/.test(input) && (
          <div className="absolute bottom-full left-0 right-0 mb-1 bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border-bright)] rounded-lg max-h-40 overflow-y-auto shadow-lg" style={{ zIndex: 9999 }}>
            {SLASH_COMMANDS
              .filter(c => c.command.includes(input.toLowerCase()))
              .map(cmd => (
                <button key={cmd.command}
                  onClick={() => setInput(cmd.command + ' ')}
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-cryo-surface-3)] flex items-center gap-2 transition-colors"
                >
                  <span className="font-mono text-[var(--color-cryo-accent)]">{cmd.command}</span>
                  <span className="text-[var(--color-cryo-text-muted)] text-[10px] truncate">{cmd.description}</span>
                </button>
              ))
            }
          </div>
        )}

        {/* Mentioned file pills */}
        {mentionedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1 px-0.5">
            {mentionedFiles.map(f => (
              <span key={f.id} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] bg-[var(--color-cryo-accent)]/15 text-[var(--color-cryo-accent)] border border-[var(--color-cryo-accent)]/30">
                <span className="max-w-[100px] truncate">{f.name}</span>
                <button
                  onClick={() => {
                    setMentionedFiles(prev => prev.filter(x => x.id !== f.id))
                    setInput(prev => prev.replace(new RegExp(`@${f.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s?`, 'g'), ''))
                  }}
                  className="hover:text-[var(--color-cryo-text)]"
                  tabIndex={-1}
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              </span>
            ))}
          </div>
        )}

        <textarea
          value={input}
          onChange={e => {
            setInput(e.target.value)
            if (!detectMentionMode(e.target.value).active) setMentionSelectedIdx(0)
          }}
          onKeyDown={e => {
            if (mentionMode.active) {
              const filtered = availableFiles.filter(f => f.original_filename.toLowerCase().includes(mentionMode.filter.toLowerCase()))
              if (e.key === 'ArrowDown') { e.preventDefault(); setMentionSelectedIdx(i => Math.min(i + 1, filtered.length - 1)); return }
              if (e.key === 'ArrowUp') { e.preventDefault(); setMentionSelectedIdx(i => Math.max(i - 1, 0)); return }
              if (e.key === 'Enter' && !e.shiftKey && filtered[mentionSelectedIdx]) {
                e.preventDefault()
                const file = filtered[mentionSelectedIdx]
                setInput(prev => prev.replace(/@\w*$/, `@${file.original_filename} `))
                setMentionedFiles(prev => prev.some(f => f.id === file.id) ? prev : [...prev, { id: file.id, name: file.original_filename }])
                setMentionSelectedIdx(0)
                return
              }
              if (e.key === 'Escape') { setInput(prev => prev.replace(/@\w*$/, '')); return }
            }
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
          }}
          placeholder='Type "/" for commands, "@" to tag a document...'
          disabled={streaming}
          rows={1}
          className="node-textarea"
          style={{ userSelect: 'text' }}
        />
        <FileUploadButton
          compact
          conversationId={conversationId || undefined}
          onUploaded={(record: UploadRecord) => {
            const cmd = record.suggested_command || ''
            const insertion = cmd ? `${cmd} ${record.server_path} ` : `${record.server_path} `
            setInput(prev => prev ? `${prev.trimEnd()} ${insertion}` : insertion)
          }}
          onDocumentUploaded={(record: CollectionFileRecord) => {
            setMentionedFiles(prev =>
              prev.some(f => f.id === record.id) ? prev : [...prev, { id: record.id, name: record.original_filename }]
            )
          }}
        />
        <button onClick={() => handleSend()} disabled={!input.trim() || streaming} className="node-send-btn">
          <Send className="w-3 h-3" />
        </button>
      </div>

      {/* Footer */}
      <div className="chat-node-footer">
        <span>{messages.length} messages</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-transparent !w-0 !h-0 !border-0 !opacity-0" />
    </div>
  )
}
