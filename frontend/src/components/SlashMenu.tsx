import { useEffect, useRef } from 'react'
import {
  BookOpen, Dna, Pill, FileSearch, FlaskConical, GitBranch, Download, Scale
} from 'lucide-react'

export interface SlashCommand {
  command: string
  description: string
  example: string
}

const ICON_MAP: Record<string, React.ReactNode> = {
  '/pubmed': <BookOpen className="w-4 h-4" />,
  '/biorxiv': <BookOpen className="w-4 h-4" />,
  '/protein': <Dna className="w-4 h-4" />,
  '/structure': <Dna className="w-4 h-4" />,
  '/drug': <Pill className="w-4 h-4" />,
  '/targets': <FlaskConical className="w-4 h-4" />,
  '/variant': <FileSearch className="w-4 h-4" />,
  '/vep': <FileSearch className="w-4 h-4" />,
  '/repurpose': <GitBranch className="w-4 h-4" />,
  '/pathway': <GitBranch className="w-4 h-4" />,
  '/compare': <Scale className="w-4 h-4" />,
  '/export': <Download className="w-4 h-4" />,
}

const CATEGORY_COLORS: Record<string, string> = {
  '/pubmed': 'text-[var(--color-cryo-blue)]',
  '/biorxiv': 'text-[var(--color-cryo-blue)]',
  '/protein': 'text-[var(--color-cryo-emerald)]',
  '/structure': 'text-[var(--color-cryo-emerald)]',
  '/drug': 'text-[var(--color-cryo-purple)]',
  '/targets': 'text-[var(--color-cryo-purple)]',
  '/variant': 'text-[var(--color-cryo-amber)]',
  '/vep': 'text-[var(--color-cryo-amber)]',
  '/repurpose': 'text-[var(--color-cryo-cyan)]',
  '/pathway': 'text-[var(--color-cryo-cyan)]',
  '/compare': 'text-[var(--color-cryo-text-dim)]',
  '/export': 'text-[var(--color-cryo-text-dim)]',
}

interface Props {
  commands: SlashCommand[]
  filter: string
  selectedIndex: number
  onSelect: (cmd: SlashCommand) => void
  visible: boolean
}

export default function SlashMenu({ commands, filter, selectedIndex, onSelect, visible }: Props) {
  const menuRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<(HTMLDivElement | null)[]>([])

  const filtered = commands.filter(c =>
    c.command.toLowerCase().includes(filter.toLowerCase()) ||
    c.description.toLowerCase().includes(filter.toLowerCase())
  )

  useEffect(() => {
    itemRefs.current[selectedIndex]?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!visible || filtered.length === 0) return null

  return (
    <div
      ref={menuRef}
      className="slash-menu absolute bottom-full left-0 right-0 mb-2 rounded-xl bg-[var(--color-cryo-surface-2)] max-h-72 overflow-y-auto z-50"
    >
      <div className="px-3 py-2 text-xs text-[var(--color-cryo-text-muted)] font-mono uppercase tracking-wider border-b border-[var(--color-cryo-border)]">
        Biology Tools
      </div>
      {filtered.map((cmd, i) => (
        <div
          key={cmd.command}
          ref={el => { itemRefs.current[i] = el }}
          onClick={() => onSelect(cmd)}
          className={`
            flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors
            ${i === selectedIndex ? 'bg-[var(--color-cryo-surface-3)]' : 'hover:bg-[var(--color-cryo-surface-3)]'}
          `}
        >
          <span className={CATEGORY_COLORS[cmd.command] || 'text-[var(--color-cryo-text-dim)]'}>
            {ICON_MAP[cmd.command] || <FlaskConical className="w-4 h-4" />}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-[var(--color-cryo-accent)]">{cmd.command}</span>
              <span className="text-xs text-[var(--color-cryo-text-dim)] truncate">{cmd.description}</span>
            </div>
            <div className="text-xs text-[var(--color-cryo-text-muted)] font-mono mt-0.5 truncate">
              {cmd.example}
            </div>
          </div>
          {i === selectedIndex && (
            <span className="text-xs text-[var(--color-cryo-text-muted)] font-mono">enter</span>
          )}
        </div>
      ))}
    </div>
  )
}
