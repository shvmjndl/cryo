/**
 * Shared file upload button — used by ChatInput (chat mode) and ChatNode (workspace).
 * Drag-and-drop + click-to-browse.
 * - Bioinformatics files (.csv, .h5ad, .bam…) → /uploads → injects server_path into chat
 * - Documents (.pdf, images) → /collections/upload → VLM OCR → injects /collections reference
 */

import { useRef, useState, useCallback } from 'react'
import { Paperclip, X, CheckCircle, AlertCircle, Loader2, FileText } from 'lucide-react'
import { uploads, collections, type UploadRecord, type CollectionFileRecord } from '../lib/api'

const DOCUMENT_EXTENSIONS = new Set([
  '.pdf',
  '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp', '.gif',
])

const BIO_EXTENSIONS = [
  '.csv', '.tsv', '.txt',
  '.h5ad', '.h5', '.hdf5',
  '.bam',
  '.fastq', '.fastq.gz', '.fq', '.fq.gz',
  '.xlsx', '.xls',
  '.parquet',
  '.json',
  '.fa', '.fasta',
  '.vcf', '.vcf.gz',
  '.bed',
]

const ACCEPTED = [...BIO_EXTENSIONS, ...Array.from(DOCUMENT_EXTENSIONS)].join(',')

interface Props {
  onUploaded: (record: UploadRecord) => void
  onDocumentUploaded?: (record: CollectionFileRecord) => void
  conversationId?: string
  compact?: boolean
}

type UploadState =
  | { status: 'idle' }
  | { status: 'uploading'; filename: string; pct: number; isDoc: boolean }
  | { status: 'done_bio'; record: UploadRecord }
  | { status: 'done_doc'; record: CollectionFileRecord }
  | { status: 'error'; message: string }

