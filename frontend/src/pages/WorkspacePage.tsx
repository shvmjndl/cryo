import { useState, useCallback, useRef, useEffect } from 'react'
import {
  ReactFlow, addEdge, useNodesState, useEdgesState, Controls, MiniMap,
  Background, BackgroundVariant,
  type Node, type Edge, type Connection, type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Plus, Dna, LogOut, MessageSquare, MoreVertical, Trash2, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, GitBranch as BranchIcon } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import ChatNode, { type ChatNodeData } from '../components/ChatNode'
import ReportPanel from '../components/ReportPanel'
import { workspace as wsApi } from '../lib/api'

interface Props {
  user: { id: string; username: string }
  onLogout: () => void
}

const nodeTypes: NodeTypes = { chatNode: ChatNode as any }

let nodeIdCounter = 0
function nextNodeId() { return `node-${++nodeIdCounter}` }

export default function WorkspacePage({ user, onLogout }: Props) {
  const navigate = useNavigate()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [loaded, setLoaded] = useState(false)
  const [reportPanel, setReportPanel] = useState<{ url: string; filename: string } | null>(null)

  // Listen for report open events fired by FileCard inside ChatNode messages
  useEffect(() => {
    const handler = (e: Event) => {
      const { url, filename } = (e as CustomEvent).detail
      setReportPanel({ url, filename })
    }
    window.addEventListener('cryo:open-report', handler)
    return () => window.removeEventListener('cryo:open-report', handler)
  }, [])

  // Workspace state
  const [workspaces, setWorkspaces] = useState<{id: string; name: string}[]>([])
  const [activeWsId, setActiveWsId] = useState<string | null>(null)
  const [wsName, setWsName] = useState('Research Session')
  const [editingName, setEditingName] = useState(false)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  // Panel state
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(false)
  const [leftWidth, setLeftWidth] = useState(210)
  const [rightWidth, setRightWidth] = useState(210)

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ─── Load workspace list on mount ───
  useEffect(() => {
    wsApi.list().then((list: any[]) => {
      setWorkspaces(list)
      if (list.length > 0) {
        loadWorkspace(list[0].id, list[0].name)
      }
    }).catch(console.error)
  }, [])

  function loadWorkspace(id: string, name: string) {
    setActiveWsId(id)
    setWsName(name)
    wsApi.get(id).then((data: any) => {
      if (data.nodes?.length > 0) {
        const maxId = Math.max(0, ...data.nodes.map((n: any) => parseInt(n.id.replace('node-', '')) || 0))
        nodeIdCounter = maxId
        setNodes(data.nodes.map((n: any) => ({
          id: n.id, type: 'chatNode',
          position: { x: n.position_x, y: n.position_y },
          data: {
            title: n.title, conversationId: n.conversation_id, messages: [],
            branchContext: n.branch_context, minimized: n.minimized,
            onBranch: handleBranch, onClose: handleClose,
            onTitleUpdate: handleTitleUpdate, onConversationUpdate: handleConversationUpdate,
          } as ChatNodeData,
          style: { width: n.width || 400, height: 420 },
        })))
        setEdges(data.edges.map((e: any) => ({
          id: e.id, source: e.source_node_id, target: e.target_node_id,
          animated: true, style: { stroke: '#06b6d4', strokeWidth: 2 },
          label: e.label || '',
          labelStyle: { fontSize: 9, fill: '#64748b' },
          labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
          labelBgPadding: [4, 4] as [number, number], labelBgBorderRadius: 4,
        })))
      } else {
        setNodes([])
        setEdges([])
      }
      setLoaded(true)
    }).catch(() => { setNodes([]); setEdges([]); setLoaded(true) })
  }

  // ─── Auto-save (debounced 2s) ───
  useEffect(() => {
    if (!loaded || !activeWsId) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      wsApi.save(activeWsId, {
        nodes: nodes.map(n => ({
          id: n.id, title: (n.data as any)?.title || 'New Research',
          conversation_id: (n.data as any)?.conversationId || null,
          parent_node_id: null,
          position_x: n.position.x, position_y: n.position.y,
          width: (n.style as any)?.width || 400,
          minimized: (n.data as any)?.minimized || false,
          branch_context: (n.data as any)?.branchContext || null,
        })),
        edges: edges.map(e => ({
          id: e.id, source_node_id: e.source, target_node_id: e.target,
          label: typeof e.label === 'string' ? e.label : null,
        })),
      }).catch(console.error)
    }, 2000)
  }, [nodes, edges, loaded, activeWsId])

  const onConnect = useCallback(
    (params: Connection) => setEdges(eds => addEdge({ ...params, animated: true, style: { stroke: '#06b6d4', strokeWidth: 2 } }, eds)),
    [setEdges],
  )

  const addNode = useCallback((options?: { parentId?: string; branchContext?: string }) => {
    const id = nextNodeId()
    let position = { x: 100 + nodes.length * 420, y: 100 + (nodes.length % 3) * 80 }
    if (options?.parentId) {
      const parent = nodes.find(n => n.id === options.parentId)
      if (parent) position = { x: parent.position.x + 440, y: parent.position.y + Math.random() * 100 - 50 }
    }
    const newNode: Node = {
      id, type: 'chatNode', position,
      data: {
        title: 'New Research', conversationId: null, messages: [],
        branchContext: options?.branchContext, minimized: false,
        onBranch: handleBranch, onClose: handleClose,
        onTitleUpdate: handleTitleUpdate, onConversationUpdate: handleConversationUpdate,
      } as ChatNodeData,
      style: { width: 400, height: 420 },
    }
    setNodes(nds => [...nds, newNode])
    if (options?.parentId) {
      setEdges(eds => [...eds, {
        id: `edge-${options.parentId}-${id}`, source: options.parentId, target: id,
        animated: true, style: { stroke: '#06b6d4', strokeWidth: 2 },
        label: (options.branchContext || '').slice(0, 30) + '...',
        labelStyle: { fontSize: 9, fill: '#64748b' },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
        labelBgPadding: [4, 4] as [number, number], labelBgBorderRadius: 4,
      }])
    }
  }, [nodes, setNodes, setEdges])

  const handleBranch = useCallback((parentNodeId: string, messageContent: string) => {
    addNode({ parentId: parentNodeId, branchContext: messageContent })
  }, [addNode])

  const handleClose = useCallback((nodeId: string) => {
    setNodes(nds => nds.filter(n => n.id !== nodeId))
    setEdges(eds => eds.filter(e => e.source !== nodeId && e.target !== nodeId))
  }, [setNodes, setEdges])

  const handleTitleUpdate = useCallback((nodeId: string, newTitle: string) => {
    setNodes(nds => nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, title: newTitle } } : n))
  }, [setNodes])

  const handleConversationUpdate = useCallback((nodeId: string, convoId: string) => {
    setNodes(nds => nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, conversationId: convoId } } : n))
  }, [setNodes])

  // ─── Drag to resize panels ───
  function startDragLeft(e: React.MouseEvent) {
    e.preventDefault()
    const startX = e.clientX
    const startW = leftWidth
    function onMove(ev: MouseEvent) { setLeftWidth(Math.max(150, Math.min(400, startW + ev.clientX - startX))) }
    function onUp() { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }
  function startDragRight(e: React.MouseEvent) {
    e.preventDefault()
    const startX = e.clientX
    const startW = rightWidth
    function onMove(ev: MouseEvent) { setRightWidth(Math.max(150, Math.min(400, startW - (ev.clientX - startX)))) }
    function onUp() { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return (
    <>
    <div className="h-screen flex flex-col bg-[var(--color-cryo-bg)]">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-cryo-border)] bg-[var(--color-cryo-surface)]">
        <div className="flex items-center gap-3">
          <Dna className="w-5 h-5 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
          <span className="text-sm font-mono font-bold tracking-widest text-[var(--color-cryo-accent)]">CRYO</span>
          <span className="text-xs text-[var(--color-cryo-text-muted)]">Research Workspace</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => addNode()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-cryo-accent)]/10 border border-[var(--color-cryo-accent)]/30 text-[var(--color-cryo-accent)] text-xs font-medium hover:bg-[var(--color-cryo-accent)]/20 transition-colors">
            <Plus className="w-3.5 h-3.5" /> New Node
          </button>
          <button onClick={() => navigate('/')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[var(--color-cryo-text-muted)] text-xs border border-[var(--color-cryo-border)] hover:border-[var(--color-cryo-border-bright)] transition-colors">
            <MessageSquare className="w-3.5 h-3.5" /> Chat View
          </button>
          <span className="text-xs text-[var(--color-cryo-text-muted)] font-mono">{user.username}</span>
          <button onClick={onLogout} className="text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-red)]"><LogOut className="w-3.5 h-3.5" /></button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">

      {/* ─── LEFT PANEL ─── */}
      {leftOpen ? (
        <div className="flex flex-shrink-0" style={{ width: leftWidth }}>
          <div className="flex-1 bg-[var(--color-cryo-surface)] border-r border-[var(--color-cryo-border)] flex flex-col overflow-hidden">
            <div className="p-3 border-b border-[var(--color-cryo-border)] flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="text-[9px] uppercase tracking-widest text-[var(--color-cryo-text-muted)]">Workspace</div>
                {editingName ? (
                  <input autoFocus value={wsName}
                    onChange={e => setWsName(e.target.value)}
                    onBlur={() => { setEditingName(false); if (activeWsId) wsApi.rename(activeWsId, wsName).catch(console.error) }}
                    onKeyDown={e => { if (e.key === 'Enter') { setEditingName(false); if (activeWsId) wsApi.rename(activeWsId, wsName).catch(console.error) } }}
                    className="text-xs text-[var(--color-cryo-text)] font-medium mt-0.5 bg-transparent border-b border-[var(--color-cryo-accent)] outline-none w-full" />
                ) : (
                  <div className="text-xs text-[var(--color-cryo-text)] font-medium mt-0.5 cursor-pointer truncate" onClick={() => setEditingName(true)}>{wsName}</div>
                )}
              </div>
              <button onClick={() => setLeftOpen(false)} className="text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text-dim)] ml-2"><PanelLeftClose className="w-3.5 h-3.5" /></button>
            </div>

            <div className="p-3 border-b border-[var(--color-cryo-border)]">
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="bg-[var(--color-cryo-surface-2)] rounded-md py-1.5">
                  <div className="text-sm font-bold text-[var(--color-cryo-accent)]">{nodes.length}</div>
                  <div className="text-[8px] text-[var(--color-cryo-text-muted)] uppercase">Nodes</div>
                </div>
                <div className="bg-[var(--color-cryo-surface-2)] rounded-md py-1.5">
                  <div className="text-sm font-bold text-[var(--color-cryo-cyan)]">{edges.length}</div>
                  <div className="text-[8px] text-[var(--color-cryo-text-muted)] uppercase">Links</div>
                </div>
              </div>
            </div>

            {/* Workspace list */}
            <div className="flex-1 overflow-y-auto">
              <div className="px-3 pt-2 pb-1 text-[9px] uppercase tracking-widest text-[var(--color-cryo-text-muted)]">Workspaces</div>
              <div className="px-2">
                {workspaces.map(w => (
                  <div key={w.id} className={`group flex items-center rounded-md mb-0.5 transition-colors ${w.id === activeWsId ? 'bg-[var(--color-cryo-accent)]/10 border-l-2 border-[var(--color-cryo-accent)]' : 'hover:bg-[var(--color-cryo-surface-2)]'}`}>
                    <button onClick={() => { if (w.id !== activeWsId) { setLoaded(false); loadWorkspace(w.id, w.name) } }}
                      className="flex-1 text-left px-2 py-2 text-xs text-[var(--color-cryo-text-dim)] flex items-center gap-2 truncate">
                      <Dna className="w-3 h-3 flex-shrink-0 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
                      <span className="truncate">{w.name}</span>
                    </button>
                    <div className="relative">
                      <button onClick={() => setMenuOpenId(menuOpenId === w.id ? null : w.id)}
                        className="p-1 opacity-0 group-hover:opacity-100 text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text)]">
                        <MoreVertical className="w-3 h-3" />
                      </button>
                      {menuOpenId === w.id && (
                        <div className="absolute right-0 top-6 z-50 bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] rounded-md shadow-lg py-1 min-w-[100px]">
                          <button onClick={() => {
                            wsApi.remove(w.id).then(() => {
                              setWorkspaces(prev => prev.filter(ws => ws.id !== w.id))
                              if (w.id === activeWsId && workspaces.length > 1) {
                                const next = workspaces.find(ws => ws.id !== w.id)
                                if (next) loadWorkspace(next.id, next.name)
                              }
                              setMenuOpenId(null)
                            })
                          }} className="w-full text-left px-3 py-1.5 text-xs text-[var(--color-cryo-red)] hover:bg-[var(--color-cryo-surface-3)] flex items-center gap-2">
                            <Trash2 className="w-3 h-3" /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <button onClick={() => {
                  wsApi.create().then((ws: any) => {
                    setWorkspaces(prev => [...prev, ws])
                    setLoaded(false)
                    loadWorkspace(ws.id, ws.name)
                  }).catch((e: any) => alert(e.message))
                }} className="w-full text-left px-2 py-2 rounded-md text-xs text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-accent)] hover:bg-[var(--color-cryo-surface-2)] flex items-center gap-2">
                  <Plus className="w-3 h-3" /> New Workspace
                </button>
              </div>
            </div>

            <div className="p-2 border-t border-[var(--color-cryo-border)]">
              <button onClick={() => navigate('/')} className="w-full flex items-center justify-center gap-1.5 px-2 py-1 rounded-md text-[10px] text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text-dim)]">
                <MessageSquare className="w-3 h-3" /> Chat View
              </button>
            </div>
          </div>
          {/* Drag handle */}
          <div onMouseDown={startDragLeft} className="w-1 cursor-col-resize hover:bg-[var(--color-cryo-accent)]/20 transition-colors" />
        </div>
      ) : (
        <div className="flex flex-col items-center py-3 gap-3 w-10 bg-[var(--color-cryo-surface)] border-r border-[var(--color-cryo-border)]">
          <button onClick={() => setLeftOpen(true)} className="text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-accent)]"><PanelLeftOpen className="w-4 h-4" /></button>
          <button onClick={() => addNode()} className="text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-accent)]" title="Add Node"><Plus className="w-4 h-4" /></button>
        </div>
      )}

      {/* ─── CANVAS ─── */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes} edges={edges}
          onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
          nodeTypes={nodeTypes} fitView minZoom={0.2} maxZoom={2}
          nodesDraggable nodesConnectable={false} elementsSelectable selectNodesOnDrag={false}
          panOnDrag={[1, 2]} selectionOnDrag={false}
          defaultEdgeOptions={{ animated: true, style: { stroke: '#06b6d4', strokeWidth: 2 } }}
          proOptions={{ hideAttribution: true }}
        >
          <Controls className="!bg-[var(--color-cryo-surface)] !border-[var(--color-cryo-border)] !shadow-lg [&_button]:!bg-[var(--color-cryo-surface-2)] [&_button]:!border-[var(--color-cryo-border)] [&_button]:!text-[var(--color-cryo-text-dim)] [&_button:hover]:!bg-[var(--color-cryo-surface-3)]" />
          <MiniMap className="!bg-[var(--color-cryo-surface)]" nodeColor="#1e293b" maskColor="rgba(10,14,20,0.7)" />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e293b" />
        </ReactFlow>
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center pointer-events-auto">
              <Dna className="w-16 h-16 text-[var(--color-cryo-accent)] mx-auto mb-4 opacity-20" strokeWidth={1} />
              <h2 className="text-xl font-light text-[var(--color-cryo-text)] mb-2">Research Workspace</h2>
              <p className="text-sm text-[var(--color-cryo-text-dim)] mb-6 max-w-sm">Create research nodes, branch from discoveries, build your knowledge tree.</p>
              <button onClick={() => addNode()} className="px-5 py-2.5 rounded-lg bg-[var(--color-cryo-accent)] text-[var(--color-cryo-bg)] font-semibold text-sm hover:brightness-110 transition-all">
                <Plus className="w-4 h-4 inline mr-2" />Start Research
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ─── RIGHT PANEL ─── */}
      {rightOpen ? (
        <div className="flex flex-shrink-0" style={{ width: rightWidth }}>
          <div onMouseDown={startDragRight} className="w-1 cursor-col-resize hover:bg-[var(--color-cryo-accent)]/20 transition-colors" />
          <div className="flex-1 bg-[var(--color-cryo-surface)] border-l border-[var(--color-cryo-border)] flex flex-col overflow-hidden">
            <div className="p-3 border-b border-[var(--color-cryo-border)] flex items-center justify-between">
              <div className="text-[9px] uppercase tracking-widest text-[var(--color-cryo-text-muted)]">Nodes ({nodes.length})</div>
              <button onClick={() => setRightOpen(false)} className="text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-text-dim)]"><PanelRightClose className="w-3.5 h-3.5" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {nodes.map(n => {
                const nd = n.data as any
                const hasChildren = edges.some(e => e.source === n.id)
                const hasParent = edges.some(e => e.target === n.id)
                return (
                  <button key={n.id} onClick={() => document.querySelector(`[data-id="${n.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
                    className="w-full text-left px-2 py-2 rounded-md mb-1 hover:bg-[var(--color-cryo-surface-2)] transition-colors">
                    <div className="flex items-center gap-2">
                      {hasParent ? <BranchIcon className="w-3 h-3 text-[var(--color-cryo-purple)] flex-shrink-0" /> : <Dna className="w-3 h-3 text-[var(--color-cryo-accent)] flex-shrink-0" strokeWidth={1.5} />}
                      <span className="text-xs text-[var(--color-cryo-text)] truncate flex-1">{nd?.title || 'New Research'}</span>
                    </div>
                    {hasChildren && <div className="text-[9px] text-[var(--color-cryo-purple)] ml-5 mt-0.5">has branches</div>}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center py-3 w-10 bg-[var(--color-cryo-surface)] border-l border-[var(--color-cryo-border)]">
          <button onClick={() => setRightOpen(true)} className="text-[var(--color-cryo-text-muted)] hover:text-[var(--color-cryo-accent)]"><PanelRightOpen className="w-4 h-4" /></button>
        </div>
      )}

      </div>
    </div>

    {reportPanel && (
      <ReportPanel
        url={reportPanel.url}
        filename={reportPanel.filename}
        onClose={() => setReportPanel(null)}
      />
    )}
    </>
  )
}
