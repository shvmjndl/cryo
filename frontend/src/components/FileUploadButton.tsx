/**
 * Shared file upload button — used by ChatInput (chat mode) and ChatNode (workspace).
 * Drag-and-drop + click-to-browse. Shows progress bar, then injects server path into chat.
 */

import { useRef, useState, useCallback } from 'react'
import { Paperclip, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { uploads, type UploadRecord } from '../lib/api'

interface Props {
  onUploaded: (record: UploadRecord) => void   // parent inserts path into input
  conversationId?: string
  compact?: boolean                             // smaller variant for workspace nodes
}

type UploadState =
  | { status: 'idle' }
  | { status: 'uploading'; filename: string; pct: number }
  | { status: 'done'; record: UploadRecord }
  | { status: 'error'; message: string }

const ACCEPTED = [
  '.csv', '.tsv', '.txt',
  '.h5ad', '.h5', '.hdf5',
  '.bam',
  '.fastq', '.fastq.gz', '.fq', '.fq.gz',
  '.xlsx', '.xls',
  '.parquet',
  '.json',
  '.fa', '.fasta',
].join(',')

const DATA_TYPE_LABELS: Record<string, string> = {
  rnaseq_counts:  'RNA-seq counts',
  scrna:          'scRNA-seq',
  bam:            'BAM alignment',
  fastq:          'FASTQ reads',
  ms_proteomics:  'Proteomics',
  sec:            'SEC data',
  metadata:       'Metadata',
  other:          'Data file',
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`
  return `${(b / 1024 ** 3).toFixed(2)} GB`
}

export default function FileUploadButton({ onUploaded, conversationId, compact = false }: Props) {
  const [state, setState] = useState<UploadState>({ status: 'idle' })
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (file: File) => {
    setState({ status: 'uploading', filename: file.name, pct: 0 })
    try {
      const record = await uploads.upload(file, conversationId, pct => {
        setState({ status: 'uploading', filename: file.name, pct })
      })
      setState({ status: 'done', record })
      onUploaded(record)
      // Auto-clear success badge after 4 s
      setTimeout(() => setState({ status: 'idle' }), 4000)
    } catch (e) {
      setState({ status: 'error', message: e instanceof Error ? e.message : 'Upload failed' })
      setTimeout(() => setState({ status: 'idle' }), 5000)
    }
  }, [conversationId, onUploaded])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const iconSize = compact ? 'w-3.5 h-3.5' : 'w-4 h-4'
  const btnBase = compact
    ? 'p-1 rounded transition-colors'
    : 'p-1.5 rounded-lg transition-colors'

  if (state.status === 'uploading') {
    return (
      <div className={`flex items-center gap-2 ${compact ? 'px-1' : 'px-2'}`}>
        <Loader2 className={`${iconSize} text-[var(--color-cryo-accent)] animate-spin flex-shrink-0`} />
        {!compact && (
          <div className="flex-1 min-w-0">
            <div className="text-xs text-[var(--color-cryo-text-dim)] truncate max-w-[120px]">{state.filename}</div>
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

  if (state.status === 'done') {
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
        <button
          onClick={() => setState({ status: 'idle' })}
          className="ml-0.5 text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text)] transition-colors"
        >
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
        title="Attach file (.csv, .h5ad, .bam, .fastq, .xlsx…)"
      >
        <Paperclip className={iconSize} />
      </button>
    </>
  )
}
