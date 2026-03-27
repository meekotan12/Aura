import { useEffect, useState } from "react";
import { FaBell } from "react-icons/fa";

import {
  fetchMyNotifications,
  markNotificationsRead,
  NotificationItem,
} from "../api/notificationsApi";

const NotificationBell = () => {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMyNotifications();
      setItems(data.items);
      setUnreadCount(data.unread_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggle = async () => {
    const next = !open;
    setOpen(next);
    if (next) {
      await load();
    }
  };

  const handleMarkRead = async (ids: number[]) => {
    if (!ids.length) return;
    try {
      await markNotificationsRead(ids);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update notifications");
    }
  };

  const unreadIds = items.filter((item) => !item.is_read).map((item) => item.id);

  return (
    <div className="notification-bell">
      <button type="button" className="btn btn-light position-relative" onClick={handleToggle}>
        <FaBell />
        {unreadCount > 0 && (
          <span className="badge bg-danger position-absolute top-0 start-100 translate-middle">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notification-panel shadow">
          <div className="notification-panel-header">
            <strong>Notifications</strong>
            <button
              type="button"
              className="btn btn-sm btn-outline-primary"
              onClick={() => handleMarkRead(unreadIds)}
              disabled={unreadIds.length === 0}
            >
              Mark all read
            </button>
          </div>

          {loading ? (
            <div className="notification-panel-body">Loading...</div>
          ) : error ? (
            <div className="notification-panel-body text-danger">{error}</div>
          ) : items.length === 0 ? (
            <div className="notification-panel-body text-muted">No notifications yet.</div>
          ) : (
            <ul className="notification-list">
              {items.map((item) => (
                <li
                  key={item.id}
                  className={`notification-item ${item.is_read ? "read" : "unread"}`}
                  onClick={() => handleMarkRead([item.id])}
                >
                  <div className="notification-title">{item.title}</div>
                  <div className="notification-message">{item.message}</div>
                  <div className="notification-time">
                    {new Date(item.created_at).toLocaleString()}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
