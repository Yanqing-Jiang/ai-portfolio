import { authService } from './auth'

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  needsAuth?: boolean
  retryAfter?: number
}

export interface UsageStats {
  current_usage: number
  limit: number
  remaining: number
  user_type: 'guest' | 'member'
  identifier: string
}

class ApiService {
  private baseUrl: string

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      // Get auth headers
      const authHeaders = await authService.getAuthHeaders()
      
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
          ...options.headers,
        },
      })

      // Handle rate limiting (401 means auth required for more requests)
      if (response.status === 401) {
        const retryAfter = response.headers.get('Retry-After')
        return {
          success: false,
          needsAuth: true,
          retryAfter: retryAfter ? parseInt(retryAfter) : undefined,
          error: 'Sign-in required after free quota. Please sign in to continue.',
        }
      }

      // Handle standard rate limiting (429)
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After')
        return {
          success: false,
          retryAfter: retryAfter ? parseInt(retryAfter) : undefined,
          error: 'Rate limit exceeded. Please try again later.',
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        return {
          success: false,
          error: errorData.detail || errorData.error || `HTTP ${response.status}`,
        }
      }

      const data = await response.json()
      return {
        success: true,
        data,
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
      }
    }
  }

  async post<T>(endpoint: string, body?: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'GET',
    })
  }

  async getUsageStats(): Promise<ApiResponse<UsageStats>> {
    return this.get<UsageStats>('/api/rate-limit/usage')
  }

  // Enhanced streaming method that handles auth errors
  async streamWithAuth(
    endpoint: string,
    onMessage: (data: any) => void,
    onError?: (error: string, needsAuth?: boolean) => void,
    onComplete?: () => void
  ): Promise<void> {
    try {
      const authHeaders = await authService.getAuthHeaders()
      
      // Use fetch for streaming
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
          ...authHeaders,
        },
      })

      // Handle rate limiting before starting stream
      if (response.status === 401) {
        const retryAfter = response.headers.get('Retry-After')
        onError?.(
          'Sign-in required after free quota. Please sign in to continue.',
          true
        )
        return
      }

      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After')
        onError?.(`Rate limit exceeded. Please try again in ${retryAfter || 'a few'} seconds.`)
        return
      }

      if (!response.ok) {
        onError?.(`HTTP ${response.status}: ${response.statusText}`)
        return
      }

      // Process the stream
      const reader = response.body?.getReader()
      if (!reader) {
        onError?.('Failed to get response stream')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          
          if (done) {
            onComplete?.()
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep the last incomplete line

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                onMessage(data)
              } catch (parseError) {
                console.warn('Failed to parse SSE data:', line)
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    } catch (error) {
      onError?.(error instanceof Error ? error.message : 'Stream connection failed')
    }
  }
}

export const apiService = new ApiService()

// Helper function to show auth modal when needed
export const handleApiError = (
  error: ApiResponse,
  showAuthModal: () => void
): string => {
  if (error.needsAuth) {
    showAuthModal()
    return error.error || 'Authentication required'
  }
  
  return error.error || 'An error occurred'
}