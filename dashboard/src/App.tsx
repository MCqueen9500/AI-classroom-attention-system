// src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Admin } from './pages/Admin'
import { History } from './pages/History'
import { Analytics } from './pages/Analytics'
import { Roster } from './pages/Roster'
import { Registration } from './pages/Registration'
import { Navbar } from './components/Navbar'
import { Sidebar } from './components/Sidebar'

function ProtectedLayout({ adminOnly = false }: { adminOnly?: boolean }) {
  const { user } = useAuth()

  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && !user?.is_admin) return <Navigate to="/dashboard" replace />
  if (!adminOnly && user?.is_admin) return <Navigate to="/admin" replace />

  return (
    <div className="min-h-screen bg-ivory text-blue flex flex-col font-sans">
      <Navbar />
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 relative">
           {/* Decorative background grid/lines for the main content area */}
           <div className="absolute inset-0 pointer-events-none opacity-5"
                style={{ backgroundImage: 'linear-gradient(#1A3C61 1px, transparent 1px), linear-gradient(90deg, #1A3C61 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
           
           <div className="relative z-10 h-full w-full max-w-[1600px] mx-auto">
             <Routes>
               {adminOnly ? (
                 <Route path="/" element={<Admin />} />
               ) : (
                 <>
                   <Route path="/dashboard" element={<Dashboard />} />
                   <Route path="/history" element={<History />} />
                   <Route path="/analytics" element={<Analytics />} />
                   <Route path="/roster" element={<Roster />} />
                   <Route path="/" element={<Navigate to="/dashboard" replace />} />
                 </>
               )}
             </Routes>
           </div>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Registration />} />
          
          <Route path="/admin/*" element={<ProtectedLayout adminOnly={true} />} />
          <Route path="/*" element={<ProtectedLayout adminOnly={false} />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
