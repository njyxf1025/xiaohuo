import { NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
  const navItems = [
    { to: '/', label: '首页', icon: '🏠' },
    { to: '/create', label: '生成', icon: '🎬' },
    { to: '/history', label: '历史', icon: '📋' },
  ]

  return (
    <div className="min-h-screen bg-[#0f1117] text-gray-100 flex flex-col pb-16 md:pb-0">
      <nav className="sticky top-0 z-50 bg-[#161822]/80 backdrop-blur-xl border-b border-white/5 hidden md:block">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🎤</span>
              <span className="text-lg font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                会唱歌的数字人
              </span>
            </div>
            <div className="flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-purple-500/20 text-purple-300 shadow-lg shadow-purple-500/10'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                    }`
                  }
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      </nav>

      <nav className="fixed bottom-0 left-0 right-0 z-50 bg-[#161822]/90 backdrop-blur-xl border-t border-white/5 md:hidden safe-bottom">
        <div className="flex items-center justify-around h-14">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                  isActive
                    ? 'text-purple-300'
                    : 'text-gray-500 hover:text-gray-300'
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}
