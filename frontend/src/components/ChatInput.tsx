import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Dna } from 'lucide-react'
import SlashMenu, { type SlashCommand, CELL_LINES } from './SlashMenu'
import FileUploadButton from './FileUploadButton'
import type { UploadRecord } from '../lib/api'

const DEFAULT_COMMANDS: SlashCommand[] = [
  // Literature
  { command: '/pubmed',      description: 'Search PubMed literature',           example: '/pubmed CRISPR glioblastoma',               category: 'literature' },
  { command: '/biorxiv',     description: 'Search bioRxiv preprints',            example: '/biorxiv single-cell RNA-seq',               category: 'literature' },
  // Protein & Structure
  { command: '/protein',     description: 'Look up protein/gene info',           example: '/protein TP53',                              category: 'protein' },
  { command: '/structure',   description: 'Find protein 3D structures',          example: '/structure EGFR',                            category: 'protein' },
  // Drug & Variant
  { command: '/drug',        description: 'Search drugs and compounds',          example: '/drug temozolomide',                         category: 'drug' },
  { command: '/targets',     description: 'Disease-target associations',         example: '/targets glioblastoma',                      category: 'drug' },
  { command: '/variant',     description: 'Variant clinical significance',       example: '/variant rs28934578',                        category: 'drug' },
  { command: '/vep',         description: 'Variant effect prediction',           example: '/vep 17:7675088:C:T',                        category: 'drug' },
  { command: '/repurpose',   description: 'Drug repurposing candidates',         example: '/repurpose Huntington disease',               category: 'drug' },
  // Simulation
  { command: '/digital_twin',description: 'Simulate metabolic drug response',   example: '/digital_twin imatinib --cell_line MCF7',     category: 'simulation' },
  { command: '/simulate',    description: 'Alias for /digital_twin',            example: '/simulate metformin --cell_line HeLa',        category: 'simulation' },
  { command: '/pathway',     description: 'Explore biological pathways',        example: '/pathway p53 signaling',                     category: 'simulation' },
  // Omics Databases
  { command: '/ppi',         description: 'Protein-protein interactions (StringDB)', example: '/ppi TP53',                             category: 'databases' },
  { command: '/kegg',        description: 'KEGG pathway search',                example: '/kegg cell cycle',                           category: 'databases' },
  { command: '/reactome',    description: 'Reactome pathway enrichment',        example: '/reactome BRCA1,BRCA2,ATM',                  category: 'databases' },
  // Analysis Pipelines
  { command: '/deseq',       description: 'Differential expression (PyDESeq2)', example: '/deseq counts.csv vs control',               category: 'analysis' },
  { command: '/scrna',       description: 'scRNA-seq clustering (Scanpy)',       example: '/scrna data.h5ad',                           category: 'analysis' },
  { command: '/annotate',    description: 'Cell type annotation (CellTypist)',   example: '/annotate scrna_processed.h5ad',             category: 'analysis' },
  { command: '/atac',        description: 'ATAC-seq peak calling (MACS3)',       example: '/atac sample.bam',                           category: 'analysis' },
  { command: '/chip',        description: 'ChIP-seq peak calling (MACS3)',       example: '/chip chip.bam vs input.bam',                category: 'analysis' },
  { command: '/meta',        description: 'Metagenomics (Kraken2 + HUMAnN3)',    example: '/meta sample_R1.fastq.gz',                   category: 'analysis' },
  { command: '/ms',          description: 'Mass spectrometry proteomics',        example: '/ms proteinGroups.txt',                      category: 'analysis' },
  { command: '/sec',         description: 'SEC chromatography analysis',         example: '/sec sec_data.csv',                          category: 'analysis' },
  // Research Workflow
  { command: '/novelty',     description: 'Research novelty / saturation check', example: '/novelty CRISPR base editing sickle cell',  category: 'research' },
  { command: '/paper',       description: 'Full manuscript planning pipeline',   example: '/paper spatial transcriptomics TNBC',        category: 'research' },
  // Output
  { command: '/compare',     description: 'Compare genes/proteins/drugs',        example: '/compare BRCA1 BRCA2',                       category: 'output' },
  { command: '/export',      description: 'Export data to Excel',                example: '/export TP53 variants',                      category: 'output' },
  { command: '/report',      description: 'Generate interactive HTML report',    example: '/report glioblastoma drug targets',           category: 'output' },
  { command: '/chart',       description: 'Generate visualization',              example: '/chart cancer mutation frequency',            category: 'output' },
]

