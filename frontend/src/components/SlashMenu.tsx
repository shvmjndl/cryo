import { useEffect, useRef } from 'react'
import {
  BookOpen, Dna, Pill, FileSearch, FlaskConical, GitBranch, Download, Scale,
  FileText, BarChart3, Microscope
} from 'lucide-react'

export interface SlashCommand {
  command: string
  description: string
  example: string
}

export const CELL_LINES: string[] = [
  'MCF7', 'HeLa', 'A549', 'HCT116', 'PC3', 'LNCaP', 'U87MG', 'HepG2',
  'K562', 'Jurkat', 'T98G', 'MDA-MB-231', 'SK-BR-3', 'BT474', 'ZR75-1',
  'PANC1', 'HT29', 'COLO205', 'SW480', 'SW620', 'DU145', '22Rv1', 'VCAP',
  'NCI-H460', 'NCI-H1299', 'NCI-H1975', 'NCI-H23', 'NCI-H522',
  'OVCAR3', 'SKOV3', 'TOV112D', 'ES2', 'Ishikawa', 'HEC1A',
  'RKO', 'LoVo', 'Caco2', 'HEK293T', 'U2OS', 'HOS', 'Saos2',
  'SH-SY5Y', 'SK-N-SH', 'MOLT4', 'RAMOS', 'DAUDI', 'NALM6', 'REH', 'KASUMI1',
]

const CELL_LINE_TISSUE: Record<string, string> = {
  'MCF7': 'breast', 'MDA-MB-231': 'breast', 'SK-BR-3': 'breast', 'BT474': 'breast', 'ZR75-1': 'breast',
  'HeLa': 'cervical', 'A549': 'lung', 'NCI-H460': 'lung', 'NCI-H1299': 'lung', 'NCI-H1975': 'lung', 'NCI-H23': 'lung', 'NCI-H522': 'lung',
  'HCT116': 'colon', 'HT29': 'colon', 'COLO205': 'colon', 'SW480': 'colon', 'SW620': 'colon', 'RKO': 'colon', 'LoVo': 'colon', 'Caco2': 'colon',
  'PC3': 'prostate', 'LNCaP': 'prostate', 'DU145': 'prostate', '22Rv1': 'prostate', 'VCAP': 'prostate',
  'U87MG': 'glioblastoma', 'T98G': 'glioblastoma',
  'HepG2': 'liver', 'PANC1': 'pancreatic',
  'K562': 'leukemia', 'Jurkat': 'leukemia', 'MOLT4': 'leukemia', 'NALM6': 'leukemia', 'REH': 'leukemia', 'KASUMI1': 'leukemia',
  'RAMOS': 'lymphoma', 'DAUDI': 'lymphoma',
  'OVCAR3': 'ovarian', 'SKOV3': 'ovarian', 'TOV112D': 'ovarian', 'ES2': 'ovarian',
  'Ishikawa': 'endometrial', 'HEC1A': 'endometrial',
  'U2OS': 'osteosarcoma', 'HOS': 'osteosarcoma', 'Saos2': 'osteosarcoma',
  'SH-SY5Y': 'neuroblastoma', 'SK-N-SH': 'neuroblastoma',
  'HEK293T': 'kidney (HEK)',
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
  '/digital_twin': <FlaskConical className="w-4 h-4" />,
  '/simulate': <FlaskConical className="w-4 h-4" />,
  '/repurpose': <GitBranch className="w-4 h-4" />,
  '/pathway': <GitBranch className="w-4 h-4" />,
  '/compare': <Scale className="w-4 h-4" />,
  '/export': <Download className="w-4 h-4" />,
  '/report': <FileText className="w-4 h-4" />,
  '/chart': <BarChart3 className="w-4 h-4" />,
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
  '/digital_twin': 'text-[var(--color-cryo-cyan)]',
  '/simulate': 'text-[var(--color-cryo-cyan)]',
  '/repurpose': 'text-[var(--color-cryo-cyan)]',
  '/pathway': 'text-[var(--color-cryo-cyan)]',
  '/compare': 'text-[var(--color-cryo-text-dim)]',
  '/export': 'text-[var(--color-cryo-text-dim)]',
  '/report': 'text-[var(--color-cryo-red)]',
  '/chart': 'text-[var(--color-cryo-amber)]',
}

