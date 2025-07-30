import React, { useState, useEffect } from 'react'
import { authService } from '../services/auth'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

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
  }

  const switchMode = () => {
    setMode(mode === 'signin' ? 'signup' : 'signin')
    resetForm()
  }

  if (!isOpen) return null

  const isSignIn = mode === 'signin'

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className={`
        relative w-full max-w-md transform transition-all duration-300 
        ${isSignIn 
          ? 'bg-gradient-to-br from-blue-50 to-purple-50' 
          : 'bg-gradient-to-br from-purple-50 to-pink-50'
        }
        rounded-2xl shadow-2xl border border-white/20
      `}>
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors z-10"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Header with different designs */}
        <div className={`
          px-8 pt-8 pb-4 text-center
          ${isSignIn 
            ? 'bg-gradient-to-r from-blue-400 to-purple-500' 
            : 'bg-gradient-to-r from-purple-600 to-pink-600'
          }
          rounded-t-2xl text-white
        `}>
          <div className={`
            w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center
            ${isSignIn 
              ? 'bg-white/20 backdrop-blur-sm' 
              : 'bg-white/20 backdrop-blur-sm'
            }
          `}>
            {isSignIn ? (
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            ) : (
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
            )}
          </div>
          <h2 className="text-2xl font-bold mb-2">
            {isSignIn ? 'Sign in to get more' : 'Supabase Secure Auth'}
          </h2>
          
          {/* Rate limit info moved up */}
          {isSignIn && (
            <div className="flex items-center justify-center space-x-6 text-sm text-white/90 mb-2">
              <div className="flex items-center">
                <div className="w-2 h-2 bg-yellow-300 rounded-full mr-2"></div>
                <span>Guest: 0/5/day</span>
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-green-300 rounded-full mr-2"></div>
                <span>Member: 0/20/day</span>
              </div>
            </div>
          )}
          
          {!isSignIn && (
            <p className="text-white/70 text-xs mt-2">
              Supabase manages user accounts and passwords securely
            </p>
          )}
        </div>

        {/* Form section */}
        <div className="px-8 py-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email field */}
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-semibold text-gray-700">
                Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={`
                    w-full px-4 py-3 bg-white border-2 rounded-xl transition-all duration-200
                    placeholder-transparent focus:placeholder-gray-400
                    ${isSignIn 
                      ? 'border-blue-200 focus:border-purple-500 focus:ring-4 focus:ring-purple-500/20' 
                      : 'border-purple-200 focus:border-pink-500 focus:ring-4 focus:ring-pink-500/20'
                    }
                    focus:outline-none text-gray-900
                  `}
                  placeholder="Enter your email"
                />
                <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Password field */}
            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-semibold text-gray-700">
                Password
              </label>
              <div className="relative">
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className={`
                    w-full px-4 py-3 bg-white border-2 rounded-xl transition-all duration-200
                    placeholder-transparent focus:placeholder-gray-400
                    ${isSignIn 
                      ? 'border-blue-200 focus:border-purple-500 focus:ring-4 focus:ring-purple-500/20' 
                      : 'border-purple-200 focus:border-pink-500 focus:ring-4 focus:ring-pink-500/20'
                    }
                    focus:outline-none text-gray-900
                  `}
                  placeholder="Enter your password"
                />
                <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
              </div>
              {mode === 'signup' && (
                <p className="text-xs text-gray-500 mt-1">
                  Password must be at least 6 characters long
                </p>
              )}
            </div>

            {/* Error message */}
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg">
                <div className="flex">
                  <svg className="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-red-700 text-sm font-medium">{error}</p>
                </div>
              </div>
            )}

            {/* Success message */}
            {message && (
              <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-lg">
                <div className="flex">
                  <svg className="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-green-700 text-sm font-medium">{message}</p>
                </div>
              </div>
            )}

            {/* Submit button */}
            <button
              type="submit"
              disabled={loading}
              className={`
                w-full py-3 px-4 rounded-xl font-semibold text-white transition-all duration-200
                ${isSignIn 
                  ? 'bg-gradient-to-r from-blue-400 to-purple-500 hover:from-blue-500 hover:to-purple-600 focus:ring-4 focus:ring-purple-500/20' 
                  : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 focus:ring-4 focus:ring-pink-500/20'
                }
                focus:outline-none disabled:opacity-70 disabled:cursor-not-allowed
                transform hover:scale-[1.02] active:scale-[0.98]
                shadow-lg hover:shadow-xl
              `}
            >
              {loading ? (
                <div className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {isSignIn ? 'Signing In...' : 'Creating Account...'}
                </div>
              ) : (
                isSignIn ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>

          {/* Mode switch */}
          <div className="mt-6 text-center">
            <p className="text-gray-600 text-sm">
              {isSignIn ? "Don't have an account?" : 'Already have an account?'}
            </p>
            <button
              onClick={switchMode}
              className={`
                mt-2 font-semibold transition-colors duration-200
                ${isSignIn 
                  ? 'text-purple-600 hover:text-purple-700' 
                  : 'text-pink-600 hover:text-pink-700'
                }
              `}
            >
              {isSignIn ? 'Create Account' : 'Sign In Instead'}
            </button>
          </div>

          {/* Rate limit info for sign-up only */}
          {!isSignIn && (
            <div className="mt-6 pt-4 border-t border-gray-200">
              <div className="flex items-center justify-center space-x-6 text-xs text-gray-500">
                <div className="flex items-center">
                  <div className="w-2 h-2 bg-yellow-400 rounded-full mr-2"></div>
                  <span>Guest: 0/5/day</span>
                </div>
                <div className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                  <span>Member: 0/20/day</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}