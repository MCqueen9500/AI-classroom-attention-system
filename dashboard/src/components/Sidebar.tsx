import { Link, useLocation } from 'react-router-dom'

export function Sidebar() {
  const location = useLocation()
  
  const links = [
    { path: '/dashboard', label: 'Live Dashboard' },
    { path: '/analytics', label: 'Analytics' },
    { path: '/history', label: 'History' },
    { path: '/roster', label: 'Roster' },
    { path: '/students', label: 'Registration' },
  ]

  return (
    <aside className="app-sidebar-nav">
      <nav>
        {links.map(link => (
          <Link 
            key={link.path} 
            to={link.path}
            className={`nav-link ${location.pathname === link.path ? 'active' : ''}`}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
