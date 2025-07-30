import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

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

  async signInWithGitHub() {
    try {
      this.updateState({ ...this.currentState, loading: true, error: null })
      
      // Get the correct redirect URL based on environment
      const redirectTo = this.getRedirectUrl()
      
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'github',
        options: {
          redirectTo
        }
      })

      if (error) {
        this.updateState({ ...this.currentState, loading: false, error: error.message })
        return { success: false, error: error.message }
      }

      // OAuth will redirect, so we don't need to update state here
      return { success: true }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateState({ ...this.currentState, loading: false, error: errorMessage })
      return { success: false, error: errorMessage }
    }
  }

  async signInWithGoogle() {
    try {
      this.updateState({ ...this.currentState, loading: true, error: null })
      
      // Get the correct redirect URL based on environment
      const redirectTo = this.getRedirectUrl()
      
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo
        }
      })

      if (error) {
        this.updateState({ ...this.currentState, loading: false, error: error.message })
        return { success: false, error: error.message }
      }

      // OAuth will redirect, so we don't need to update state here
      return { success: true }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateState({ ...this.currentState, loading: false, error: errorMessage })
      return { success: false, error: errorMessage }
    }
  }

  private getRedirectUrl(): string {
    // Get the correct URL based on environment
    let url = import.meta.env.VITE_APP_URL ?? // Production URL from env
              window.location.origin ?? // Current origin fallback
              'http://localhost:3000' // Development fallback
    
    // Ensure URL starts with http
    if (!url.startsWith('http')) {
      url = `https://${url}`
    }
    
    // Remove trailing slash if present
    url = url.replace(/\/$/, '')
    
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
      const { data: { session } } = await supabase.auth.getSession()
      return session?.access_token || null
    } catch {
      return null
    }
  }

  // Helper to get auth headers for API calls
  async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getAccessToken()
    return token 
      ? { 'Authorization': `Bearer ${token}` }
      : {}
  }
}

// Export singleton instance
export const authService = new AuthService()