import { useEffect, useRef, useState } from "react";
import {
  FaCamera,
  FaCheckCircle,
  FaCompass,
  FaMapMarkerAlt,
  FaPauseCircle,
  FaPlayCircle,
  FaRedoAlt,
  FaUsers,
} from "react-icons/fa";

import CameraFeed, { type CameraFeedStats } from "./CameraFeed";
import {
  describePublicAttendanceError,
  fetchNearbyPublicAttendanceEvents,
  submitPublicAttendanceScan,
  type PublicAttendanceEventSummary,
  type PublicAttendanceFaceOutcome,
} from "../api/publicAttendanceApi";
import "../css/PublicAttendanceKiosk.css";

type LocationSnapshot = {
  latitude: number;
  longitude: number;
  accuracyM?: number | null;
  resolvedAt: string;
};

type StatusTone = "info" | "success" | "error";

type CooldownEntry = {
  studentId: string;
  studentName: string | null;
  expiresAt: number;
};

const INITIAL_CAMERA_STATS: CameraFeedStats = {
  requestsPerSecond: 0,
  pageVisible: true,
  networkBackoffMs: 0,
};

const SUCCESS_ACTIONS = new Set<PublicAttendanceFaceOutcome["action"]>([
  "time_in",
  "time_out",
]);

const COOLDOWN_ACTIONS = new Set<PublicAttendanceFaceOutcome["action"]>([
  "time_in",
  "time_out",
  "already_signed_in",
  "already_signed_out",
  "cooldown_skipped",
]);

const getCurrentPosition = () =>
  new Promise<GeolocationPosition>((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported on this browser."));
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    });
  });

const formatDateTime = (value: string) =>
  new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

const formatDistance = (value?: number | null) =>
  typeof value === "number" ? `${value.toFixed(value < 10 ? 1 : 0)} m` : "N/A";

const formatCooldownSeconds = (expiresAt: number) =>
  Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));

const phaseLabel = (phase: "sign_in" | "sign_out") =>
  phase === "sign_in" ? "Sign in" : "Sign out";

const outcomeToneClass = (action: PublicAttendanceFaceOutcome["action"]) => {
  if (SUCCESS_ACTIONS.has(action)) {
    return "is-success";
  }

  if (
    action === "liveness_failed" ||
    action === "out_of_scope" ||
    action === "no_match" ||
    action === "rejected"
  ) {
    return "is-error";
  }

  return "is-info";
};

const statusToneFromOutcomes = (outcomes: PublicAttendanceFaceOutcome[]): StatusTone => {
  if (outcomes.some((outcome) => SUCCESS_ACTIONS.has(outcome.action))) {
    return "success";
  }

  if (
    outcomes.some((outcome) =>
      ["liveness_failed", "out_of_scope", "no_match", "rejected"].includes(outcome.action),
    )
  ) {
    return "error";
  }

  return "info";
};

const primaryOutcomeMessage = (outcomes: PublicAttendanceFaceOutcome[], fallback: string) => {
  const priority = outcomes.find((outcome) => SUCCESS_ACTIONS.has(outcome.action));
  if (priority) {
    return priority.message;
  }

  return outcomes[0]?.message ?? fallback;
};

