import { useEffect, useState } from 'react'
import { Wifi, WifiOff, Zap, RefreshCw } from 'lucide-react'
import { cn, formatTimestamp } from '@/lib/utils'
import type { HealthStatus } from '@/types'

interface HeaderProps {
  title: string
  health: HealthStatus | null
  lastRefresh: Date | null
  onRefresh: () => void
  isMock: boolean
}

export default function Header({ title, health, lastRefresh, onRefresh, isMock }: HeaderProps) {
  const [isOnline, setIsOnline] = useState(true)
  const [spinning, setSpinning] = useState(false)

  useEffect(() => {
    const check = () => setIsOnline(navigator.onLine)
    window.addEventListener('online', check)
    window.addEventListener('offline', check)
    return () => {
      window.removeEventListener('online', check)
      window.removeEventListener('offline', check)
    }
  }, [])

  const handleRefresh = () => {
    setSpinning(true)
    onRefresh()
    setTimeout(() => setSpinning(false), 1000)
  }

  const connected = isOnline && health?.status === 'ok'

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-30">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {isMock && (
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium border border-amber-200">
            Demo Mode
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* LLM Provider Badge */}
        {health?.current_provider && (
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100">
            <Zap className="w-3.5 h-3.5 text-indigo-600" />
            <span className="text-xs font-medium text-indigo-700 capitalize">
              {health.current_provider}
            </span>
          </div>
        )}

        {/* Connection Status */}
        <div className="flex items-center gap-2">
          {connected ? (
            <Wifi className="w-4 h-4 text-emerald-500" />
          ) : (
            <WifiOff className="w-4 h-4 text-rose-500" />
          )}
          <div className={cn('w-2 h-2 rounded-full', connected ? 'bg-emerald-500' : 'bg-rose-500')} />
          <span className="text-xs text-slate-500 hidden sm:inline">
            {connected ? 'Connected' : 'Offline'}
          </span>
        </div>

        {/* Last Refresh */}
        {lastRefresh && (
          <span className="text-xs text-slate-400 hidden md:inline">
            {formatTimestamp(lastRefresh.toISOString())}
          </span>
        )}

        {/* Refresh Button */}
        <button
          onClick={handleRefresh}
          className={cn(
            'p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-all',
            spinning && 'animate-spin'
          )}
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
