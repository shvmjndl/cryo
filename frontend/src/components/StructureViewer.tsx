import { useEffect, useRef, useState } from 'react'
import { Box, ExternalLink, Maximize2, Minimize2, RotateCcw } from 'lucide-react'

declare const $3Dmol: any

interface Props {
  pdbId: string
  title?: string
  compact?: boolean  // workspace nodes — smaller canvas, resize after layout settles
}

export function StructureViewer({ pdbId, title, compact = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<any>(null)
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const id = pdbId.toUpperCase()

  useEffect(() => {
    if (!containerRef.current) return
    let cancelled = false

    const init = async () => {
      try {
        // Wait for 3Dmol CDN to be ready
        let attempts = 0
        while (typeof $3Dmol === 'undefined' && attempts < 30) {
          await new Promise(r => setTimeout(r, 200))
          attempts++
        }
        if (typeof $3Dmol === 'undefined') throw new Error('3Dmol not loaded')
        if (cancelled || !containerRef.current) return

        const viewer = $3Dmol.createViewer(containerRef.current, {
          backgroundColor: '#0a0e14',
        })
        viewerRef.current = viewer

        const res = await fetch(`/api/structure/${id}`)
        if (!res.ok) throw new Error(`${id} not found (${res.status})`)
        const data = await res.text()
        if (cancelled) return

        viewer.addModel(data, 'cif')
        viewer.setStyle({}, { cartoon: { color: 'spectrum' } })
        viewer.zoomTo()
        viewer.render()
        setLoading(false)

        // Re-measure after layout settles — critical for workspace nodes
        // React Flow lays out nodes asynchronously, so the container may have
        // been 0×0 when 3Dmol first measured it.
        setTimeout(() => {
          if (!cancelled && viewerRef.current) {
            viewerRef.current.resize()
            viewerRef.current.render()
          }
        }, 150)
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.message ?? `Could not load ${id}`)
          setLoading(false)
        }
      }
    }

    init()
    return () => { cancelled = true }
  }, [id])

  const resetView = () => {
    viewerRef.current?.zoomTo()
    viewerRef.current?.render()
  }

  const handleExpand = () => {
    setExpanded(e => !e)
    setTimeout(() => {
      viewerRef.current?.resize()
      viewerRef.current?.render()
    }, 60)
  }

  const canvasClass = [
    'structure-viewer-canvas',
    compact && !expanded ? 'structure-viewer-canvas-compact' : '',
  ].filter(Boolean).join(' ')

  return (
    <div className={`structure-viewer${expanded ? ' structure-viewer-expanded' : ''}`}>
      <div className="structure-viewer-header">
        <Box className="w-3.5 h-3.5 text-[var(--color-cryo-accent)]" />
        <span className="structure-viewer-pdb">{id}</span>
        {title && <span className="structure-viewer-name">{title}</span>}
        <div className="structure-viewer-actions">
          <button onClick={resetView} title="Reset view">
            <RotateCcw className="w-3 h-3" />
          </button>
          <a href={`https://www.rcsb.org/structure/${id}`} target="_blank" rel="noopener noreferrer" title="Open in RCSB">
            <ExternalLink className="w-3 h-3" />
          </a>
          <button onClick={handleExpand} title={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
          </button>
        </div>
      </div>

      <div ref={containerRef} className={canvasClass}>
        {loading && !error && (
          <div className="structure-viewer-overlay">
            <span className="animate-pulse-glow text-xs text-[var(--color-cryo-text-dim)]">
              Loading {id}…
            </span>
          </div>
        )}
        {error && (
          <div className="structure-viewer-overlay">
            <span className="text-xs text-[var(--color-cryo-red)]">{error}</span>
          </div>
        )}
      </div>

      <div className="structure-viewer-footer">
        Drag to rotate · Scroll to zoom · Right-drag to pan
      </div>
    </div>
  )
}
