import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient";

export default function Teachers() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    supabase
      .from("teachers")
      .select("*")
      .order("full_name")
      .then(({ data, error }) => {
        if (error) setError(error.message);
        setRows(data || []);
        setLoading(false);
      });
  }, []);

  return (
    <div>
      <div className="summary">
        {loading ? "Loading…" : `${rows.length} teachers`} (managed in the desktop app)
      </div>
      {error && <div className="error">{error}</div>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Code</th>
              <th>Department</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td>{t.full_name}</td>
                <td>{t.employee_code ?? "—"}</td>
                <td>{t.department ?? "—"}</td>
                <td>{t.email ?? "—"}</td>
                <td>{t.phone ?? "—"}</td>
                <td className={t.active ? "present" : "muted"}>
                  {t.active ? "Active" : "Inactive"}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan="6" className="muted center-cell">
                  No teachers yet. Add them in the desktop app and sync.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
