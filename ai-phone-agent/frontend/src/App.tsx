import { useState, useCallback, useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from '@/components/Sidebar'
import Header from '@/components/Header'
import LiveCallsView from '@/views/LiveCallsView'
import HistoryView from '@/views/HistoryView'
import AnalyticsView from '@/views/AnalyticsView'
import SettingsView from '@/views/SettingsView'
import { mockHealth } from '@/lib/mockData'
import type { HealthStatus } from '@/types'

export type NavView = 'live' | 'history' | 'analytics' | 'settings'

const viewTitles: Record<NavView, string> = {
  live: 'Live Calls',
  history: 'Call History',
  analytics: 'Analytics',
  settings: 'Settings',
}

const viewPaths: Record<NavView, string> = {
  live: '/live',
  history: '/history',
  analytics: '/analytics',
  settings: '/settings',
}

function Dashboard() {
  const [activeView, setActiveView] = useState<NavView>('live')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [isMock, setIsMock] = useState(false)

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/health', { signal: AbortSignal.timeout(3000) })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json() as HealthStatus
      setHealth(data)
      setIsMock(false)
    } catch {
      setHealth(mockHealth)
      setIsMock(true)
    }
    setLastRefresh(new Date())
  }, [])

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 5000)
    return () => clearInterval(interval)
  }, [fetchHealth])

  const handleNavigate = useCallback((view: NavView) => {
    setActiveView(view)
    window.location.hash = viewPaths[view]
  }, [])

  // Sync active view with hash
  useEffect(() => {
    const sync = () => {
      const hash = window.location.hash.replace('#', '')
      for (const [view, path] of Object.entries(viewPaths)) {
        if (path === hash) {
          setActiveView(view as NavView)
          return
        }
      }
    }
    sync()
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  return (
    <div className="min-h-[100dvh] bg-[#f8fafc]">
      {/* Sidebar */}
      <Sidebar activeView={activeView} onNavigate={handleNavigate} />

      {/* Main content */}
      <main className="lg:ml-64 transition-all duration-300">
        <Header
          title={viewTitles[activeView]}
          health={health}
          lastRefresh={lastRefresh}
          onRefresh={fetchHealth}
          isMock={isMock}
        />

        <div className="min-h-[calc(100dvh-64px)]">
          <Routes>
            <Route path="/live" element={<LiveCallsView />} />
            <Route path="/history" element={<HistoryView />} />
            <Route path="/analytics" element={<AnalyticsView />} />
            <Route path="/settings" element={<SettingsView />} />
            <Route path="/" element={<Navigate to="/live" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <Dashboard />
    </HashRouter>
  )
}
