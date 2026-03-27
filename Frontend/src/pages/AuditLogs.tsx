import { FormEvent, useEffect, useState } from "react";

import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import { fetchAuditLogs, AuditLogItem } from "../api/platformOpsApi";
import { isStoredCampusAdmin } from "../lib/auth/storedUser";

const AuditLogs = () => {
  const isSchoolIT = isStoredCampusAdmin();
  const NavbarComponent = isSchoolIT ? NavbarSchoolIT : NavbarAdmin;

  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [statusValue, setStatusValue] = useState("");

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLogs({
        q: q || undefined,
        action: action || undefined,
        status: statusValue || undefined,
        limit: 100,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await loadLogs();
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa" }}>
      <NavbarComponent />
      <main className="container py-4">
        <h2 className="mb-3">Audit Logs</h2>
        <form className="row g-2 mb-3" onSubmit={onSubmit}>
          <div className="col-md-5">
            <input
              className="form-control"
              placeholder="Search action/status/details"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="col-md-3">
            <input
              className="form-control"
              placeholder="Action filter"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            />
          </div>
          <div className="col-md-2">
            <input
              className="form-control"
              placeholder="Status filter"
              value={statusValue}
              onChange={(e) => setStatusValue(e.target.value)}
            />
          </div>
          <div className="col-md-2 d-grid">
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? "Loading..." : "Search"}
            </button>
          </div>
        </form>

        {error && <div className="alert alert-danger">{error}</div>}
        {!error && <p className="text-muted">Total results: {total}</p>}

        <div className="table-responsive bg-white border rounded">
          <table className="table table-striped table-sm mb-0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Action</th>
                <th>Status</th>
                <th>Actor</th>
                <th>Created</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.action}</td>
                  <td>{item.status}</td>
                  <td>{item.actor_user_id ?? "-"}</td>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td style={{ maxWidth: 460, whiteSpace: "pre-wrap" }}>
                    {item.details_json ? JSON.stringify(item.details_json) : item.details || "-"}
                  </td>
                </tr>
              ))}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-4">
                    No logs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
};

export default AuditLogs;
