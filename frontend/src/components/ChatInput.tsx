import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Dna, X } from 'lucide-react'
import SlashMenu, { type SlashCommand, type GemModel, CELL_LINES, GEM_MODELS } from './SlashMenu'
import FileMentionMenu from './FileMentionMenu'
import FileUploadButton from './FileUploadButton'
import type { UploadRecord, CollectionFileRecord } from '../lib/api'
import { collections } from '../lib/api'

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
  { command: '/gem',         description: 'Query genome-scale metabolic model', example: '/gem stats --model ijo1366',                  category: 'simulation' },
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

function detectCellLineMode(val: string): { active: boolean; filter: string } {
  const isDigitalTwin = val.startsWith('/digital_twin') || val.startsWith('/simulate')
  if (!isDigitalTwin) return { active: false, filter: '' }
  const match = val.match(/--cell[_\-]?line\s+(\S*)$/)
  if (match) return { active: true, filter: match[1] }
  if (/--cell[_\-]?line$/.test(val.trimEnd())) return { active: true, filter: '' }
  return { active: false, filter: '' }
}

function detectModelMode(val: string): { active: boolean; filter: string } {
  const isDigitalTwin = val.startsWith('/digital_twin') || val.startsWith('/simulate')
    || val.startsWith('/gem')
  if (!isDigitalTwin) return { active: false, filter: '' }
  const match = val.match(/--(?:model|backbone)\s+(\S*)$/)
  if (match) return { active: true, filter: match[1] }
  if (/--(?:model|backbone)$/.test(val.trimEnd())) return { active: true, filter: '' }
  return { active: false, filter: '' }
}

// Detect @ mention: triggers when last word starts with @
function detectMentionMode(val: string): { active: boolean; filter: string } {
  const match = val.match(/@(\w*)$/)
  if (match) return { active: true, filter: match[1] }
  return { active: false, filter: '' }
}

interface MentionedFile {
  id: string
  name: string
}

interface Props {
  onSend: (message: string, fileIds?: string[]) => void
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
  const [modelMode, setModelMode] = useState(false)
  const [modelFilter, setModelFilter] = useState('')

  // @ mention state
  const [mentionMode, setMentionMode] = useState(false)
  const [mentionFilter, setMentionFilter] = useState('')
  const [availableFiles, setAvailableFiles] = useState<CollectionFileRecord[]>([])
  const [mentionedFiles, setMentionedFiles] = useState<MentionedFile[]>([])

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const filteredCommands = DEFAULT_COMMANDS.filter(c =>
    c.command.includes(slashFilter.toLowerCase()) ||
    c.description.toLowerCase().includes(slashFilter.toLowerCase())
  )

  const filteredCellLines = CELL_LINES.filter(cl =>
    cl.toLowerCase().includes(cellLineFilter.toLowerCase())
  )

  const filteredModels = GEM_MODELS.filter(m =>
    m.key.toLowerCase().includes(modelFilter.toLowerCase()) ||
    m.label.toLowerCase().includes(modelFilter.toLowerCase()) ||
    m.organism.toLowerCase().includes(modelFilter.toLowerCase())
  )

