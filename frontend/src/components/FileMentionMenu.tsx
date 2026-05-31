import { useEffect, useRef } from 'react'
import { FileText, Image, Clock, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import type { CollectionFileRecord } from '../lib/api'

interface Props {
  files: CollectionFileRecord[]
  filter: string
  selectedIndex: number
  onSelect: (file: CollectionFileRecord) => void
  visible: boolean
}

function fileIcon(ext: string | null) {
  if (!ext) return <FileText className="w-4 h-4 flex-shrink-0" />
  if (['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp', '.gif'].includes(ext))
    return <Image className="w-4 h-4 flex-shrink-0" />
  return <FileText className="w-4 h-4 flex-shrink-0" />
}

function statusBadge(status: CollectionFileRecord['status']) {
  switch (status) {
    case 'done':
      return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
    case 'processing':
    case 'pending':
      return <Loader2 className="w-3.5 h-3.5 text-yellow-400 animate-spin flex-shrink-0" />
    case 'error':
      return <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
    default:
      return <Clock className="w-3.5 h-3.5 text-[var(--color-cryo-text-muted)] flex-shrink-0" />
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

export default function FileMentionMenu({ files, filter, selectedIndex, onSelect, visible }: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const selectedRef = useRef<HTMLButtonElement>(null)

  const filtered = files.filter(f =>
    f.original_filename.toLowerCase().includes(filter.toLowerCase())
  )

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!visible || filtered.length === 0) return null

  return (
    <div
      ref={listRef}
      className="absolute bottom-full left-0 right-0 mb-1 z-50 rounded-xl overflow-hidden border border-[var(--color-cryo-border)] bg-[var(--color-cryo-surface-2)] shadow-xl max-h-64 overflow-y-auto"
    >
      <div className="px-3 py-1.5 border-b border-[var(--color-cryo-border)]">
        <span className="text-xs text-[var(--color-cryo-text-muted)] font-mono">
          @ mention a document
        </span>
      </div>
      {filtered.map((file, i) => (
        <button
          key={file.id}
          ref={i === selectedIndex ? selectedRef : undefined}
          onClick={() => onSelect(file)}
          className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${
            i === selectedIndex
              ? 'bg-[var(--color-cryo-accent)]/15 text-[var(--color-cryo-text)]'
              : 'hover:bg-[var(--color-cryo-surface-3)] text-[var(--color-cryo-text-muted)]'
          }`}
        >
          <span className={i === selectedIndex ? 'text-[var(--color-cryo-accent)]' : ''}>
            {fileIcon(file.file_ext)}
          </span>
          <span className="flex-1 min-w-0">
            <span className="block text-sm font-medium truncate text-[var(--color-cryo-text)]">
              {file.original_filename}
            </span>
            <span className="block text-xs text-[var(--color-cryo-text-muted)]">
              {formatSize(file.file_size)} · {file.file_ext?.replace('.', '').toUpperCase()}
            </span>
          </span>
          {statusBadge(file.status)}
        </button>
      ))}
      {filtered.length === 0 && (
        <div className="px-3 py-3 text-xs text-[var(--color-cryo-text-muted)]">
          No documents found. Upload a PDF or image first.
        </div>
      )}
    </div>
  )
}
