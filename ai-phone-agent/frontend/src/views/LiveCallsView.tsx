import { useState, useEffect, useCallback } from 'react'
import { Phone, Clock, Volume2, Play, Pause, PhoneOff } from 'lucide-react'
import { cn, formatDuration } from '@/lib/utils'
import { mockActiveCalls } from '@/lib/mockData'
import type { CallSession } from '@/types'
import CallCard from '@/components/CallCard'

export default function LiveCallsView() {
  const [calls, setCalls] = useState<Record<string, CallSession>>(mockActiveCalls)
  const [loading, setLoading] = useState(true)
  const [soundEnabled, setSoundEnabled] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCalls = useCallback(async () => {
    try {
      const res = await fetch('/api/calls')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      // Filter only active calls
      const active: Record<string, CallSession> = {}
      for (const [sid, call] of Object.entries(data)) {
        const c = call as CallSession
        if (c.outcome === 'in_progress') {
          active[sid] = c
        }
      }
      // Only update if we got real data, otherwise keep mocks
      if (Object.keys(active).length > 0) {
        setCalls(active)
        setError(null)
      }
    } catch {
      // Keep mock data on error
      setError('API unavailable - showing demo data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCalls()
    const interval = setInterval(fetchCalls, 5000)
    return () => clearInterval(interval)
  }, [fetchCalls])

  // Sound notification for new calls
  useEffect(() => {
    if (!soundEnabled) return
    const activeCount = Object.keys(calls).length
    if (activeCount > 0) {
      const audio = new Audio()
      audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIG2m98OScTgwOUarm7blmFgU7k9n1unEiBC13yO/eizEIHWq+8+OWT'
      audio.volume = 0.3
      audio.play().catch(() => {})
    }
  }, [soundEnabled])

  const activeCallsList = Object.values(calls)
  const totalToday = 12 // Mock stat
  const avgDuration = activeCallsList.length > 0
    ? Math.round(activeCallsList.reduce((s, c) => s + c.duration_seconds, 0) / activeCallsList.length)
    : 0

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 bg-white rounded-xl border border-slate-200 animate-pulse" />
          ))}
        </div>
        <div className="h-64 bg-white rounded-xl border border-slate-200 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm">
          <PhoneOff className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Stats Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Active Calls</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                {activeCallsList.length}
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center">
              <Phone className="w-5 h-5 text-emerald-600" />
            </div>
          </div>
          {activeCallsList.length > 0 && (
            <div className="mt-2 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-emerald-600 font-medium">
                {activeCallsList.length} call{activeCallsList.length !== 1 ? 's' : ''} in progress
              </span>
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Avg Duration</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                {formatDuration(avgDuration)}
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center">
              <Clock className="w-5 h-5 text-indigo-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Total Today</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{totalToday}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <Play className="w-5 h-5 text-blue-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Sound toggle */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">
          {activeCallsList.length > 0 ? 'Live Call Monitoring' : 'No Active Calls'}
        </h3>
        <button
          onClick={() => setSoundEnabled(!soundEnabled)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            soundEnabled
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-slate-100 text-slate-500 border border-slate-200'
          )}
        >
          {soundEnabled ? (
            <>
              <Volume2 className="w-3.5 h-3.5" />
              Sound On
            </>
          ) : (
            <>
              <Pause className="w-3.5 h-3.5" />
              Sound Off
            </>
          )}
        </button>
      </div>

      {/* Call Cards Grid */}
      {activeCallsList.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
            <Phone className="w-8 h-8 text-slate-300" />
          </div>
          <h3 className="text-lg font-semibold text-slate-700">No Active Calls</h3>
          <p className="text-sm text-slate-400 mt-1">
            Calls will appear here when they come in. The page refreshes automatically every 5 seconds.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {activeCallsList.map((call) => (
            <CallCard key={call.call_sid} call={call} isLive />
          ))}
        </div>
      )}
    </div>
  )
}
