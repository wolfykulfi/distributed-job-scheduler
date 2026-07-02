import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import Button from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import SectionLabel from '../components/ui/SectionLabel'

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const { login, register } = useAuth()
  const navigate = useNavigate()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, fullName, orgName)
      }
      navigate('/projects')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-screen grid-cols-1 bg-white text-black md:grid-cols-12">
      {/* Left: identity block, asymmetric 7/12, textured */}
      <div className="swiss-grid-pattern relative flex flex-col justify-between border-black p-8 md:col-span-7 md:border-r-4 md:p-16">
        <span className="text-xs font-bold tracking-widest uppercase">Job Scheduler</span>
        <div>
          <SectionLabel index={1}>Authentication</SectionLabel>
          <h1 className="text-6xl leading-[0.9] font-black tracking-tighter uppercase md:text-8xl">
            Access
            <br />
            the
            <br />
            System<span className="text-swiss-accent">.</span>
          </h1>
        </div>
        <p className="max-w-sm text-sm text-black/60">
          Distributed job scheduling &mdash; queues, workers, retries, and dead letter handling in one place.
        </p>
      </div>

      {/* Right: form, 5/12 */}
      <div className="flex flex-col justify-center p-8 md:col-span-5 md:p-16">
        <SectionLabel index={2}>{mode === 'login' ? 'Log In' : 'Register'}</SectionLabel>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1 block text-xs font-bold tracking-widest uppercase">Email</label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-bold tracking-widest uppercase">Password</label>
            <Input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {mode === 'register' && (
            <>
              <div>
                <label className="mb-1 block text-xs font-bold tracking-widest uppercase">Full name</label>
                <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-bold tracking-widest uppercase">Organization</label>
                <Input required value={orgName} onChange={(e) => setOrgName(e.target.value)} />
              </div>
            </>
          )}
          {error && (
            <p className="border-2 border-swiss-accent bg-swiss-accent/5 px-3 py-2 text-sm text-swiss-accent">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="mt-2 h-12">
            {mode === 'login' ? 'Log In' : 'Create Account'}
          </Button>
        </form>
        <button
          className="swiss-focusable mt-4 text-left text-xs font-bold tracking-widest text-black/60 uppercase hover:text-swiss-accent"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
        >
          {mode === 'login' ? 'Need an account? Register →' : '← Already have an account? Log in'}
        </button>
      </div>
    </div>
  )
}
