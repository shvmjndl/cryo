import { useState } from 'react'
import { Dna, FlaskConical, ArrowRight } from 'lucide-react'

interface Props {
  onLogin: (email: string, password: string) => Promise<void>
  onSignup: (data: { email: string; username: string; password: string; full_name?: string }) => Promise<void>
}

export default function AuthPage({ onLogin, onSignup }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await onLogin(email, password)
      } else {
        await onSignup({ email, username, password, full_name: fullName || undefined })
      }
    } catch (err: any) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center p-16 bg-[var(--color-cryo-surface)]">
        <div className="max-w-md">
          <div className="flex items-center gap-3 mb-8">
            <Dna className="w-10 h-10 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
            <span className="text-4xl font-bold font-mono tracking-widest text-[var(--color-cryo-accent)]">
              CRYO
            </span>
          </div>
          <h1 className="text-3xl font-light text-[var(--color-cryo-text)] mb-4 leading-tight">
            Comprehensive Research
            <br />
            <span className="text-[var(--color-cryo-accent)]">Yielding Outcomes</span>
          </h1>
          <p className="text-[var(--color-cryo-text-dim)] text-lg leading-relaxed mb-8">
            AI-powered biology research platform. Mine literature, annotate proteins,
            repurpose drugs, and interpret genomic variants — all from one interface.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2">
            {['Literature Mining', 'Protein Analysis', 'Drug Repurposing', 'Variant Interpretation'].map(f => (
              <span
                key={f}
                className="px-3 py-1.5 rounded-full text-xs font-mono border border-[var(--color-cryo-border-bright)] text-[var(--color-cryo-text-dim)]"
              >
                <FlaskConical className="w-3 h-3 inline mr-1.5 text-[var(--color-cryo-accent)]" />
                {f}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <Dna className="w-8 h-8 text-[var(--color-cryo-accent)]" strokeWidth={1.5} />
            <span className="text-3xl font-bold font-mono tracking-widest text-[var(--color-cryo-accent)]">CRYO</span>
          </div>

          <h2 className="text-xl font-medium mb-6 text-center">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <>
                <input
                  type="text"
                  placeholder="Full name"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] text-[var(--color-cryo-text)] placeholder:text-[var(--color-cryo-text-muted)] focus:outline-none focus:border-[var(--color-cryo-accent)] transition-colors"
                />
                <input
                  type="text"
                  placeholder="Username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  required
                  className="w-full px-4 py-3 rounded-lg bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] text-[var(--color-cryo-text)] placeholder:text-[var(--color-cryo-text-muted)] focus:outline-none focus:border-[var(--color-cryo-accent)] transition-colors"
                />
              </>
            )}
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full px-4 py-3 rounded-lg bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] text-[var(--color-cryo-text)] placeholder:text-[var(--color-cryo-text-muted)] focus:outline-none focus:border-[var(--color-cryo-accent)] transition-colors"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-4 py-3 rounded-lg bg-[var(--color-cryo-surface-2)] border border-[var(--color-cryo-border)] text-[var(--color-cryo-text)] placeholder:text-[var(--color-cryo-text-muted)] focus:outline-none focus:border-[var(--color-cryo-accent)] transition-colors"
            />

            {error && (
              <div className="text-[var(--color-cryo-red)] text-sm text-center">{error}</div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg bg-[var(--color-cryo-accent)] text-[var(--color-cryo-bg)] font-semibold hover:brightness-110 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? 'Processing...' : mode === 'login' ? 'Sign in' : 'Create account'}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[var(--color-cryo-text-dim)]">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError('') }}
              className="text-[var(--color-cryo-accent)] hover:underline"
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
