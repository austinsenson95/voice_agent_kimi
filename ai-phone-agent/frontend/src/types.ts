export interface Turn {
  speaker: 'user' | 'ai';
  text: string;
  timestamp: string;
  state?: string;
}

export type CallState = 'opening' | 'discovery' | 'pitch' | 'objection' | 'close' | 'ended';
export type CallOutcome = 'booked' | 'declined' | 'handoff' | 'dropped' | 'in_progress';

export interface CallSession {
  call_sid: string;
  phone_number: string;
  state: CallState;
  outcome: CallOutcome;
  started_at: string;
  ended_at?: string;
  duration_seconds: number;
  transcript: Turn[];
  recording_url?: string;
  llm_provider: string;
  llm_model: string;
  last_ai_message?: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  model: string;
  latency_ms: number;
  api_key_set: boolean;
  description: string;
  pros: string[];
}

export interface BattleCard {
  business_name: string;
  owner_name: string;
  service_description: string;
  pricing: string;
  session_duration: string;
  ideal_client: string;
  calendar_link: string;
}

export interface Objection {
  id: string;
  trigger: string;
  response: string;
  category: string;
}

export interface DailyAnalytics {
  date: string;
  total_calls: number;
  booked: number;
  declined: number;
  handoff: number;
  dropped: number;
  avg_duration: number;
  avg_latency_ms: number;
}

export interface Analytics {
  summary: {
    total_calls: number;
    conversion_rate: number;
    avg_duration: number;
    top_objection: string;
  };
  daily: DailyAnalytics[];
  objections: { name: string; count: number }[];
  provider_usage: { provider: string; count: number }[];
  response_times: { timestamp: string; latency_ms: number; provider: string }[];
}

export interface HealthStatus {
  status: string;
  active_calls: number;
  current_provider: string;
  uptime_seconds: number;
}
