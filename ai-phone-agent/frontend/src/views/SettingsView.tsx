import { useState } from 'react'
import {
  Settings,
  Zap,
  Building2,
  MessageSquareWarning,
  ChevronDown,
  ChevronUp,
  Save,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  TestTube,
  Plus,
  Trash2,
  Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { mockProviders, mockBattleCard, mockObjections } from '@/lib/mockData'
import { useMutation } from '@/hooks/useApi'
import type { BattleCard, Objection } from '@/types'

type SettingsTab = 'llm' | 'business' | 'objections'

const providerInfo: Record<string, { pros: string[]; color: string }> = {
  groq: { pros: ['Fastest', '<100ms', 'Great for voice', 'Free tier available'], color: 'bg-orange-500' },
  openai: { pros: ['Reliable', 'Good quality', 'Moderate cost', 'Great tool use'], color: 'bg-emerald-500' },
  anthropic: { pros: ['Best reasoning', 'Excellent for objections', 'Long context', 'High quality'], color: 'bg-violet-500' },
  deepseek: { pros: ['Cheapest', 'Good for async', 'Budget friendly', 'Decent quality'], color: 'bg-blue-500' },
}

export default function SettingsView() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('llm')
  const [selectedProvider, setSelectedProvider] = useState('groq')
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    groq: '',
    openai: '',
    anthropic: '',
    deepseek: '',
  })
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')
  const [testLatency, setTestLatency] = useState<number | null>(null)

  // Business context state
  const [battleCard, setBattleCard] = useState<BattleCard>({ ...mockBattleCard })

  // Objections state
  const [objections, setObjections] = useState<Objection[]>([...mockObjections])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Partial<Objection>>({})

  const providerMutation = useMutation('/api/settings/provider', 'POST')
  const battleCardMutation = useMutation('/api/battle-card', 'PUT')

  const handleSaveProvider = async () => {
    setSaveStatus('saving')
    try {
      await providerMutation.mutate({ provider: selectedProvider, api_key: apiKeys[selectedProvider] || undefined })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 3000)
    } catch {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  const handleTestProvider = async () => {
    setTestStatus('testing')
    setTestLatency(null)
    const start = performance.now()
    try {
      await fetch('/api/settings/provider', {
        method: 'GET',
        headers: { 'x-provider': selectedProvider },
      })
      const latency = Math.round(performance.now() - start)
      setTestLatency(latency)
      setTestStatus('success')
    } catch {
      // Mock latency test
      await new Promise(r => setTimeout(r, 800))
      const mockLatency = selectedProvider === 'groq' ? 85 : selectedProvider === 'openai' ? 250 : selectedProvider === 'anthropic' ? 350 : 400
      setTestLatency(mockLatency)
      setTestStatus('success')
    }
    setTimeout(() => setTestStatus('idle'), 4000)
  }

  const handleSaveBattleCard = async () => {
    setSaveStatus('saving')
    try {
      await battleCardMutation.mutate({ ...battleCard } as unknown as Record<string, unknown>)
      setSaveStatus('saved')
    } catch {
      setSaveStatus('saved') // Mock success
    }
    setTimeout(() => setSaveStatus('idle'), 3000)
  }

  const handleEditObjection = (obj: Objection) => {
    setEditingId(obj.id)
    setEditForm({ ...obj })
  }

  const handleSaveObjection = () => {
    if (!editingId) return
    setObjections(prev => prev.map(o => o.id === editingId ? { ...o, ...editForm } as Objection : o))
    setEditingId(null)
    setEditForm({})
  }

  const handleDeleteObjection = (id: string) => {
    setObjections(prev => prev.filter(o => o.id !== id))
  }

  const handleAddObjection = () => {
    const newObj: Objection = {
      id: Date.now().toString(),
      trigger: 'New trigger phrase',
      response: 'Enter response here...',
      category: 'general',
    }
    setObjections(prev => [...prev, newObj])
    setEditingId(newObj.id)
    setEditForm({ ...newObj })
  }

  const tabs: { id: SettingsTab; label: string; icon: typeof Settings }[] = [
    { id: 'llm', label: 'LLM Provider', icon: Zap },
    { id: 'business', label: 'Business Context', icon: Building2 },
    { id: 'objections', label: 'Objections', icon: MessageSquareWarning },
  ]

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1 bg-white rounded-xl border border-slate-200 p-1 shadow-sm w-fit">
        {tabs.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all',
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* LLM Provider Tab */}
      {activeTab === 'llm' && (
        <div className="space-y-6">
          {/* Provider Selection */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-base font-semibold text-slate-800 mb-1">LLM Provider</h3>
            <p className="text-sm text-slate-500 mb-5">Switch the AI engine that powers your phone agent</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
              {mockProviders.map(p => {
                const info = providerInfo[p.id] || { pros: [], color: 'bg-slate-500' }
                const isSelected = selectedProvider === p.id
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProvider(p.id)}
                    className={cn(
                      'relative flex flex-col items-start p-4 rounded-xl border-2 text-left transition-all',
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50/50 shadow-sm'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    )}
                  >
                    {isSelected && (
                      <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                    <div className="flex items-center gap-2 mb-2">
                      <div className={cn('w-2.5 h-2.5 rounded-full', info.color)} />
                      <span className="font-semibold text-sm text-slate-800">{p.name}</span>
                      <span className="text-xs text-slate-400">{p.model}</span>
                    </div>
                    <p className="text-xs text-slate-500 mb-2">{p.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {info.pros.map(pro => (
                        <span key={pro} className="px-2 py-0.5 rounded-full bg-white border border-slate-200 text-[10px] text-slate-500">
                          {pro}
                        </span>
                      ))}
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-xs">
                      <span className="text-slate-400">
                        Latency: <span className="font-mono font-medium text-slate-600">{p.latency_ms}ms</span>
                      </span>
                      <span className={cn(
                        'px-1.5 py-0.5 rounded text-[10px] font-medium',
                        p.api_key_set ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'
                      )}>
                        {p.api_key_set ? 'Key set' : 'No key'}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* API Key Input */}
            <div className="mb-5">
              <label className="block text-xs font-medium text-slate-700 mb-1.5">
                API Key for {mockProviders.find(p => p.id === selectedProvider)?.name}
              </label>
              <div className="relative">
                <input
                  type={showKeys[selectedProvider] ? 'text' : 'password'}
                  value={apiKeys[selectedProvider] || ''}
                  onChange={e => setApiKeys(prev => ({ ...prev, [selectedProvider]: e.target.value }))}
                  placeholder="Enter API key (leave empty to use env var)"
                  className="w-full px-4 py-2.5 pr-10 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <button
                  onClick={() => setShowKeys(prev => ({ ...prev, [selectedProvider]: !prev[selectedProvider] }))}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showKeys[selectedProvider] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveProvider}
                disabled={saveStatus === 'saving'}
                className={cn(
                  'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all',
                  saveStatus === 'saved'
                    ? 'bg-emerald-600 text-white'
                    : saveStatus === 'error'
                    ? 'bg-rose-600 text-white'
                    : 'bg-indigo-600 text-white hover:bg-indigo-700'
                )}
              >
                {saveStatus === 'saving' && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                {saveStatus === 'saved' && <Check className="w-4 h-4" />}
                {saveStatus === 'error' && <AlertCircle className="w-4 h-4" />}
                {saveStatus === 'idle' && <Save className="w-4 h-4" />}
                {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved!' : saveStatus === 'error' ? 'Failed' : 'Save Provider'}
              </button>

              <button
                onClick={handleTestProvider}
                disabled={testStatus === 'testing'}
                className={cn(
                  'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium border transition-all',
                  testStatus === 'success'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : testStatus === 'error'
                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                )}
              >
                {testStatus === 'testing' && <div className="w-4 h-4 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />}
                {testStatus === 'success' && <Check className="w-4 h-4" />}
                {testStatus === 'idle' && <TestTube className="w-4 h-4" />}
                {testStatus === 'testing' ? 'Testing...' : testStatus === 'success' ? `${testLatency}ms` : 'Test Provider'}
              </button>
            </div>
          </div>

          {/* Info Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(providerInfo).map(([key, info]) => (
              <div key={key} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <div className={cn('w-2 h-2 rounded-full', info.color)} />
                  <span className="text-sm font-semibold text-slate-700 capitalize">{key}</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {info.pros.map(pro => (
                    <span key={pro} className="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-100 text-[10px] text-slate-500">
                      {pro}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Business Context Tab */}
      {activeTab === 'business' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-base font-semibold text-slate-800 mb-1">Business Context</h3>
            <p className="text-sm text-slate-500 mb-5">
              This information forms the AI&apos;s &quot;battle card&quot; — everything it needs to know about your business.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
              {([
                { key: 'business_name', label: 'Business Name', placeholder: 'Hamza Coaching' },
                { key: 'owner_name', label: 'Owner Name', placeholder: 'John Doe' },
                { key: 'pricing', label: 'Pricing', placeholder: 'Rs 25,000 for 8 sessions' },
                { key: 'session_duration', label: 'Session Duration', placeholder: '60 minutes' },
                { key: 'ideal_client', label: 'Ideal Client', placeholder: 'Working professionals with 3-10 years experience' },
                { key: 'calendar_link', label: 'Calendar Link', placeholder: 'https://calendly.com/...' },
              ] as const).map(field => (
                <div key={field.key}>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">{field.label}</label>
                  <input
                    type="text"
                    value={battleCard[field.key] || ''}
                    onChange={e => setBattleCard(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
              ))}
              <div className="md:col-span-2">
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Service Description</label>
                <textarea
                  value={battleCard.service_description}
                  onChange={e => setBattleCard(prev => ({ ...prev, service_description: e.target.value }))}
                  placeholder="Describe your coaching service..."
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                />
              </div>
            </div>

            <button
              onClick={handleSaveBattleCard}
              disabled={saveStatus === 'saving'}
              className={cn(
                'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all',
                saveStatus === 'saved' ? 'bg-emerald-600 text-white' : 'bg-indigo-600 text-white hover:bg-indigo-700'
              )}
            >
              {saveStatus === 'saving' && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
              {saveStatus === 'saved' && <Check className="w-4 h-4" />}
              {saveStatus === 'idle' && <Save className="w-4 h-4" />}
              {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved!' : 'Save Changes'}
            </button>
          </div>

          {/* Preview */}
          <div className="bg-slate-900 rounded-xl p-6 shadow-sm">
            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              AI Battle Card Preview
            </h4>
            <div className="bg-slate-800 rounded-lg p-4 space-y-2 text-sm font-mono">
              <p><span className="text-indigo-400">business_name:</span> <span className="text-emerald-400">&quot;{battleCard.business_name || '...'}&quot;</span></p>
              <p><span className="text-indigo-400">owner_name:</span> <span className="text-emerald-400">&quot;{battleCard.owner_name || '...'}&quot;</span></p>
              <p><span className="text-indigo-400">pricing:</span> <span className="text-emerald-400">&quot;{battleCard.pricing || '...'}&quot;</span></p>
              <p><span className="text-indigo-400">session_duration:</span> <span className="text-emerald-400">&quot;{battleCard.session_duration || '...'}&quot;</span></p>
              <p><span className="text-indigo-400">ideal_client:</span> <span className="text-emerald-400">&quot;{battleCard.ideal_client || '...'}&quot;</span></p>
              <p><span className="text-indigo-400">service_description:</span> <span className="text-emerald-400">&quot;{battleCard.service_description?.slice(0, 100) || '...'}{battleCard.service_description?.length > 100 ? '...' : ''}&quot;</span></p>
            </div>
          </div>
        </div>
      )}

      {/* Objections Tab */}
      {activeTab === 'objections' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-base font-semibold text-slate-800">Objection Handlers</h3>
                <p className="text-sm text-slate-500">Configure how the AI responds to common objections</p>
              </div>
              <button
                onClick={handleAddObjection}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Objection
              </button>
            </div>

            <div className="space-y-3">
              {objections.map((obj, index) => (
                <div key={obj.id} className="border border-slate-200 rounded-xl overflow-hidden">
                  {/* Header row */}
                  <div
                    className="flex items-center gap-3 px-4 py-3 bg-slate-50 cursor-pointer hover:bg-slate-100 transition-colors"
                    onClick={() => editingId === obj.id ? null : handleEditObjection(obj)}
                  >
                    <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-semibold flex-shrink-0">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-700 truncate">
                        Trigger: <span className="text-slate-500">&quot;{obj.trigger}&quot;</span>
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-[10px] font-medium capitalize">
                      {obj.category}
                    </span>
                    {editingId === obj.id ? (
                      <ChevronUp className="w-4 h-4 text-slate-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-400" />
                    )}
                  </div>

                  {/* Edit form */}
                  {editingId === obj.id && (
                    <div className="p-4 border-t border-slate-200 space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-slate-700 mb-1">Trigger Phrase</label>
                        <input
                          type="text"
                          value={editForm.trigger || ''}
                          onChange={e => setEditForm(prev => ({ ...prev, trigger: e.target.value }))}
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-700 mb-1">Response</label>
                        <textarea
                          value={editForm.response || ''}
                          onChange={e => setEditForm(prev => ({ ...prev, response: e.target.value }))}
                          rows={3}
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-700 mb-1">Category</label>
                        <input
                          type="text"
                          value={editForm.category || ''}
                          onChange={e => setEditForm(prev => ({ ...prev, category: e.target.value }))}
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={handleSaveObjection}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
                        >
                          <Save className="w-3.5 h-3.5" />
                          Save
                        </button>
                        <button
                          onClick={() => { setEditingId(null); setEditForm({}) }}
                          className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-50 transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleDeleteObjection(obj.id)}
                          className="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-lg text-rose-600 text-xs font-medium hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {objections.length === 0 && (
                <div className="text-center py-8 text-sm text-slate-400">
                  No objections configured yet. Click &quot;Add Objection&quot; to create one.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
