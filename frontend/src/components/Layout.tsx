import { Music2, Sparkles, History } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "../lib/utils";

const navItems = [
  { to: "/", label: "首页", icon: Music2, end: true },
  { to: "/generate", label: "创作", icon: Sparkles },
  { to: "/history", label: "历史", icon: History },
];

export default function Layout() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(1200px 600px at 10% -10%, rgba(124,58,237,0.18), transparent 60%), radial-gradient(900px 500px at 110% 10%, rgba(59,130,246,0.12), transparent 60%), linear-gradient(180deg, #020617 0%, #0b1024 60%, #020617 100%)",
        }}
      />
      <header className="sticky top-0 z-30 border-b border-slate-800/70 bg-slate-950/70 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <NavLink to="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
              <Music2 className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold leading-tight text-white">
                会唱歌的数字人
              </span>
              <span className="text-xs text-slate-400">
                Singing Digital Human
              </span>
            </div>
          </NavLink>
          <nav className="flex items-center gap-1">
            {navItems.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-brand-500/15 text-brand-200 ring-1 ring-brand-500/30"
                      : "text-slate-300 hover:bg-slate-800/60 hover:text-white",
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-6 py-10">
        <Outlet />
      </main>
      <footer className="border-t border-slate-800/70 py-6 text-center text-xs text-slate-500">
        © {new Date().getFullYear()} 会唱歌的数字人 · Wav2Lip-ONNX + DirectML
      </footer>
    </div>
  );
}
