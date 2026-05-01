import { useState, useEffect, useRef } from 'react'
import {
  Phone,
  Clock,
  ChevronDown,
  ChevronUp,
  Headphones,
  Bot,
  User,
} from 'lucide-react'
import { cn, formatDuration, formatPhone, formatTimestamp } from '@/lib/utils'
import type { CallSession, CallState } from '@/types'

interface CallCardProps {
  call: CallSession
  isLive?: boolean
}

const stateColors: Record<CallState, { bg: string; text: string; border: string; dot: string }> = {
  opening: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', dot: 'bg-blue-500' },
  discovery: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200', dot: 'bg-purple-500' },
  pitch: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', dot: 'bg-indigo-500' },
  objection: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', dot: 'bg-amber-500' },
  close: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', dot: 'bg-emerald-500' },
  ended: { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200', dot: 'bg-slate-400' },
}

export default function CallCard({ call, isLive = false }: CallCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [liveDuration, setLiveDuration] = useState(call.duration_seconds)
  const scrollRef = useRef<HTMLDivElement>(null)

  const colors = stateColors[call.state]

  // Live timer for active calls
  useEffect(() => {
    if (!isLive || call.state === 'ended') return
    setLiveDuration(call.duration_seconds)
    const interval = setInterval(() => {
      setLiveDuration(d => d + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [isLive, call.state, call.duration_seconds])

  // Auto-scroll transcript for live calls
  useEffect(() => {
    if (isLive && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [call.transcript.length, isLive])

  const handleListen = () => {
    if (call.recording_url) {
      window.open(call.recording_url, '_blank')
    }
  }

  return (
    <div className={cn(
      'bg-white rounded-xl border shadow-sm transition-all duration-200 overflow-hidden',
      isLive ? 'border-indigo-200 shadow-indigo-100' : 'border-slate-200'
    )}>
      {/* Card Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
              <Phone className="w-4 h-4 text-slate-600" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate">
                {formatPhone(call.phone_number)}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={cn(
                  'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border',
                  colors.bg, colors.text, colors.border
                )}>
                  {isLive && call.state !== 'ended' && (
                    <span className={cn('w-1.5 h-1.5 rounded-full animate-pulse', colors.dot)} />
                  )}
                  {call.state.charAt(0).toUpperCase() + call.state.slice(1)}
                </span>
                <span className="text-xs text-slate-400">
                  {call.llm_provider}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Duration */}
            <div className="flex items-center gap-1 text-xs text-slate-500 bg-slate-50 px-2 py-1 rounded-md">
              <Clock className="w-3 h-3" />
              <span className="font-mono">{formatDuration(liveDuration)}</span>
            </div>

            {/* Listen button */}
            {call.recording_url && (
              <button
                onClick={handleListen}
                className="p-1.5 rounded-md text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                title="Listen to recording"
              >
                <Headphones className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Last message preview */}
        {call.last_ai_message && (
          <p className="mt-3 text-xs text-slate-500 line-clamp-2 bg-slate-50 rounded-lg px-3 py-2">
            <Bot className="w-3 h-3 inline mr-1 text-indigo-500" />
            {call.last_ai_message}
          </p>
        )}

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 font-medium transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-3.5 h-3.5" />
              Hide transcript
            </>
          ) : (
            <>
              <ChevronDown className="w-3.5 h-3.5" />
              View transcript ({call.transcript.length} messages)
            </>
          )}
        </button>
      </div>

      {/* Expanded Transcript */}
      {expanded && (
        <div
          ref={scrollRef}
          className="border-t border-slate-100 bg-slate-50/50 max-h-80 overflow-y-auto custom-scrollbar"
        >
          <div className="p-4 space-y-3">
            {call.transcript.map((turn, i) => (
              <div key={i} className={cn('flex', turn.speaker === 'user' ? 'justify-start' : 'justify-end')}>
                <div className={cn(
                  'max-w-[85%] rounded-xl px-3 py-2',
                  turn.speaker === 'user'
                    ? 'bg-white border border-slate-200 text-slate-700'
                    : 'bg-indigo-600 text-white'
                )}>
                  <div className="flex items-center gap-1.5 mb-1">
                    {turn.speaker === 'user' ? (
                      <User className="w-3 h-3 text-slate-400" />
                    ) : (
                      <Bot className="w-3 h-3 text-indigo-200" />
                    )}
                    <span className={cn('text-[10px] font-medium', turn.speaker === 'user' ? 'text-slate-400' : 'text-indigo-200')}>
                      {turn.speaker === 'user' ? 'Caller' : 'AI Agent'}
                    </span>
                    <span className={cn('text-[10px]', turn.speaker === 'user' ? 'text-slate-300' : 'text-indigo-300')}>
                      {formatTimestamp(turn.timestamp)}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed">{turn.text}</p>
                  {turn.state && (
                    <span className={cn(
                      'inline-block mt-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium',
                      turn.speaker === 'user'
                        ? 'bg-slate-100 text-slate-500'
                        : 'bg-indigo-500/50 text-indigo-100'
                    )}>
                      {turn.state}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
