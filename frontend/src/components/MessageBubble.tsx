/**
 * MessageBubble — wrapper for ChatPage that uses the shared ChatMessage component.
 * Adds the outer bubble styling (alignment, max-width, background).
 */

import ChatMessage, { type ChatMsg } from './ChatMessage'
import { Wrench } from 'lucide-react'

interface Props {
  message: ChatMsg
  bionicMode?: boolean
}

export default function MessageBubble({ message, bionicMode = false }: Props) {
  const isUser = message.role === 'user'

  if (message.role === 'tool') {
    return (
      <div className="tool-indicator rounded-lg px-4 py-2 mx-4 my-1 text-xs font-mono text-[var(--color-cryo-text-dim)]">
        <Wrench className="w-3 h-3 inline mr-2 text-[var(--color-cryo-purple)]" />
        Tool execution
      </div>
    )
  }

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`
        max-w-[80%] rounded-xl px-5 py-3.5
        ${isUser ? 'msg-user' : 'msg-assistant'}
      `}>
        <ChatMessage message={message} />
      </div>
    </div>
  )
}
