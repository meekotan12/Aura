import { useEffect, useRef, useState } from "react";
import { FaDownload, FaFileExcel, FaRedoAlt, FaTrashAlt, FaUpload } from "react-icons/fa";

import NavbarSchoolIT from "../components/NavbarSchoolIT";
import {
  downloadImportErrors,
  downloadPreviewImportErrors,
  downloadPreviewRetryFile,
  downloadUserImportTemplate,
  getImportStatus,
  importUsersFromExcel,
  ImportPreviewSummary,
  previewImportUsersFromExcel,
  removeInvalidPreviewRows,
  retryFailedImportRows,
  UserImportSummary,
} from "../api/schoolSettingsApi";

const POLL_INTERVAL_MS = 1500;

const SchoolImportUsers = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloadingTemplate, setDownloadingTemplate] = useState(false);
  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [downloadingPreviewErrors, setDownloadingPreviewErrors] = useState(false);
  const [downloadingPreviewRetryFile, setDownloadingPreviewRetryFile] = useState(false);
  const [cleaningPreview, setCleaningPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<UserImportSummary | null>(null);
  const [preview, setPreview] = useState<ImportPreviewSummary | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = (queuedJobId: string) => {
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const status = await getImportStatus(queuedJobId);
        setSummary(status);
        if (status.state === "completed" || status.state === "failed") {
          stopPolling();
          setLoading(false);
        }
      } catch (err) {
        stopPolling();
        setLoading(false);
        setError(err instanceof Error ? err.message : "Failed to poll import status.");
      }
    }, POLL_INTERVAL_MS);
  };

  const handleDownloadTemplate = async () => {
    setDownloadingTemplate(true);
    setError(null);
    try {
      await downloadUserImportTemplate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download template.");
    } finally {
      setDownloadingTemplate(false);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setError("Please select an Excel (.xlsx) file first.");
      return;
    }
    if (!preview) {
      setError("Preview the file first before importing.");
      return;
    }
    if (!preview.preview_token) {
      setError("Preview token is missing. Preview the file again before importing.");
      return;
    }
    if (!preview.can_commit) {
      setError("Fix preview errors before importing.");
      return;
    }

    setLoading(true);
    setError(null);
    setSummary(null);

    try {
      const job = await importUsersFromExcel(preview.preview_token);
      setJobId(job.job_id);
      startPolling(job.job_id);
    } catch (err) {
      setLoading(false);
      setError(err instanceof Error ? err.message : "Failed to import users.");
    }
  };

  const handlePreview = async () => {
    if (!selectedFile) {
      setError("Please select an Excel (.xlsx) file first.");
      return;
    }

    setPreviewing(true);
    setError(null);
    setPreview(null);
    setSummary(null);

    try {
      const result = await previewImportUsersFromExcel(selectedFile);
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview file.");
    } finally {
      setPreviewing(false);
    }
  };

  const handleDownloadPreviewErrors = async () => {
    if (!preview?.preview_token) return;

    setDownloadingPreviewErrors(true);
    setError(null);
    try {
      await downloadPreviewImportErrors(preview.preview_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download preview errors.");
    } finally {
      setDownloadingPreviewErrors(false);
    }
  };

  const handleDownloadPreviewRetryFile = async () => {
    if (!preview?.preview_token) return;

    setDownloadingPreviewRetryFile(true);
    setError(null);
    try {
      await downloadPreviewRetryFile(preview.preview_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download preview retry file.");
    } finally {
      setDownloadingPreviewRetryFile(false);
    }
  };

  const handleRemoveInvalidRows = async () => {
    if (!preview?.preview_token) return;
    if (preview.valid_rows <= 0) {
      setError("Remove Invalid Rows needs at least one valid preview row to keep.");
      return;
    }

    setCleaningPreview(true);
    setError(null);
    try {
      const cleanedPreview = await removeInvalidPreviewRows(preview.preview_token);
      setPreview(cleanedPreview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove invalid preview rows.");
    } finally {
      setCleaningPreview(false);
    }
  };

  const handleDownloadErrors = async () => {
    if (!jobId) return;

    setDownloadingErrors(true);
    setError(null);
    try {
      await downloadImportErrors(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download failed rows report.");
    } finally {
      setDownloadingErrors(false);
    }
  };

  const handleRetryFailedRows = async () => {
    if (!jobId) return;
    setRetrying(true);
    setError(null);
    try {
      const job = await retryFailedImportRows(jobId);
      setJobId(job.job_id);
      setSummary(null);
      setPreview(null);
      startPolling(job.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retry failed rows.");
    } finally {
      setRetrying(false);
    }
  };

  const canRemoveInvalidRows =
    Boolean(preview?.preview_token) &&
    (preview?.invalid_rows ?? 0) > 0 &&
    (preview?.valid_rows ?? 0) > 0;

  return (
    <div style={{ minHeight: "100vh", background: "#f5f7fa" }}>
      <NavbarSchoolIT />

      <main className="container py-4">
        <div className="card border-0 shadow-sm">
          <div className="card-body">
            <h3 className="mb-2">Import Students via Excel</h3>
            <p className="text-muted">
              Upload your student sheet. Imported accounts are created as students in your own
              campus automatically, and officer assignments happen later from Manage SSG.
            </p>

            <div className="d-flex flex-wrap gap-2 mb-3">
              <button
                className="btn btn-outline-secondary"
                onClick={handleDownloadTemplate}
                disabled={downloadingTemplate}
              >
                <FaDownload className="me-2" />
                {downloadingTemplate ? "Downloading..." : "Download Template"}
              </button>

              <label className="btn btn-outline-primary mb-0">
                <FaFileExcel className="me-2" />
                {selectedFile ? selectedFile.name : "Choose .xlsx File"}
                <input
                  type="file"
                  accept=".xlsx"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0] || null;
                    setSelectedFile(file);
                    setPreview(null);
                    setSummary(null);
                    setError(null);
                  }}
                />
              </label>

              <button className="btn btn-outline-primary" onClick={handlePreview} disabled={previewing || loading}>
                {previewing ? "Previewing..." : "Preview File"}
              </button>

              <button
                className="btn btn-primary"
                onClick={handleImport}
                disabled={loading || previewing || !preview?.can_commit}
                style={{
                  backgroundColor: "var(--primary-color, #162F65)",
                  borderColor: "var(--primary-color, #162F65)",
                }}
              >
                <FaUpload className="me-2" />
                {loading ? "Processing..." : "Import Approved Rows"}
              </button>
            </div>

            {preview && (
              <div className="mt-3">
                <div className={`alert ${preview.can_commit ? "alert-success" : "alert-warning"}`}>
                  <strong>Preview:</strong> {preview.valid_rows} valid, {preview.invalid_rows} invalid (total{" "}
                  {preview.total_rows}).
                  {!preview.can_commit && " Please fix invalid rows before importing."}
                </div>

                {preview.invalid_rows > 0 && preview.preview_token && (
                  <div className="d-flex flex-wrap gap-2 mb-3">
                    <button
                      className="btn btn-outline-danger"
                      onClick={handleDownloadPreviewErrors}
                      disabled={downloadingPreviewErrors || cleaningPreview}
                      type="button"
                    >
                      <FaDownload className="me-2" />
                      {downloadingPreviewErrors ? "Downloading..." : "Download Errors"}
                    </button>
                    <button
                      className="btn btn-outline-secondary"
                      onClick={handleDownloadPreviewRetryFile}
                      disabled={downloadingPreviewRetryFile || cleaningPreview}
                      type="button"
                    >
                      <FaRedoAlt className="me-2" />
                      {downloadingPreviewRetryFile ? "Preparing..." : "Retry File"}
                    </button>
                    <button
                      className="btn btn-outline-primary"
                      onClick={handleRemoveInvalidRows}
                      disabled={cleaningPreview || !canRemoveInvalidRows}
                      type="button"
                    >
                      <FaTrashAlt className="me-2" />
                      {cleaningPreview ? "Removing..." : "Remove Invalid Rows"}
                    </button>
                  </div>
                )}

                {preview.invalid_rows > 0 && preview.valid_rows === 0 && (
                  <div className="alert alert-secondary py-2">
                    Remove Invalid Rows becomes available after the preview has at least one valid
                    row to keep.
                  </div>
                )}

                {preview.can_commit && (
                  <div className="alert alert-success py-2">
                    Approved preview is ready. Use <strong>Import Approved Rows</strong> to continue.
                  </div>
                )}

                <div className="table-responsive">
                  <table className="table table-sm table-bordered align-middle">
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Status</th>
                        <th>Errors</th>
                        <th>Suggestions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.slice(0, 30).map((row) => (
                        <tr key={`${row.row}-${row.status}`}>
                          <td>{row.row}</td>
                          <td>{row.status}</td>
                          <td>{row.errors.join("; ") || "-"}</td>
                          <td>{row.suggestions.join(" | ") || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {error && (
              <div className="alert alert-danger mb-3" role="alert">
                {error}
              </div>
            )}

            {summary && (
              <div className="mt-3">
                <div className="alert alert-info" role="alert">
                  <strong>Job State:</strong> {summary.state} <br />
                  <strong>Progress:</strong> {summary.processed_rows}/{summary.total_rows} ({summary.percentage_completed}%)
                  <br />
                  <strong>Result:</strong> {summary.success_count} success, {summary.failed_count} failed
                </div>

                {summary.failed_count > 0 && (
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <h6 className="mb-0">Row Errors</h6>
                    <div className="d-flex gap-2">
                      <button
                        className="btn btn-sm btn-outline-danger"
                        onClick={handleDownloadErrors}
                        disabled={downloadingErrors || !jobId}
                      >
                        {downloadingErrors ? "Downloading..." : "Download Failed Rows"}
                      </button>
                      <button
                        className="btn btn-sm btn-outline-primary"
                        onClick={handleRetryFailedRows}
                        disabled={retrying || !jobId}
                      >
                        {retrying ? "Retrying..." : "Retry Failed Rows"}
                      </button>
                    </div>
                  </div>
                )}

                {summary.errors.length > 0 && (
                  <div className="table-responsive">
                    <table className="table table-sm table-bordered align-middle">
                      <thead>
                        <tr>
                          <th>Row</th>
                          <th>Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.errors.map((row) => (
                          <tr key={`${row.row}-${row.error}`}>
                            <td>{row.row}</td>
                            <td>{row.error}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default SchoolImportUsers;