const PublicAttendanceKiosk = () => {
  const [location, setLocation] = useState<LocationSnapshot | null>(null);
  const [locationMessage, setLocationMessage] = useState(
    "Allow location access to load nearby public attendance events.",
  );
  const [isRefreshingLocation, setIsRefreshingLocation] = useState(false);
  const [nearbyEvents, setNearbyEvents] = useState<PublicAttendanceEventSummary[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [scanCooldownSeconds, setScanCooldownSeconds] = useState(8);
  const [scanStatus, setScanStatus] = useState(
    "Pick a nearby event, start the camera, then arm the live scan.",
  );
  const [scanStatusTone, setScanStatusTone] = useState<StatusTone>("info");
  const [cameraOn, setCameraOn] = useState(false);
  const [scanArmed, setScanArmed] = useState(false);
  const [cameraStats, setCameraStats] = useState<CameraFeedStats>(INITIAL_CAMERA_STATS);
  const [outcomes, setOutcomes] = useState<PublicAttendanceFaceOutcome[]>([]);
  const [cooldownEntries, setCooldownEntries] = useState<CooldownEntry[]>([]);
  const [lastScanAt, setLastScanAt] = useState<string | null>(null);

  const cooldownByStudentRef = useRef<Record<string, CooldownEntry>>({});

  const selectedEvent =
    nearbyEvents.find((event) => event.id === selectedEventId) ?? null;

  const syncCooldownEntries = () => {
    const now = Date.now();
    const nextEntries = Object.values(cooldownByStudentRef.current)
      .filter((entry) => entry.expiresAt > now)
      .sort((left, right) => left.expiresAt - right.expiresAt);

    cooldownByStudentRef.current = Object.fromEntries(
      nextEntries.map((entry) => [entry.studentId, entry]),
    );
    setCooldownEntries(nextEntries);
    return nextEntries.map((entry) => entry.studentId);
  };

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      syncCooldownEntries();
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (!cameraOn) {
      setScanArmed(false);
    }
  }, [cameraOn]);

  const loadNearbyEvents = async () => {
    setIsRefreshingLocation(true);
    setScanStatusTone("info");
    setScanStatus("Finding your location and loading nearby attendance events...");

    try {
      const position = await getCurrentPosition();
      const nextLocation: LocationSnapshot = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracyM: position.coords.accuracy,
        resolvedAt: new Date().toISOString(),
      };
      const response = await fetchNearbyPublicAttendanceEvents(nextLocation);

      setLocation(nextLocation);
      setLocationMessage(
        `Location updated at ${formatDateTime(nextLocation.resolvedAt)} with ${formatDistance(
          nextLocation.accuracyM,
        )} accuracy.`,
      );
      setNearbyEvents(response.events);
      setScanCooldownSeconds(response.scan_cooldown_seconds);
      setSelectedEventId((currentId) => {
        if (currentId && response.events.some((event) => event.id === currentId)) {
          return currentId;
        }

        return response.events[0]?.id ?? null;
      });
      setOutcomes([]);

      if (response.events.length === 0) {
        setScanStatus("No nearby public attendance events are open for scanning right now.");
      } else {
        setScanStatus(
          `Found ${response.events.length} nearby event${
            response.events.length === 1 ? "" : "s"
          }. Select one to start the public kiosk.`,
        );
      }
    } catch (error) {
      setNearbyEvents([]);
      setSelectedEventId(null);
      setScanArmed(false);
      setLocationMessage(describePublicAttendanceError(error));
      setScanStatus(describePublicAttendanceError(error));
      setScanStatusTone("error");
    } finally {
      setIsRefreshingLocation(false);
    }
  };

  const handleSelectEvent = (event: PublicAttendanceEventSummary) => {
    setSelectedEventId(event.id);
    setOutcomes([]);
    setLastScanAt(null);
    setScanArmed(false);
    setScanStatus(event.phase_message);
    setScanStatusTone("info");
  };

  const handleFrame = async (imageBlob: Blob) => {
    if (!selectedEvent || !location) {
      return;
    }

    const activeCooldownStudentIds = syncCooldownEntries();

    try {
      const response = await submitPublicAttendanceScan({
        eventId: selectedEvent.id,
        imageBlob,
        location,
        cooldownStudentIds: activeCooldownStudentIds,
      });

      const now = Date.now();
      const nextCooldowns = { ...cooldownByStudentRef.current };
      for (const outcome of response.outcomes) {
        if (!outcome.student_id || !COOLDOWN_ACTIONS.has(outcome.action)) {
          continue;
        }

        nextCooldowns[outcome.student_id] = {
          studentId: outcome.student_id,
          studentName: outcome.student_name ?? null,
          expiresAt: now + response.scan_cooldown_seconds * 1000,
        };
      }

      cooldownByStudentRef.current = nextCooldowns;
      syncCooldownEntries();
      setScanCooldownSeconds(response.scan_cooldown_seconds);
      setOutcomes(response.outcomes);
      setLastScanAt(new Date().toISOString());
      setScanStatus(primaryOutcomeMessage(response.outcomes, response.message));
      setScanStatusTone(statusToneFromOutcomes(response.outcomes));
    } catch (error) {
      setScanStatus(describePublicAttendanceError(error));
      setScanStatusTone("error");
    }
  };

  return (
    <section className="public-attendance-kiosk">
      <div className="public-attendance-kiosk__header">
        <div>
          <span className="public-attendance-kiosk__eyebrow">
            <FaUsers />
            Public Attendance
          </span>
          <h2>Public Face Attendance Kiosk</h2>
          <p>
            Nearby geofenced events can record student sign in and sign out from the
            landing page without logging students into the web app.
          </p>
        </div>
        <button
          type="button"
          className="public-attendance-kiosk__refresh"
          onClick={loadNearbyEvents}
          disabled={isRefreshingLocation}
        >
          <FaRedoAlt />
          {isRefreshingLocation ? "Locating..." : "Find Nearby Events"}
        </button>
      </div>

      <div className="public-attendance-kiosk__steps">
        <div className="public-attendance-kiosk__step">
          <strong>1. Share location</strong>
          <span>{locationMessage}</span>
        </div>
        <div className="public-attendance-kiosk__step">
          <strong>2. Choose event</strong>
          <span>
            {selectedEvent
              ? `${selectedEvent.name} is ready for ${phaseLabel(selectedEvent.attendance_phase).toLowerCase()}.`
              : "Select a nearby event after loading location."}
          </span>
        </div>
        <div className="public-attendance-kiosk__step">
          <strong>3. Scan faces</strong>
          <span>{scanStatus}</span>
        </div>
      </div>

      <div className="public-attendance-kiosk__layout">
        <div className="public-attendance-kiosk__events">
          <div className="public-attendance-kiosk__panel-title">
            <FaMapMarkerAlt />
            <span>Nearby Events</span>
          </div>

          {nearbyEvents.length === 0 ? (
            <div className="public-attendance-kiosk__empty">
              Use <strong>Find Nearby Events</strong> to load active public attendance
              events for your current location.
            </div>
          ) : (
            <div className="public-attendance-kiosk__event-list">
              {nearbyEvents.map((event) => {
                const isSelected = event.id === selectedEventId;
                return (
                  <button
                    key={event.id}
                    type="button"
                    className={`public-attendance-kiosk__event-card${
                      isSelected ? " is-selected" : ""
                    }`}
                    onClick={() => handleSelectEvent(event)}
                  >
                    <div className="public-attendance-kiosk__event-top">
                      <strong>{event.name}</strong>
                      <span className={`public-attendance-kiosk__phase phase-${event.attendance_phase}`}>
                        {phaseLabel(event.attendance_phase)}
                      </span>
                    </div>
                    <p>{event.school_name}</p>
                    <p>{event.location}</p>
                    <div className="public-attendance-kiosk__event-meta">
                      <span>{formatDateTime(event.start_datetime)}</span>
                      <span>{formatDistance(event.distance_m)} away</span>
                    </div>
                    <div className="public-attendance-kiosk__event-scope">
                      <FaCompass />
                      <span>{event.scope_label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="public-attendance-kiosk__scanner">
          <div className="public-attendance-kiosk__panel-title">
            <FaCamera />
            <span>Live Camera Scanner</span>
          </div>

          <div className="public-attendance-kiosk__scanner-card">
            <div className="public-attendance-kiosk__scanner-meta">
              <div>
                <strong>{selectedEvent?.name ?? "No event selected"}</strong>
                <span>
                  {selectedEvent
                    ? `${phaseLabel(selectedEvent.attendance_phase)} is active for ${selectedEvent.scope_label}.`
                    : "Choose a nearby event to activate the kiosk scanner."}
                </span>
              </div>

              <button
                type="button"
                className={`public-attendance-kiosk__arm-button${
                  scanArmed ? " is-armed" : ""
                }`}
                onClick={() => setScanArmed((current) => !current)}
                disabled={!selectedEvent || !location || !cameraOn}
              >
                {scanArmed ? <FaPauseCircle /> : <FaPlayCircle />}
                {scanArmed ? "Pause Scan" : "Arm Live Scan"}
              </button>
            </div>

            <CameraFeed
              autoStart={false}
              showControls
              streamEnabled={undefined}
              scanEnabled={Boolean(selectedEvent && location && cameraOn && scanArmed)}
              scanIntervalMs={1100}
              onFrame={handleFrame}
              onCameraStateChange={setCameraOn}
              onStatsChange={setCameraStats}
              onScanError={(error) => {
                setScanStatus(describePublicAttendanceError(error));
                setScanStatusTone("error");
              }}
              placeholderText="Start the camera, keep the device inside the event geofence, and arm the live scan."
            />

            <div className={`public-attendance-kiosk__status status-${scanStatusTone}`}>
              {scanStatusTone === "success" ? <FaCheckCircle /> : <FaCompass />}
              <span>{scanStatus}</span>
            </div>

            <div className="public-attendance-kiosk__metrics">
              <div>
                <span>Location accuracy</span>
                <strong>{formatDistance(location?.accuracyM)}</strong>
              </div>
              <div>
                <span>Scan cooldown</span>
                <strong>{scanCooldownSeconds}s</strong>
              </div>
              <div>
                <span>Scan rate</span>
                <strong>{cameraStats.requestsPerSecond.toFixed(1)}/s</strong>
              </div>
              <div>
                <span>Backoff</span>
                <strong>{cameraStats.networkBackoffMs} ms</strong>
              </div>
            </div>
          </div>

          <div className="public-attendance-kiosk__results">
            <div className="public-attendance-kiosk__results-header">
              <strong>Latest Scan Outcomes</strong>
              <span>{lastScanAt ? `Updated ${formatDateTime(lastScanAt)}` : "Waiting for first scan"}</span>
            </div>

            {outcomes.length === 0 ? (
              <div className="public-attendance-kiosk__empty">
                Live scan outcomes will appear here after the first processed frame.
              </div>
            ) : (
              <div className="public-attendance-kiosk__outcome-list">
                {outcomes.map((outcome, index) => (
                  <article
                    key={`${outcome.student_id ?? "unknown"}-${outcome.action}-${index}`}
                    className={`public-attendance-kiosk__outcome ${outcomeToneClass(outcome.action)}`}
                  >
                    <div className="public-attendance-kiosk__outcome-top">
                      <strong>{outcome.student_name ?? "Unmatched face"}</strong>
                      <span>{outcome.action.replace(/_/g, " ")}</span>
                    </div>
                    {outcome.student_id ? <small>{outcome.student_id}</small> : null}
                    <p>{outcome.message}</p>
                    <div className="public-attendance-kiosk__outcome-meta">
                      <span>Confidence: {typeof outcome.confidence === "number" ? outcome.confidence.toFixed(3) : "N/A"}</span>
                      <span>Liveness: {outcome.liveness?.label ?? "N/A"}</span>
                      <span>Distance: {formatDistance(outcome.distance)}</span>
                    </div>
                  </article>
                ))}
              </div>
            )}

            {cooldownEntries.length > 0 ? (
              <div className="public-attendance-kiosk__cooldowns">
                <strong>Cooldown Window</strong>
                <div className="public-attendance-kiosk__cooldown-list">
                  {cooldownEntries.map((entry) => (
                    <span key={entry.studentId}>
                      {(entry.studentName || entry.studentId).trim()} - {formatCooldownSeconds(entry.expiresAt)}s
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
};

export default PublicAttendanceKiosk;
