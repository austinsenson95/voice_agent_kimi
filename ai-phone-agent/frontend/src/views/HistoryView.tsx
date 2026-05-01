import { useState, useMemo, useCallback } from 'react'
import {
  Search,
  Download,
  ChevronLeft,
  ChevronRight,
  Filter,
  Headphones,
  Phone,
  Calendar,
  X,
} from 'lucide-react'
import { cn, formatDuration, formatPhone, formatTimestamp } from '@/lib/utils'
import { generateMockHistory } from '@/lib/mockData'
import type { CallSession, CallOutcome } from '@/types'

const PAGE_SIZE = 5

type DateFilter = 'all' | 'today' | 'week' | 'month'

export default function HistoryView() {
  const [history] = useState<CallSession[]>(generateMockHistory())
  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState<DateFilter>('all')
  const [outcomeFilter, setOutcomeFilter] = useState<CallOutcome | 'all'>('all')
  const [page, setPage] = useState(0)
  const [expandedSid, setExpandedSid] = useState<string | null>(null)

  const filtered = useMemo(() => {
    let result = [...history]

    // Search
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.phone_number.toLowerCase().includes(q) ||
        c.state.toLowerCase().includes(q) ||
        c.outcome.toLowerCase().includes(q)
      )
    }

    // Date filter
    const now = Date.now()
    if (dateFilter === 'today') {
      result = result.filter(c => now - new Date(c.started_at).getTime() < 86400000)
    } else if (dateFilter === 'week') {
      result = result.filter(c => now - new Date(c.started_at).getTime() < 604800000)
    } else if (dateFilter === 'month') {
      result = result.filter(c => now - new Date(c.started_at).getTime() < 2592000000)
    }

    // Outcome filter
    if (outcomeFilter !== 'all') {
      result = result.filter(c => c.outcome === outcomeFilter)
    }

    return result
  }, [history, search, dateFilter, outcomeFilter])

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE)
  const pageData = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const handleExport = useCallback(() => {
    const rows = filtered.map(c => ({
      'Phone': c.phone_number,
      'Date': new Date(c.started_at).toLocaleDateString('en-IN'),
      'Duration (s)': String(c.duration_seconds),
      'State': c.state,
      'Outcome': c.outcome,
      'Provider': c.llm_provider,
    }))
    if (rows.length === 0) return
    const headers = Object.keys(rows[0])
    const csv = [
      headers.join(','),
      ...rows.map(r => headers.map(h => `"${r[h as keyof typeof r].replace(/"/g, '\\"')}"`).join(',')),
    ].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `call-history-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [filtered])

  const outcomeColors: Record<string, string> = {
    booked: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    declined: 'bg-rose-50 text-rose-700 border-rose-200',
    handoff: 'bg-blue-50 text-blue-700 border-blue-200',
    dropped: 'bg-slate-50 text-slate-600 border-slate-200',
    in_progress: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  }

  return (
    <div className="p-6 space-y-6">
      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by phone, state, or outcome..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0) }}
              className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            {search && (
              <button onClick={() => { setSearch(''); setPage(0) }} className="absolute right-3 top-1/2 -translate-y-1/2">
                <X className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600" />
              </button>
            )}
          </div>

          {/* Date filter */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-400" />
            {(['all', 'today', 'week', 'month'] as DateFilter[]).map(f => (
              <button
                key={f}
                onClick={() => { setDateFilter(f); setPage(0) }}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize',
                  dateFilter === f
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'
                )}
              >
                {f === 'all' ? 'All Time' : f}
              </button>
            ))}
          </div>

          {/* Export */}
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-medium hover:bg-indigo-100 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>

        {/* Outcome filter pills */}
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          {(['all', 'booked', 'declined', 'handoff', 'dropped'] as const).map(o => (
            <button
              key={o}
              onClick={() => { setOutcomeFilter(o); setPage(0) }}
              className={cn(
                'px-2.5 py-1 rounded-full text-xs font-medium transition-colors capitalize',
                outcomeFilter === o
                  ? 'bg-slate-800 text-white'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              )}
            >
              {o}
            </button>
          ))}
          <span className="ml-auto text-xs text-slate-400">
            {filtered.length} result{filtered.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Phone</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Date</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Duration</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">State</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Outcome</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Recording</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Provider</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pageData.map(call => (
                <>
                  <tr
                    key={call.call_sid}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => setExpandedSid(expandedSid === call.call_sid ? null : call.call_sid)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Phone className="w-3.5 h-3.5 text-slate-400" />
                        <span className="font-mono text-xs">{formatPhone(call.phone_number)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {new Date(call.started_at).toLocaleDateString('en-IN')}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-600">
                      {formatDuration(call.duration_seconds)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="capitalize text-slate-600">{call.state}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'px-2 py-0.5 rounded-full text-xs font-medium border capitalize',
                        outcomeColors[call.outcome] || 'bg-slate-50 text-slate-600'
                      )}>
                        {call.outcome.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {call.recording_url ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            window.open(call.recording_url, '_blank')
                          }}
                          className="p-1 rounded text-indigo-600 hover:bg-indigo-50 transition-colors"
                        >
                          <Headphones className="w-4 h-4" />
                        </button>
                      ) : (
                        <span className="text-xs text-slate-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500 capitalize">{call.llm_provider}</span>
                    </td>
                  </tr>
                  {/* Expanded transcript */}
                  {expandedSid === call.call_sid && (
                    <tr>
                      <td colSpan={7} className="px-4 py-4 bg-slate-50/50">
                        <div className="max-h-64 overflow-y-auto custom-scrollbar space-y-2">
                          <h4 className="text-xs font-semibold text-slate-500 mb-2">Transcript</h4>
                          {call.transcript.map((turn, i) => (
                            <div key={i} className={cn('flex', turn.speaker === 'user' ? 'justify-start' : 'justify-end')}>
                              <div className={cn(
                                'max-w-[90%] rounded-lg px-3 py-2 text-xs',
                                turn.speaker === 'user'
                                  ? 'bg-white border border-slate-200 text-slate-700'
                                  : 'bg-indigo-600 text-white'
                              )}>
                                <div className="flex items-center gap-1.5 mb-0.5">
                                  <span className={cn('text-[10px] font-medium', turn.speaker === 'user' ? 'text-slate-400' : 'text-indigo-200')}>
                                    {turn.speaker === 'user' ? 'Caller' : 'AI'}
                                  </span>
                                  <span className={cn('text-[10px]', turn.speaker === 'user' ? 'text-slate-300' : 'text-indigo-300')}>
                                    {formatTimestamp(turn.timestamp)}
                                  </span>
                                </div>
                                {turn.text}
                                {turn.state && (
                                  <span className={cn(
                                    'inline-block ml-2 px-1 rounded text-[10px]',
                                    turn.speaker === 'user' ? 'bg-slate-100 text-slate-500' : 'bg-indigo-500/50 text-indigo-100'
                                  )}>
                                    {turn.state}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
              {pageData.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-400">
                    No calls found matching your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pageCount > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 bg-slate-50">
            <span className="text-xs text-slate-500">
              Page {page + 1} of {pageCount}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              {Array.from({ length: pageCount }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setPage(i)}
                  className={cn(
                    'w-7 h-7 rounded-lg text-xs font-medium transition-colors',
                    page === i
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-500 hover:bg-slate-200'
                  )}
                >
                  {i + 1}
                </button>
              ))}
              <button
                onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))}
                disabled={page === pageCount - 1}
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200 disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
