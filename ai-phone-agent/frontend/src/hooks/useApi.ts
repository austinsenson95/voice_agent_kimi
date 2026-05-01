import { useState, useEffect, useCallback, useRef } from 'react'

const BASE_URL = (import.meta as unknown as { env: Record<string, string> }).env.VITE_API_URL || ''

interface UseApiOptions {
  refreshInterval?: number
  enabled?: boolean
}

interface UseApiResult<T> {
  data: T | null
  loading: boolean
  error: Error | null
  refetch: () => void
  isMock: boolean
}

export function useApi<T>(
  endpoint: string,
  options: UseApiOptions = {}
): UseApiResult<T> {
  const { refreshInterval = 0, enabled = true } = options
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [isMock, setIsMock] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch(`${BASE_URL}${endpoint}`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const result = await response.json()
      setData(result)
      setError(null)
      setIsMock(false)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setLoading(false)
    }
  }, [endpoint])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    fetchData()
    if (refreshInterval > 0) {
      intervalRef.current = setInterval(fetchData, refreshInterval)
      return () => {
        if (intervalRef.current) clearInterval(intervalRef.current)
      }
    }
  }, [fetchData, refreshInterval, enabled])

  return { data, loading, error, refetch: fetchData, isMock }
}

interface UseMutationResult<T, V> {
  mutate: (variables: V) => Promise<T | null>
  loading: boolean
  error: Error | null
  data: T | null
}

export function useMutation<T = unknown, V = Record<string, unknown>>(
  endpoint: string,
  method: 'POST' | 'PUT' | 'DELETE' = 'POST'
): UseMutationResult<T, V> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const mutate = useCallback(
    async (variables: V): Promise<T | null> => {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`${BASE_URL}${endpoint}`, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(variables),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const result = await response.json()
        setData(result)
        return result
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err))
        setError(error)
        return null
      } finally {
        setLoading(false)
      }
    },
    [endpoint, method]
  )

  return { mutate, loading, error, data }
}
