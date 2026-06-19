import { useEffect, useState } from "react";
import { supabase, isConfigured } from "./supabaseClient";
import Login from "./Login.jsx";
import Attendance from "./Attendance.jsx";
import Teachers from "./Teachers.jsx";

export default function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("attendance");

  useEffect(() => {
    if (!isConfigured) {
      setLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!isConfigured) {
    return (
      <div className="center">
        <div className="card">
          <h2>Not configured</h2>
          <p className="muted">
            Create a <code>.env</code> file (see <code>.env.example</code>) with your
            Supabase URL and anon key, then restart the dev server.
          </p>
        </div>
      </div>
    );
  }

  if (loading) return <div className="center muted">Loading…</div>;
  if (!session) return <Login />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">📷 Attendance Dashboard</div>
        <nav className="tabs">
          <button className={tab === "attendance" ? "active" : ""} onClick={() => setTab("attendance")}>
            Attendance
          </button>
          <button className={tab === "teachers" ? "active" : ""} onClick={() => setTab("teachers")}>
            Teachers
          </button>
        </nav>
        <div className="user">
          <span className="muted">{session.user.email}</span>
          <button className="ghost" onClick={() => supabase.auth.signOut()}>
            Sign out
          </button>
        </div>
      </header>
      <main className="content">
        {tab === "attendance" ? <Attendance /> : <Teachers />}
      </main>
    </div>
  );
}