  const filteredFiles = availableFiles.filter(f =>
    f.original_filename.toLowerCase().includes(mentionFilter.toLowerCase())
  )

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
    }
  }, [input])

  // Fetch available files when @ mode activates
  useEffect(() => {
    if (!mentionMode) return
    collections.listFiles(conversationId).then(setAvailableFiles).catch(() => setAvailableFiles([]))
  }, [mentionMode, conversationId])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setInput(val)
    setSelectedIndex(0)

    // --model sub-menu
    const mMode = detectModelMode(val)
    if (mMode.active) {
      setModelMode(true)
      setModelFilter(mMode.filter)
      setCellLineMode(false)
      setShowSlash(false)
      setMentionMode(false)
      return
    }
    setModelMode(false)

    // --cell_line sub-menu
    const clMode = detectCellLineMode(val)
    if (clMode.active) {
      setCellLineMode(true)
      setCellLineFilter(clMode.filter)
      setShowSlash(false)
      setMentionMode(false)
      return
    }
    setCellLineMode(false)

    // @ mention
    const mtn = detectMentionMode(val)
    if (mtn.active) {
      setMentionMode(true)
      setMentionFilter(mtn.filter)
      setShowSlash(false)
      return
    }
    setMentionMode(false)

    // Slash command menu
    if (val === '/' || val.match(/^\/\w*$/)) {
      setShowSlash(true)
      setSlashFilter(val)
    } else {
      setShowSlash(false)
    }
  }, [])

  const selectMention = useCallback((file: CollectionFileRecord) => {
    // Replace the trailing @filter with @filename
    const newInput = input.replace(/@\w*$/, `@${file.original_filename} `)
    setInput(newInput)
    setMentionMode(false)
    setSelectedIndex(0)
    // Track mentioned file (deduplicate)
    setMentionedFiles(prev => prev.some(f => f.id === file.id) ? prev : [...prev, { id: file.id, name: file.original_filename }])
    textareaRef.current?.focus()
  }, [input])

  const removeMention = useCallback((fileId: string) => {
    const file = mentionedFiles.find(f => f.id === fileId)
    if (file) {
      setInput(prev => prev.replace(new RegExp(`@${file.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s?`, 'g'), ''))
    }
    setMentionedFiles(prev => prev.filter(f => f.id !== fileId))
    textareaRef.current?.focus()
  }, [mentionedFiles])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const menuOpen = showSlash || cellLineMode || modelMode || mentionMode
    const listLength = modelMode ? filteredModels.length
      : cellLineMode ? filteredCellLines.length
      : mentionMode ? filteredFiles.length
      : filteredCommands.length

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
        if (modelMode && filteredModels[selectedIndex]) {
          selectModel(filteredModels[selectedIndex])
        } else if (cellLineMode && filteredCellLines[selectedIndex]) {
          selectCellLine(filteredCellLines[selectedIndex])
        } else if (mentionMode && filteredFiles[selectedIndex]) {
          selectMention(filteredFiles[selectedIndex])
        } else if (showSlash && filteredCommands[selectedIndex]) {
          selectCommand(filteredCommands[selectedIndex])
        }
        return
      }
      if (e.key === 'Escape') {
        setShowSlash(false)
        setCellLineMode(false)
        setModelMode(false)
        setMentionMode(false)
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [showSlash, cellLineMode, modelMode, mentionMode, filteredCommands, filteredCellLines, filteredModels, filteredFiles, selectedIndex, input, selectMention])

  const selectCommand = (cmd: SlashCommand) => {
    setInput(cmd.command + ' ')
    setShowSlash(false)
    setSelectedIndex(0)
    textareaRef.current?.focus()
  }

  const selectCellLine = (cellLine: string) => {
    const newVal = input.replace(/--cell_line\s*\S*$/, `--cell_line ${cellLine}`)
    setInput(newVal)
    setCellLineMode(false)
    setSelectedIndex(0)
    textareaRef.current?.focus()
  }

  const selectModel = (model: GemModel) => {
    const newVal = input.replace(/--(?:model|backbone)\s*\S*$/, `--model ${model.key}`)
    setInput(newVal)
    setModelMode(false)
    setSelectedIndex(0)
    textareaRef.current?.focus()
  }

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    const fileIds = mentionedFiles.map(f => f.id)
    onSend(trimmed, fileIds.length ? fileIds : undefined)
    setInput('')
    setShowSlash(false)
    setCellLineMode(false)
    setModelMode(false)
    setMentionMode(false)
    setMentionedFiles([])
  }

  const handleUploaded = useCallback((record: UploadRecord) => {
    const cmd = record.suggested_command || ''
    const insertion = cmd
      ? `${cmd} ${record.server_path} `
      : `${record.server_path} `
    setInput(prev => prev ? `${prev.trimEnd()} ${insertion}` : insertion)
    textareaRef.current?.focus()
  }, [])

  const handleDocumentUploaded = useCallback((record: CollectionFileRecord) => {
    // Auto-tag the uploaded document as a mention
    setMentionedFiles(prev =>
      prev.some(f => f.id === record.id)
        ? prev
        : [...prev, { id: record.id, name: record.original_filename }]
    )
    textareaRef.current?.focus()
  }, [])

  const menuVisible = showSlash || cellLineMode || modelMode

  return (
    <div className="relative">
      {/* @ file mention menu */}
      <FileMentionMenu
        files={availableFiles}
        filter={mentionFilter}
        selectedIndex={selectedIndex}
        onSelect={selectMention}
        visible={mentionMode}
      />

      {/* Slash / cell-line / model menus */}
      <SlashMenu
        commands={DEFAULT_COMMANDS}
        filter={slashFilter}
        selectedIndex={selectedIndex}
        onSelect={selectCommand}
        visible={menuVisible}
        mode={modelMode ? 'models' : cellLineMode ? 'cell_lines' : 'commands'}
        cellLineFilter={cellLineFilter}
        onSelectCellLine={selectCellLine}
        modelFilter={modelFilter}
        onSelectModel={selectModel}
      />

      {/* Mentioned file pills */}
      {mentionedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-1.5 px-1">
          {mentionedFiles.map(f => (
            <span
              key={f.id}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-[var(--color-cryo-accent)]/15 text-[var(--color-cryo-accent)] border border-[var(--color-cryo-accent)]/30"
            >
              <span className="max-w-[180px] truncate">{f.name}</span>
              <button
                onClick={() => removeMention(f.id)}
                className="hover:text-[var(--color-cryo-text)] transition-colors"
                tabIndex={-1}
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2 p-3 rounded-xl bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] focus-within:border-[var(--color-cryo-accent)] transition-colors">
        <Dna className="w-5 h-5 text-[var(--color-cryo-accent)] mb-1.5 flex-shrink-0 opacity-50" strokeWidth={1.5} />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder='Ask about biology, type "/" for tools, "@" to tag a document...'
          disabled={disabled}
          rows={1}
          className="flex-1 bg-transparent text-[var(--color-cryo-text)] placeholder:text-[var(--color-cryo-text-muted)] resize-none focus:outline-none text-sm leading-relaxed"
        />
        <div className="flex items-center gap-1 mb-0.5 flex-shrink-0">
          <FileUploadButton
            onUploaded={handleUploaded}
            onDocumentUploaded={handleDocumentUploaded}
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
          Type <kbd className="px-1 py-0.5 rounded bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-accent)]">/</kbd> for tools ·{' '}
          <kbd className="px-1 py-0.5 rounded bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-accent)]">@</kbd> to tag a document
        </span>
        <span className="text-xs text-[var(--color-cryo-text-muted)]">
          Shift+Enter for newline
        </span>
      </div>
    </div>
  )
}
