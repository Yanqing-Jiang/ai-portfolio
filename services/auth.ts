import { createClient } from '@supabase/supabase-js'
import { configService } from './config'

const supabaseUrl = configService.getSupabaseUrl()
const supabaseAnonKey = configService.getSupabaseAnonKey()

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env file.')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export interface User {
  id: string
  email?: string
  user_metadata?: Record<string, any>
}

export interface AuthState {
  user: User | null
  loading: boolean
  error: string | null
}

class AuthService {
  private listeners: ((authState: AuthState) => void)[] = []
  private currentState: AuthState = {
    user: null,
    loading: true,
    error: null
  }

  constructor() {
    this.initialize()
  }

  private async initialize() {
    try {
      // Get initial session
      const { data: { session }, error } = await supabase.auth.getSession()
      
      if (error) {
        this.updateState({ user: null, loading: false, error: error.message })
        return
      }

      this.updateState({
        user: session?.user || null,
        loading: false,
        error: null
      })

      // Listen for auth changes
      supabase.auth.onAuthStateChange((event, session) => {
        this.updateState({
          user: session?.user || null,
          loading: false,
          error: null
        })
      })
    } catch (error) {
      this.updateState({
        user: null,
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private updateState(newState: Partial<AuthState>) {
    this.currentState = { ...this.currentState, ...newState }
    this.listeners.forEach(listener => listener(this.currentState))
  }

  subscribe(listener: (authState: AuthState) => void) {
    this.listeners.push(listener)
    // Immediately call with current state
    listener(this.currentState)
    
    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener)
    }
  }

  getCurrentState(): AuthState {
    return this.currentState
  }

  async signUp(email: string, password: string) {
    try {
      this.updateState({ ...this.currentState, loading: true, error: null })
      
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
      })

      if (error) {
        this.updateState({ ...this.currentState, loading: false, error: error.message })
        return { success: false, error: error.message }
      }

      // Note: User might need to confirm email depending on your Supabase settings
      return { success: true, user: data.user, needsConfirmation: !data.session }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateState({ ...this.currentState, loading: false, error: errorMessage })
      return { success: false, error: errorMessage }
    }
  }

  async signIn(email: string, password: string) {
    try {
      this.updateState({ ...this.currentState, loading: true, error: null })
      
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      })

      if (error) {
        this.updateState({ ...this.currentState, loading: false, error: error.message })
        return { success: false, error: error.message }
      }

      return { success: true, user: data.user }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateState({ ...this.currentState, loading: false, error: errorMessage })
      return { success: false, error: errorMessage }
    }
  }

  async signInWithPopup(provider: 'github' | 'google'): Promise<{ success: boolean; error?: string }> {
    try {
      this.updateState({ ...this.currentState, loading: true, error: null })

      const callbackUrl = `${window.location.origin}/auth/callback`

      const { data, error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          skipBrowserRedirect: true,
          redirectTo: callbackUrl,
        },
      })

      if (error) {
        this.updateState({ ...this.currentState, loading: false, error: error.message })
        return { success: false, error: error.message }
      }

      if (!data?.url) {
        this.updateState({ ...this.currentState, loading: false })
        return { success: false, error: 'No OAuth URL returned' }
      }

      // Register listener BEFORE opening popup to avoid race condition
      const authPromise = new Promise<{ success: boolean; error?: string }>((resolve) => {
        let cleaned = false
        const cleanup = () => {
          if (cleaned) return
          cleaned = true
          window.removeEventListener('message', handleMessage)
          clearInterval(popupPollId)
          clearTimeout(timeoutId)
        }

        const handleMessage = (event: MessageEvent) => {
          if (event.origin !== window.location.origin) return
          if (event.data?.type !== 'supabase-auth-complete') return

          cleanup()
          supabase.auth.getSession().then(({ data: { session } }) => {
            this.updateState({
              user: session?.user || null,
              loading: false,
              error: null,
            })
            resolve({ success: !!session, error: session ? undefined : 'Session not established' })
          })
        }

        window.addEventListener('message', handleMessage)

        // Poll for popup closed (user dismissed it)
        let popupPollId: ReturnType<typeof setInterval>
        const startPolling = (popupRef: Window) => {
          popupPollId = setInterval(() => {
            if (popupRef.closed) {
              cleanup()
              this.updateState({ ...this.currentState, loading: false })
              resolve({ success: false, error: 'Sign-in window was closed' })
            }
          }, 500)
        }

        // Timeout after 5 minutes
        const timeoutId = setTimeout(() => {
          cleanup()
          this.updateState({ ...this.currentState, loading: false })
          resolve({ success: false, error: 'Sign-in timed out' })
        }, 300000)

        // Open popup after listener is ready
        const popup = window.open(data.url, 'supabase-auth', 'width=500,height=700,left=200,top=100')

        if (!popup || popup.closed) {
          // Popup blocked — fall back to redirect
          cleanup()
          const redirectTo = this.getRedirectUrl()
          supabase.auth.signInWithOAuth({ provider, options: { redirectTo } }).then(({ error: fbError }) => {
            if (fbError) {
              this.updateState({ ...this.currentState, loading: false, error: fbError.message })
              resolve({ success: false, error: fbError.message })
            } else {
              // Redirect will navigate away — resolve as pending
              resolve({ success: true })
            }
          })
          return
        }

        startPolling(popup)
      })

      return authPromise
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateState({ ...this.currentState, loading: false, error: errorMessage })
      return { success: false, error: errorMessage }
    }
  }

  async signInWithGitHub() {
    return this.signInWithPopup('github')
  }

  async signInWithGoogle() {
    return this.signInWithPopup('google')
  }

  private getRedirectUrl(): string {
    // Get the correct URL based on environment
    let url = configService.getAppUrl() ?? // Production URL from env
              window.location.origin ?? // Current origin fallback
              'http://localhost:3000' // Development fallback

    // Ensure URL starts with http
    if (!url.startsWith('http')) {
      url = `https://${url}`
    }

    // Remove trailing slash if present
    url = url.replace(/\/$/, '')

    // Preserve the current path so OAuth returns the user to where they were
    const currentPath = window.location.pathname + window.location.search
    if (currentPath && currentPath !== '/') {
      url += currentPath
    }

    console.log(`OAuth Redirect URL: ${url}`)

    return url
  }

  async signOut() {
    try {
      this.updateState({ ...this.currentState, loading: true, error: null })
      
      const { error } = await supabase.auth.signOut()
      
      if (error) {
        this.updateState({ ...this.currentState, loading: false, error: error.message })
        return { success: false, error: error.message }
      }

      return { success: true }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateState({ ...this.currentState, loading: false, error: errorMessage })
      return { success: false, error: errorMessage }
    }
  }

  async getAccessToken(): Promise<string | null> {
    try {
      // First try getSession which uses cached session
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        return session.access_token
      }

      // If no session but we have a user, force refresh to get a new token
      if (this.currentState.user) {
        console.warn('[Auth] Session missing but user exists, attempting refresh...')
        const { data: { session: refreshedSession }, error } = await supabase.auth.refreshSession()
        if (error) {
          console.error('[Auth] Session refresh failed:', error.message)
          return null
        }
        return refreshedSession?.access_token || null
      }

      return null
    } catch (error) {
      console.error('[Auth] getAccessToken error:', error)
      return null
    }
  }

  // Helper to get auth headers for API calls
  async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getAccessToken()
    if (!token && this.currentState.user) {
      console.error('[Auth] WARNING: User logged in but no access token available!')
    }
    return token
      ? { 'Authorization': `Bearer ${token}` }
      : {}
  }
}

// Export singleton instance
export const authService = new AuthService()