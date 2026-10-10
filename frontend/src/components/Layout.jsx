import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { ShieldCheck, Moon, Sun } from "@phosphor-icons/react";

export default function Layout() {
  const [theme, setTheme] = useState(document.documentElement.getAttribute("data-theme") || "light");

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch { /* storage unavailable */ }
    setTheme(next);
  };

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="wordmark">
            <ShieldCheck size={24} weight="fill" aria-hidden="true" />
            <span>SCC Triage Hub</span>
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>Dashboard</NavLink>
            <NavLink to="/findings">Findings</NavLink>
            <NavLink to="/help">How to use</NavLink>
          </nav>
          <button
            className="btn btn-quiet btn-icon"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          >
            {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}

export function PageHead({ eyebrow, title, subtitle, mono, children }) {
  return (
    <div className="page-head spread">
      <div>
        <p className={mono ? "eyebrow id" : "eyebrow"}>{eyebrow}</p>
        <h1>{title}</h1>
        {subtitle && <p className="subtitle">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
