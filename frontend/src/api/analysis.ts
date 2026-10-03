/**
 * API client for the Pipe Freeze-Risk backend
 */

import type {
  PipeParams,
  AnalysisResponse,
  AnalysisStatus,
  AnalysisResults,
} from '@/types'

const API_BASE = '/api/analysis'

/** Throw with the backend's `detail` message when there is one */
async function check(response: Response, action: string): Promise<Response> {
  if (response.ok) return response
  let detail = response.statusText
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') detail = body.detail
    else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ')
  } catch {
    // Not JSON; keep statusText
  }
  throw new Error(`Failed to ${action}: ${detail}`)
}

class AnalysisAPI {
  /**
   * Start a full analysis on Allsolve
   */
  async start(params: PipeParams): Promise<AnalysisResponse> {
    const response = await fetch(`${API_BASE}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    await check(response, 'start analysis')
    return response.json()
  }

  /**
   * Get the current status of an analysis
   */
  async getStatus(analysisId: string): Promise<AnalysisStatus> {
    const response = await fetch(`${API_BASE}/${analysisId}/status`)
    await check(response, 'get status')
    return response.json()
  }

  /**
   * Get the results of a completed analysis
   */
  async getResults(analysisId: string): Promise<AnalysisResults> {
    const response = await fetch(`${API_BASE}/${analysisId}/results`)
    await check(response, 'get results')
    return response.json()
  }

  /**
   * Abort a running analysis
   */
  async abort(analysisId: string): Promise<{ status: string; message: string }> {
    const response = await fetch(`${API_BASE}/${analysisId}/abort`, { method: 'POST' })
    await check(response, 'abort analysis')
    return response.json()
  }

  /**
   * Local estimate on the backend (no Allsolve calls)
   */
  async runDemo(params: PipeParams): Promise<AnalysisResults> {
    const response = await fetch(`${API_BASE}/demo/demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    await check(response, 'run demo')
    return response.json()
  }

  /**
   * Create a WebSocket connection for real-time updates
   */
  connectWebSocket(
    analysisId: string,
    onMessage: (data: Record<string, unknown>) => void,
    onError?: (error: Event) => void
  ): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}${API_BASE}/${analysisId}/ws`)

    ws.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data))
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      onError?.(error)
    }

    // Send ping every 25 seconds to keep connection alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 25000)

    ws.onclose = () => {
      clearInterval(pingInterval)
    }

    return ws
  }
}

export const analysisApi = new AnalysisAPI()