interface Props {
  commands: SlashCommand[]
  filter: string
  selectedIndex: number
  onSelect: (cmd: SlashCommand) => void
  visible: boolean
  // Cell line sub-menu
  mode?: 'commands' | 'cell_lines'
  cellLineFilter?: string
  onSelectCellLine?: (line: string) => void
}

export default function SlashMenu({
  commands, filter, selectedIndex, onSelect, visible,
  mode = 'commands', cellLineFilter = '', onSelectCellLine,
}: Props) {
  const menuRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<(HTMLDivElement | null)[]>([])

  const filteredCommands = commands.filter(c =>
    c.command.toLowerCase().includes(filter.toLowerCase()) ||
    c.description.toLowerCase().includes(filter.toLowerCase())
  )

  const filteredCellLines = CELL_LINES.filter(cl =>
    cl.toLowerCase().includes(cellLineFilter.toLowerCase()) ||
    (CELL_LINE_TISSUE[cl] || '').toLowerCase().includes(cellLineFilter.toLowerCase())
  )

  useEffect(() => {
    itemRefs.current[selectedIndex]?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!visible) return null
  if (mode === 'commands' && filteredCommands.length === 0) return null
  if (mode === 'cell_lines' && filteredCellLines.length === 0) return null

  if (mode === 'cell_lines') {
    return (
      <div
        ref={menuRef}
        className="slash-menu absolute bottom-full left-0 right-0 mb-2 rounded-xl bg-[var(--color-cryo-surface-2)] max-h-72 overflow-y-auto z-50"
      >
        <div className="px-3 py-2 text-xs text-[var(--color-cryo-cyan)] font-mono uppercase tracking-wider border-b border-[var(--color-cryo-border)] flex items-center gap-2">
          <Microscope className="w-3 h-3" />
          Cell Lines <span className="text-[var(--color-cryo-text-muted)] normal-case">({filteredCellLines.length} available)</span>
        </div>
        {filteredCellLines.map((cl, i) => (
          <div
            key={cl}
            ref={el => { itemRefs.current[i] = el }}
            onClick={() => onSelectCellLine?.(cl)}
            className={`
              flex items-center gap-3 px-4 py-2 cursor-pointer transition-colors
              ${i === selectedIndex ? 'bg-[var(--color-cryo-surface-3)]' : 'hover:bg-[var(--color-cryo-surface-3)]'}
            `}
          >
            <span className="text-[var(--color-cryo-cyan)]">
              <Microscope className="w-3.5 h-3.5" />
            </span>
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <span className="font-mono text-sm text-[var(--color-cryo-text)]">{cl}</span>
              {CELL_LINE_TISSUE[cl] && (
                <span className="text-[10px] text-[var(--color-cryo-text-muted)] bg-[var(--color-cryo-surface-3)] px-1.5 py-0.5 rounded-full">
                  {CELL_LINE_TISSUE[cl]}
                </span>
              )}
            </div>
            {i === selectedIndex && (
              <span className="text-xs text-[var(--color-cryo-text-muted)] font-mono">enter</span>
            )}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div
      ref={menuRef}
      className="slash-menu absolute bottom-full left-0 right-0 mb-2 rounded-xl bg-[var(--color-cryo-surface-2)] max-h-72 overflow-y-auto z-50"
    >
      <div className="px-3 py-2 text-xs text-[var(--color-cryo-text-muted)] font-mono uppercase tracking-wider border-b border-[var(--color-cryo-border)]">
        Biology Tools
      </div>
      {filteredCommands.map((cmd, i) => (
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
