import { useState, useMemo } from 'react'
import {
  BarChart3,
  TrendingUp,
  Clock,
  AlertTriangle,
  Phone,
  Target,
  Zap,
  Activity,
} from 'lucide-react'
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'
import { cn, formatDuration } from '@/lib/utils'
import { generateMockAnalytics } from '@/lib/mockData'

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4']

export default function AnalyticsView() {
  const [timeRange, setTimeRange] = useState<'7' | '14' | '30'>('30')
  const analytics = useMemo(() => generateMockAnalytics(), [])

  const dailyData = useMemo(() => {
    const days = parseInt(timeRange)
    return analytics.daily.slice(-days).map(d => ({
      ...d,
      date: new Date(d.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
      avg_duration_min: Math.round(d.avg_duration / 60 * 10) / 10,
    }))
  }, [analytics.daily, timeRange])

  const summary = analytics.summary

  return (
    <div className="p-6 space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Total Calls</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{summary.total_calls}</p>
            </div>
            <div className="w-11 h-11 rounded-xl bg-indigo-50 flex items-center justify-center">
              <Phone className="w-5 h-5 text-indigo-600" />
            </div>
          </div>
          <div className="mt-3 flex items-center gap-1 text-xs text-emerald-600">
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="font-medium">+12%</span>
            <span className="text-slate-400">vs last period</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Conversion Rate</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{summary.conversion_rate}%</p>
            </div>
            <div className="w-11 h-11 rounded-xl bg-emerald-50 flex items-center justify-center">
              <Target className="w-5 h-5 text-emerald-600" />
            </div>
          </div>
          <div className="mt-3 w-full bg-slate-100 rounded-full h-1.5">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all"
              style={{ width: `${summary.conversion_rate}%` }}
            />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Avg Duration</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{formatDuration(summary.avg_duration)}</p>
            </div>
            <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center">
              <Clock className="w-5 h-5 text-blue-600" />
            </div>
          </div>
          <div className="mt-3 text-xs text-slate-400">
            Per completed call
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">Top Objection</p>
              <p className="text-lg font-bold text-slate-900 mt-1 truncate">{summary.top_objection}</p>
            </div>
            <div className="w-11 h-11 rounded-xl bg-amber-50 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
            </div>
          </div>
          <div className="mt-3 text-xs text-slate-400">
            Most frequent blocker
          </div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calls Per Day - Line Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <Activity className="w-4 h-4 text-indigo-500" />
              Calls Per Day
            </h3>
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              {(['7', '14', '30'] as const).map(r => (
                <button
                  key={r}
                  onClick={() => setTimeRange(r)}
                  className={cn(
                    'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                    timeRange === r
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  )}
                >
                  {r}D
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={dailyData}>
              <defs>
                <linearGradient id="colorCalls" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
              />
              <Area type="monotone" dataKey="total_calls" stroke="#6366f1" strokeWidth={2} fill="url(#colorCalls)" name="Total Calls" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Outcome Distribution - Pie Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-500" />
            Outcome Distribution
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={[
                  { name: 'Booked', value: analytics.daily.reduce((s, d) => s + d.booked, 0) },
                  { name: 'Declined', value: analytics.daily.reduce((s, d) => s + d.declined, 0) },
                  { name: 'Handoff', value: analytics.daily.reduce((s, d) => s + d.handoff, 0) },
                  { name: 'Dropped', value: analytics.daily.reduce((s, d) => s + d.dropped, 0) },
                ]}
                cx="50%"
                cy="50%"
                innerRadius={45}
                outerRadius={75}
                paddingAngle={3}
                dataKey="value"
              >
                {COLORS.slice(0, 4).map((color, i) => (
                  <Cell key={i} fill={color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-x-4 gap-y-1 justify-center mt-2">
            {['Booked', 'Declined', 'Handoff', 'Dropped'].map((label, i) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i] }} />
                <span className="text-[11px] text-slate-500">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Objections - Bar Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            Top Objections
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={analytics.objections} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} width={140} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="count" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Occurrences" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* LLM Response Time - Area Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-500" />
            LLM Response Time (ms)
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={dailyData}>
              <defs>
                <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} domain={['dataMin - 20', 'dataMax + 20']} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
              <Area type="monotone" dataKey="avg_latency_ms" stroke="#10b981" strokeWidth={2} fill="url(#colorLatency)" name="Avg Latency (ms)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Provider Usage */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4 text-violet-500" />
          LLM Provider Usage
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {analytics.provider_usage.map((p, i) => (
            <div key={p.provider} className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i] }} />
              <div>
                <p className="text-xs font-medium text-slate-700">{p.provider}</p>
                <p className="text-lg font-bold text-slate-900">{p.count}</p>
                <p className="text-[10px] text-slate-400">
                  {Math.round((p.count / analytics.provider_usage.reduce((s, x) => s + x.count, 0)) * 100)}% of total
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
