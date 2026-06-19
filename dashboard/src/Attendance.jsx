import { useEffect, useMemo, useState } from "react";
import { supabase } from "./supabaseClient";
import { exportCsv, exportXlsx } from "./exporters";

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function Attendance() {
  const [teachers, setTeachers] = useState([]);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [start, setStart] = useState(isoDaysAgo(30));
  const [end, setEnd] = useState(isoDaysAgo(0));
  const [teacherId, setTeacherId] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    supabase
      .from("teachers")
      .select("id, full_name")
      .order("full_name")
      .then(({ data }) => setTeachers(data || []));
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    let q = supabase
      .from("attendance")
      .select(
        "id, check_type, timestamp, status, liveness_score, teacher_id, teachers(full_name, employee_code, department)"
      )
      .gte("timestamp", `${start}T00:00:00`)
      .lte("timestamp", `${end}T23:59:59`)
      .order("timestamp", { ascending: false });
    if (teacherId) q = q.eq("teacher_id", teacherId);
    if (status) q = q.eq("status", status);

    const { data, error } = await q;
    if (error) setError(error.message);
    setRows(data || []);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lateCount = useMemo(() => rows.filter((r) => r.status === "late").length, [rows]);

  const flat = () =>
    rows.map((r) => ({
      Teacher: r.teachers?.full_name ?? "",
      Code: r.teachers?.employee_code ?? "",
      Department: r.teachers?.department ?? "",
      Type: r.check_type?.toUpperCase() ?? "",
      Status: r.status ?? "",
      Timestamp: r.timestamp?.replace("T", " ").slice(0, 19) ?? "",
      Liveness: r.liveness_score ?? "",
    }));

  return (
    <div>
      <div className="filters">
        <label>
          From
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label>
          Teacher
          <select value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
            <option value="">All teachers</option>
            {teachers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="present">Present</option>
            <option value="late">Late</option>
          </select>
        </label>
        <button onClick={load}>Apply</button>
        <div className="spacer" />
        <button className="ghost" onClick={() => exportCsv(flat(), "attendance")}>
          Export CSV
        </button>
        <button onClick={() => exportXlsx(flat(), "attendance")}>Export Excel</button>
      </div>

      <div className="summary">
        {loading ? "Loading…" : `${rows.length} records · ${lateCount} late`}
      </div>
      {error && <div className="error">{error}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Teacher</th>
              <th>Dept</th>
              <th>Type</th>
              <th>Status</th>
              <th>Time</th>
              <th>Liveness</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.teachers?.full_name ?? "—"}</td>
                <td>{r.teachers?.department ?? "—"}</td>
                <td>{r.check_type?.toUpperCase()}</td>
                <td className={r.status === "late" ? "late" : "present"}>{r.status}</td>
                <td>{r.timestamp?.replace("T", "  ").slice(0, 19)}</td>
                <td>{r.liveness_score != null ? Number(r.liveness_score).toFixed(2) : "—"}</td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan="6" className="muted center-cell">
                  No records for this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
