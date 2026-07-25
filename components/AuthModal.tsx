import React, { useState, useEffect } from 'react'
import { authService } from '../services/auth'
// @ts-ignore
import { Helmet } from 'react-helmet-async'

// --- Function/Class Map ---
// Component: AuthModal — reusable sign-in/sign-up modal; called from Chat, LinkedIn photo pages, and the nav drawer to prompt Supabase auth.
// Purpose: Present Supabase-powered email/password and OAuth flows with consistent styling and status messaging.
// Themed to the site system: bg #12110F · surface #191816 · bone #F1EADF · muted #A8A096 · hairline #37332E · vermilion #F04A32.

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

const inputClass =
  'w-full rounded-[4px] border border-[#37332E] bg-[#12110F] px-4 py-3 text-[15px] text-[#F1EADF] placeholder-[#A8A096]/50 transition-colors focus:border-[#F04A32] focus:outline-none'

const labelClass = 'block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A8A096]'

const Spinner: React.FC = () => (
  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
)

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [githubLoading, setGithubLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      resetForm()
    }
  }, [isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')

    try {
      if (mode === 'signup') {
        const result = await authService.signUp(email, password)
        if (result.success) {
          if (result.needsConfirmation) {
            setMessage('Please check your email to confirm your account.')
          } else {
            setMessage('Account created successfully!')
            setTimeout(() => {
              onSuccess?.()
              onClose()
            }, 1500)
          }
        } else {
          setError(result.error || 'Sign up failed')
        }
      } else {
        const result = await authService.signIn(email, password)
        if (result.success) {
          setMessage('Signed in successfully!')
          setTimeout(() => {
            onSuccess?.()
            onClose()
          }, 1000)
        } else {
          setError(result.error || 'Sign in failed')
        }
      }
    } catch (err) {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setEmail('')
    setPassword('')
    setError('')
    setMessage('')
    setLoading(false)
    setGithubLoading(false)
    setGoogleLoading(false)
  }

  const handleGitHubSignIn = async () => {
    setGithubLoading(true)
    setError('')
    setMessage('')

    try {
      const result = await authService.signInWithGitHub()
      if (result.success) {
        setMessage('Signed in successfully!')
        setTimeout(() => { onSuccess?.(); onClose() }, 1000)
      } else {
        setError(result.error || 'GitHub sign-in failed')
      }
    } catch (err) {
      setError('An unexpected error occurred with GitHub sign-in')
    } finally {
      setGithubLoading(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true)
    setError('')
    setMessage('')

    try {
      const result = await authService.signInWithGoogle()
      if (result.success) {
        setMessage('Signed in successfully!')
        setTimeout(() => { onSuccess?.(); onClose() }, 1000)
      } else {
        setError(result.error || 'Google sign-in failed')
      }
    } catch (err) {
      setError('An unexpected error occurred with Google sign-in')
    } finally {
      setGoogleLoading(false)
    }
  }

  const switchMode = () => {
    setMode(mode === 'signin' ? 'signup' : 'signin')
    resetForm()
  }

  if (!isOpen) return null

  const isSignIn = mode === 'signin'

  return (
    <>
      <Helmet>
        <meta name="robots" content="noindex,nofollow" />
      </Helmet>
      {/* z-[90]: above the nav drawer (z-[70]) that can spawn this modal */}
      <div
        className="fixed inset-0 z-[90] flex items-center justify-center bg-[#12110F]/80 p-4 backdrop-blur-sm"
        onClick={onClose}
        style={{ colorScheme: 'dark' }}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-md rounded-[6px] border border-[#37332E] bg-[#191816]"
        >
          {/* Close button */}
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-4 top-4 z-10 flex h-9 w-9 items-center justify-center rounded-[4px] text-[#A8A096] transition-colors hover:text-[#F1EADF]"
          >
            ✕
          </button>

          {/* Header */}
          <div className="border-b border-[#37332E] px-8 pb-6 pt-8">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#F04A32]">Access</p>
            <h2 className="mt-2 text-[26px] font-black tracking-[-0.03em] text-[#F1EADF]">
              {isSignIn ? 'Sign in' : 'Create account'}<span className="text-[#F04A32]">.</span>
            </h2>
            {isSignIn ? (
              <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-[#A8A096]">
                Guest 5/day · Member 10/day
              </p>
            ) : (
              <p className="mt-2 text-[13px] text-[#A8A096]">
                Accounts and passwords are managed securely by Supabase.
              </p>
            )}
          </div>

          {/* Form section */}
          <div className="px-8 py-6">
            {/* OAuth Buttons - Only show for sign-in */}
            {isSignIn && (
              <div className="mb-6">
                <div className="grid grid-cols-1 gap-3">
                  {/* Google OAuth Button */}
                  <button
                    type="button"
                    onClick={handleGoogleSignIn}
                    disabled={googleLoading || loading || githubLoading}
                    className="flex w-full items-center justify-center gap-3 rounded-[4px] border border-[#37332E] bg-transparent px-4 py-3 text-[14px] font-semibold text-[#F1EADF] transition-colors hover:border-[#A8A096] hover:bg-[#12110F] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {googleLoading ? (
                      <><Spinner /> Connecting...</>
                    ) : (
                      <>
                        <svg className="h-4 w-4" viewBox="0 0 24 24">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                        Continue with Google
                      </>
                    )}
                  </button>

                  {/* GitHub OAuth Button */}
                  <button
                    type="button"
                    onClick={handleGitHubSignIn}
                    disabled={githubLoading || loading || googleLoading}
                    className="flex w-full items-center justify-center gap-3 rounded-[4px] border border-[#37332E] bg-transparent px-4 py-3 text-[14px] font-semibold text-[#F1EADF] transition-colors hover:border-[#A8A096] hover:bg-[#12110F] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {githubLoading ? (
                      <><Spinner /> Connecting...</>
                    ) : (
                      <>
                        <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M12 0C5.374 0 0 5.373 0 12 0 17.302 3.438 21.8 8.207 23.387c.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.30.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                        </svg>
                        Continue with GitHub
                      </>
                    )}
                  </button>
                </div>

                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-[#37332E]"></div>
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-[#191816] px-3 font-mono text-[10px] uppercase tracking-[0.2em] text-[#A8A096]">or</span>
                  </div>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email field */}
              <div className="space-y-2">
                <label htmlFor="email" className={labelClass}>
                  Email address
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={inputClass}
                  placeholder="you@example.com"
                />
              </div>

              {/* Password field */}
              <div className="space-y-2">
                <label htmlFor="password" className={labelClass}>
                  Password
                </label>
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className={inputClass}
                  placeholder="••••••••"
                />
                {mode === 'signup' && (
                  <p className="text-[12px] text-[#A8A096]">
                    Password must be at least 6 characters long
                  </p>
                )}
              </div>

              {/* Error message */}
              {error && (
                <div className="rounded-[4px] border-l-2 border-[#F04A32] bg-[#F04A32]/10 px-4 py-3">
                  <p className="text-[13px] font-medium text-[#F1EADF]">{error}</p>
                </div>
              )}

              {/* Success message */}
              {message && (
                <div className="rounded-[4px] border-l-2 border-[#F1EADF]/50 bg-[#12110F] px-4 py-3">
                  <p className="text-[13px] font-medium text-[#F1EADF]">{message}</p>
                </div>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-[4px] bg-[#F04A32] px-4 py-3 text-[15px] font-semibold text-[#12110F] transition-colors hover:bg-[#D63B27] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <><Spinner /> {isSignIn ? 'Signing in...' : 'Creating account...'}</>
                ) : (
                  isSignIn ? 'Sign in' : 'Create account'
                )}
              </button>
            </form>

            {/* Mode switch */}
            <div className="mt-6 flex items-baseline justify-center gap-2 text-[13px]">
              <span className="text-[#A8A096]">
                {isSignIn ? "Don't have an account?" : 'Already have an account?'}
              </span>
              <button
                onClick={switchMode}
                className="font-semibold text-[#F04A32] transition-colors hover:text-[#D63B27]"
              >
                {isSignIn ? 'Create account' : 'Sign in instead'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
