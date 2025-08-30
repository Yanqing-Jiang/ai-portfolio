/**
 * Configuration service to centralize environment variable access
 */
class ConfigService {
  private static instance: ConfigService

  public static getInstance(): ConfigService {
    if (!ConfigService.instance) {
      ConfigService.instance = new ConfigService()
    }
    return ConfigService.instance
  }

  /**
   * Get the backend URL from environment variables
   */
  getBackendUrl(): string {
    return import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
  }

  /**
   * Get the Supabase URL from environment variables
   */
  getSupabaseUrl(): string {
    return import.meta.env.VITE_SUPABASE_URL
  }

  /**
   * Get the Supabase anonymous key from environment variables
   */
  getSupabaseAnonKey(): string {
    return import.meta.env.VITE_SUPABASE_ANON_KEY
  }

  /**
   * Get the app URL for OAuth redirects
   */
  getAppUrl(): string {
    return import.meta.env.VITE_APP_URL
  }
}

// Export singleton instance
export const configService = ConfigService.getInstance()