// Detect if user has typed --cell_line (with optional partial name after it)
function detectCellLineMode(val: string): { active: boolean; filter: string } {
  const isDigitalTwin = val.startsWith('/digital_twin') || val.startsWith('/simulate')
  if (!isDigitalTwin) return { active: false, filter: '' }
  const match = val.match(/--cell_line\s+(\S*)$/)
  if (match) return { active: true, filter: match[1] }
  // also trigger when --cell_line is the last thing typed (no space yet)
  if (/--cell_line$/.test(val.trimEnd())) return { active: true, filter: '' }
  return { active: false, filter: '' }
}

interface Props {
  onSend: (message: string) => void
  disabled?: boolean
  conversationId?: string
}

export default function ChatInput({ onSend, disabled, conversationId }: Props) {
  const [input, setInput] = useState('')
  const [showSlash, setShowSlash] = useState(false)
  const [slashFilter, setSlashFilter] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [cellLineMode, setCellLineMode] = useState(false)
  const [cellLineFilter, setCellLineFilter] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const filteredCommands = DEFAULT_COMMANDS.filter(c =>
    c.command.includes(slashFilter.toLowerCase()) ||
    c.description.toLowerCase().includes(slashFilter.toLowerCase())
  )

  const filteredCellLines = CELL_LINES.filter(cl =>
    cl.toLowerCase().includes(cellLineFilter.toLowerCase())
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
    setSelectedIndex(0)

    // Cell line sub-menu takes priority when --cell_line detected
    const clMode = detectCellLineMode(val)
    if (clMode.active) {
      setCellLineMode(true)
      setCellLineFilter(clMode.filter)
      setShowSlash(false)
      return
    }

    setCellLineMode(false)

    // Slash command menu: only when input is purely a slash command fragment
    if (val === '/' || val.match(/^\/\w*$/)) {
      setShowSlash(true)
      setSlashFilter(val)
    } else {
      setShowSlash(false)
    }
  }, [])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const menuOpen = showSlash || cellLineMode
    const listLength = cellLineMode ? filteredCellLines.length : filteredCommands.length

    if (menuOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, listLength - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (cellLineMode && filteredCellLines[selectedIndex]) {
          selectCellLine(filteredCellLines[selectedIndex])
        } else if (showSlash && filteredCommands[selectedIndex]) {
          selectCommand(filteredCommands[selectedIndex])
        }
        return
      }
      if (e.key === 'Escape') {
        setShowSlash(false)
        setCellLineMode(false)
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [showSlash, cellLineMode, filteredCommands, filteredCellLines, selectedIndex, input])

  const selectCommand = (cmd: SlashCommand) => {
    setInput(cmd.command + ' ')
    setShowSlash(false)
    setSelectedIndex(0)
    textareaRef.current?.focus()
  }

  const selectCellLine = (cellLine: string) => {
    // Replace partial name after --cell_line with the selected line
    const newVal = input.replace(/--cell_line\s*\S*$/, `--cell_line ${cellLine}`)
    setInput(newVal)
    setCellLineMode(false)
    setSelectedIndex(0)
    textareaRef.current?.focus()
  }

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
    setShowSlash(false)
    setCellLineMode(false)
  }

  const handleUploaded = useCallback((record: UploadRecord) => {
    const cmd = record.suggested_command || ''
    const insertion = cmd
      ? `${cmd} ${record.server_path} `
      : `${record.server_path} `
    setInput(prev => prev ? `${prev.trimEnd()} ${insertion}` : insertion)
    textareaRef.current?.focus()
  }, [])

  const menuVisible = showSlash || cellLineMode

  return (
    <div className="relative">
      <SlashMenu
        commands={DEFAULT_COMMANDS}
        filter={slashFilter}
        selectedIndex={selectedIndex}
        onSelect={selectCommand}
        visible={menuVisible}
        mode={cellLineMode ? 'cell_lines' : 'commands'}
        cellLineFilter={cellLineFilter}
        onSelectCellLine={selectCellLine}
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
        <div className="flex items-center gap-1 mb-0.5 flex-shrink-0">
          <FileUploadButton
            onUploaded={handleUploaded}
            conversationId={conversationId}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || disabled}
            className="p-2 rounded-lg bg-[var(--color-cryo-accent)] text-[var(--color-cryo-bg)] hover:brightness-110 transition-all disabled:opacity-30 disabled:hover:brightness-100"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
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
