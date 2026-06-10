import { authService } from './auth'
import { configService } from './config'

// --- Function/Class Map ---
// Class: ApiService — shared API client; called across frontend components to add auth headers and surface rate-limit details.
// Method: makeRequest — core fetch wrapper surfacing server-provided detail messages for 401/429 responses.
// Method: getUsageStats/countUserInput — fetches/consumes per-scope rate limits for chat and other workflows.
// Purpose: Centralize backend communication with consistent error handling and auth headers.

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
  base_identifier?: string
  scope: string
  message?: string
}

class ApiService {
  private baseUrl: string

  constructor(baseUrl?: string) {
    // Use config service first, then provided baseUrl, then fallback
    this.baseUrl = configService.getBackendUrl() || baseUrl || 'http://localhost:8000'
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const extractError = async (response: Response) => {
      try {
        const data = await response.json()
        if (typeof data?.detail === 'string') return data.detail
        if (typeof data?.error === 'string') return data.error
      } catch {
        // ignore JSON parse issues
      }
      try {
        const text = await response.text()
        const trimmed = text.trim()
        if (trimmed && !trimmed.startsWith('<')) {
          return trimmed
        }
      } catch {
        // ignore text read issues
      }
      return undefined
    }

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
        const detail = await extractError(response)
        return {
          success: false,
          needsAuth: true,
          retryAfter: retryAfter ? parseInt(retryAfter) : undefined,
          error: detail || 'Sign-in required after free quota. Please sign in to continue.',
        }
      }

      // Handle standard rate limiting (429)
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After')
        const detail = await extractError(response)
        return {
          success: false,
          retryAfter: retryAfter ? parseInt(retryAfter) : undefined,
          error: detail || 'Rate limit exceeded. Please try again later.',
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

  async getUsageStats(scope?: string): Promise<ApiResponse<UsageStats>> {
    const query = scope ? `?scope=${encodeURIComponent(scope)}` : ''
    return this.get<UsageStats>(`/api/rate-limit/usage${query}`)
  }

  async countUserInput(options?: { scope?: string; weight?: number }): Promise<ApiResponse<UsageStats>> {
    const payload = options
      ? { ...(options.scope ? { scope: options.scope } : {}), ...(options.weight ? { weight: options.weight } : {}) }
      : undefined
    return this.post<UsageStats>('/api/user-input', payload)
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
