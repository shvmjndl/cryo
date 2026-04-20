import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'

export default function App() {
  const { user, loading, login, signup, logout } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--color-cryo-bg)]">
        <div className="flex flex-col items-center gap-4">
          <div className="text-4xl font-bold text-[var(--color-cryo-accent)] font-mono tracking-widest">
            CRYO
          </div>
          <div className="flex gap-1">
            {[0, 1, 2].map(i => (
              <div
                key={i}
                className="w-2 h-2 rounded-full bg-[var(--color-cryo-accent)] animate-pulse-glow"
                style={{ animationDelay: `${i * 0.3}s` }}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <Routes>
      <Route
        path="/auth"
        element={user ? <Navigate to="/" /> : <AuthPage onLogin={login} onSignup={signup} />}
      />
      <Route
        path="/*"
        element={user ? <ChatPage user={user} onLogout={logout} /> : <Navigate to="/auth" />}
      />
    </Routes>
  )
}
