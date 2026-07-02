import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Button from './ui/Button'

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-white text-black">
      <header className="border-b-4 border-black">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 md:px-12">
          <Link to="/projects" className="text-lg font-black tracking-tighter uppercase">
            Job Scheduler<span className="text-swiss-accent">.</span>
          </Link>
          {user && (
            <div className="flex items-center gap-4">
              <span className="hidden text-xs font-medium tracking-wide text-black/60 uppercase md:inline">
                {user.email}
              </span>
              <Button variant="secondary" onClick={logout} className="px-3 py-1.5">
                Log out
              </Button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-10 md:px-12 md:py-16">
        <Outlet />
      </main>
    </div>
  )
}
