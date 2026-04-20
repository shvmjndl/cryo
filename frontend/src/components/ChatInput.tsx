import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Dna } from 'lucide-react'
import SlashMenu, { type SlashCommand } from './SlashMenu'

const DEFAULT_COMMANDS: SlashCommand[] = [
  { command: '/pubmed', description: 'Search PubMed literature', example: '/pubmed CRISPR glioblastoma' },
  { command: '/biorxiv', description: 'Search bioRxiv preprints', example: '/biorxiv single-cell RNA-seq' },
  { command: '/protein', description: 'Look up protein/gene info', example: '/protein TP53' },
  { command: '/structure', description: 'Find protein 3D structures', example: '/structure EGFR' },
  { command: '/drug', description: 'Search drugs and compounds', example: '/drug temozolomide' },
  { command: '/targets', description: 'Disease-target associations', example: '/targets glioblastoma' },
  { command: '/variant', description: 'Variant clinical significance', example: '/variant rs28934578' },
  { command: '/vep', description: 'Variant effect prediction', example: '/vep 17:7675088:C:T' },
  { command: '/repurpose', description: 'Drug repurposing candidates', example: '/repurpose Huntington disease' },
  { command: '/pathway', description: 'Explore biological pathways', example: '/pathway p53 signaling' },
  { command: '/compare', description: 'Compare genes/proteins/drugs', example: '/compare BRCA1 BRCA2' },
  { command: '/export', description: 'Export data to Excel', example: '/export TP53 variants' },
  { command: '/report', description: 'Generate PDF report', example: '/report glioblastoma drug targets' },
  { command: '/chart', description: 'Generate visualization', example: '/chart cancer mutation frequency' },
]

interface Props {
  onSend: (message: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [input, setInput] = useState('')
  const [showSlash, setShowSlash] = useState(false)
  const [slashFilter, setSlashFilter] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const filtered = DEFAULT_COMMANDS.filter(c =>
    c.command.includes(slashFilter.toLowerCase()) ||
    c.description.toLowerCase().includes(slashFilter.toLowerCase())
  )

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
    }
  }, [input])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setInput(val)

    // Detect slash at start of input or after newline
    if (val === '/' || val.match(/^\/\w*$/)) {
      setShowSlash(true)
      setSlashFilter(val)
      setSelectedIndex(0)
    } else {
      setShowSlash(false)
    }
  }, [])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (showSlash) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (filtered[selectedIndex]) {
          selectCommand(filtered[selectedIndex])
        }
      } else if (e.key === 'Escape') {
        setShowSlash(false)
      }
      return
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [showSlash, filtered, selectedIndex, input])

  const selectCommand = (cmd: SlashCommand) => {
    setInput(cmd.command + ' ')
    setShowSlash(false)
    textareaRef.current?.focus()
  }

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
    setShowSlash(false)
  }

  return (
    <div className="relative">
      <SlashMenu
        commands={DEFAULT_COMMANDS}
        filter={slashFilter}
        selectedIndex={selectedIndex}
        onSelect={selectCommand}
        visible={showSlash}
      />

      <div className="flex items-end gap-2 p-3 rounded-xl bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] focus-within:border-[var(--color-cryo-accent)] transition-colors">
        <Dna className="w-5 h-5 text-[var(--color-cryo-accent)] mb-1.5 flex-shrink-0 opacity-50" strokeWidth={1.5} />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder='Ask about biology or type "/" for tools...'
          disabled={disabled}
          rows={1}
          className="flex-1 bg-transparent text-[var(--color-cryo-text)] placeholder:text-[var(--color-cryo-text-muted)] resize-none focus:outline-none text-sm leading-relaxed"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className="p-2 rounded-lg bg-[var(--color-cryo-accent)] text-[var(--color-cryo-bg)] hover:brightness-110 transition-all disabled:opacity-30 disabled:hover:brightness-100 flex-shrink-0"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>

      <div className="flex items-center justify-between mt-2 px-1">
        <span className="text-xs text-[var(--color-cryo-text-muted)] font-mono">
          Type <kbd className="px-1 py-0.5 rounded bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-accent)]">/</kbd> for tools
        </span>
        <span className="text-xs text-[var(--color-cryo-text-muted)]">
          Shift+Enter for newline
        </span>
      </div>
    </div>
  )
}
