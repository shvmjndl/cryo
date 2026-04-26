import { useEffect, useRef } from 'react'
import { X, ExternalLink, FileText, RefreshCw } from 'lucide-react'

interface Props {
  url: string
  filename: string
  onClose: () => void
}

export default function ReportPanel({ url, filename, onClose }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <>
      {/* Backdrop — click to close */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 h-screen z-50 flex flex-col"
        style={{
          width: 'clamp(480px, 58vw, 1100px)',
          background: 'var(--color-cryo-surface)',
          borderLeft: '1px solid var(--color-cryo-border-bright)',
          boxShadow: '-8px 0 40px rgba(0,0,0,0.4)',
          animation: 'slideInRight 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-4 py-3 border-b flex-shrink-0"
          style={{ borderColor: 'var(--color-cryo-border)' }}
        >
          <FileText className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-cryo-accent)' }} />
          <span
            className="flex-1 text-sm font-mono truncate"
            style={{ color: 'var(--color-cryo-text-dim)' }}
            title={filename}
          >
            {filename}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => iframeRef.current && (iframeRef.current.src = iframeRef.current.src)}
              className="p-1.5 rounded transition-colors"
              style={{ color: 'var(--color-cryo-text-muted)' }}
              title="Reload"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors"
              style={{ color: 'var(--color-cryo-accent)' }}
              title="Open in new tab"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              New tab
            </a>
            <button
              onClick={onClose}
              className="p-1.5 rounded transition-colors hover:bg-red-500/10"
              style={{ color: 'var(--color-cryo-text-muted)' }}
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* iframe */}
        <iframe
          ref={iframeRef}
          src={url}
          title={filename}
          className="flex-1 w-full"
          style={{ border: 'none', display: 'block', background: '#fff' }}
          sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals"
        />
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
    </>
  )
}