const DATA_TYPE_LABELS: Record<string, string> = {
  rnaseq_counts:  'RNA-seq counts',
  scrna:          'scRNA-seq',
  bam:            'BAM alignment',
  fastq:          'FASTQ reads',
  ms_proteomics:  'Proteomics',
  sec:            'SEC data',
  metadata:       'Metadata',
  document:       'Document',
  other:          'Data file',
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`
  return `${(b / 1024 ** 3).toFixed(2)} GB`
}

function getExt(filename: string): string {
  const lower = filename.toLowerCase()
  for (const de of ['.fastq.gz', '.fq.gz', '.vcf.gz', '.tar.gz']) {
    if (lower.endsWith(de)) return de
  }
  return '.' + lower.split('.').pop()!
}

export default function FileUploadButton({ onUploaded, onDocumentUploaded, conversationId, compact = false }: Props) {
  const [state, setState] = useState<UploadState>({ status: 'idle' })
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (file: File) => {
    const ext = getExt(file.name)
    const isDoc = DOCUMENT_EXTENSIONS.has(ext)

    setState({ status: 'uploading', filename: file.name, pct: 0, isDoc })
    try {
      if (isDoc) {
        const record = await collections.upload(
          file,
          { conversationId, collectionName: file.name.replace(/\.[^.]+$/, '') },
          pct => setState({ status: 'uploading', filename: file.name, pct, isDoc: true }),
        )
        setState({ status: 'done_doc', record })
        onDocumentUploaded?.(record)
        setTimeout(() => setState({ status: 'idle' }), 5000)
      } else {
        const record = await uploads.upload(file, conversationId, pct =>
          setState({ status: 'uploading', filename: file.name, pct, isDoc: false }),
        )
        setState({ status: 'done_bio', record })
        onUploaded(record)
        setTimeout(() => setState({ status: 'idle' }), 4000)
      }
    } catch (e) {
      setState({ status: 'error', message: e instanceof Error ? e.message : 'Upload failed' })
      setTimeout(() => setState({ status: 'idle' }), 5000)
    }
  }, [conversationId, onUploaded, onDocumentUploaded])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const iconSize = compact ? 'w-3.5 h-3.5' : 'w-4 h-4'
  const btnBase = compact ? 'p-1 rounded transition-colors' : 'p-1.5 rounded-lg transition-colors'

  if (state.status === 'uploading') {
    return (
      <div className={`flex items-center gap-2 ${compact ? 'px-1' : 'px-2'}`}>
        <Loader2 className={`${iconSize} text-[var(--color-cryo-accent)] animate-spin flex-shrink-0`} />
        {!compact && (
          <div className="flex-1 min-w-0">
            <div className="text-xs text-[var(--color-cryo-text-dim)] truncate max-w-[120px]">
              {state.isDoc ? '📄 ' : ''}{state.filename}
            </div>
            <div className="h-1 mt-0.5 rounded-full bg-[var(--color-cryo-border)] overflow-hidden w-24">
              <div
                className="h-full bg-[var(--color-cryo-accent)] transition-all duration-200 rounded-full"
                style={{ width: `${state.pct}%` }}
              />
            </div>
          </div>
        )}
        {compact && <span className="text-[10px] text-[var(--color-cryo-text-muted)]">{state.pct}%</span>}
      </div>
    )
  }

  if (state.status === 'done_bio') {
    const { record } = state
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[var(--color-cryo-emerald)]/10 border border-[var(--color-cryo-emerald)]/20">
        <CheckCircle className={`${iconSize} text-[var(--color-cryo-emerald)] flex-shrink-0`} />
        {!compact && (
          <div className="min-w-0">
            <div className="text-xs font-medium text-[var(--color-cryo-emerald)] truncate max-w-[140px]">
              {record.original_filename}
            </div>
            <div className="text-[10px] text-[var(--color-cryo-text-muted)]">
              {DATA_TYPE_LABELS[record.data_type || ''] || 'Uploaded'} · {formatBytes(record.file_size)}
              {record.suggested_command && (
                <span className="ml-1 font-mono text-[var(--color-cryo-accent)]">{record.suggested_command}</span>
              )}
            </div>
          </div>
        )}
        <button onClick={() => setState({ status: 'idle' })} className="ml-0.5 text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text)] transition-colors">
          <X className="w-3 h-3" />
        </button>
      </div>
    )
  }

  if (state.status === 'done_doc') {
    const { record } = state
    const statusColor = record.status === 'error'
      ? 'text-red-400 bg-red-500/10 border-red-500/20'
      : 'text-[var(--color-cryo-cyan)] bg-[var(--color-cryo-cyan)]/10 border-[var(--color-cryo-cyan)]/20'
    return (
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border ${statusColor}`}>
        <FileText className={`${iconSize} flex-shrink-0`} />
        {!compact && (
          <div className="min-w-0">
            <div className="text-xs font-medium truncate max-w-[140px]">
              {record.original_filename}
            </div>
            <div className="text-[10px] opacity-75">
              {record.status === 'done' ? 'Parsed ✓' : record.status === 'error' ? 'OCR failed' : 'Processing…'}
              {' · '}{record.collection.name}
            </div>
          </div>
        )}
        <button onClick={() => setState({ status: 'idle' })} className="ml-0.5 opacity-70 hover:opacity-100 transition-opacity">
          <X className="w-3 h-3" />
        </button>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-red-500/10 border border-red-500/20">
        <AlertCircle className={`${iconSize} text-red-400 flex-shrink-0`} />
        {!compact && <span className="text-xs text-red-400 truncate max-w-[140px]">{state.message}</span>}
        <button onClick={() => setState({ status: 'idle' })} className="ml-0.5 text-red-400/70 hover:text-red-400">
          <X className="w-3 h-3" />
        </button>
      </div>
    )
  }

  // Idle — show the button + hidden input
  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = '' }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragEnter={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={e => { e.preventDefault(); setDragging(false) }}
        onDragOver={e => e.preventDefault()}
        onDrop={onDrop}
        className={`${btnBase} ${
          dragging
            ? 'bg-[var(--color-cryo-accent)]/20 text-[var(--color-cryo-accent)] border border-[var(--color-cryo-accent)]/40'
            : 'text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-accent)] hover:bg-[var(--color-cryo-accent)]/10'
        }`}
        title="Attach file (.csv, .h5ad, .bam, .fastq, .pdf, .png…)"
      >
        <Paperclip className={iconSize} />
      </button>
    </>
  )
}
