"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AWARENESS_STREAM_URL,
  acknowledgeObservationApi,
  fetchAwarenessStatus,
  fetchBriefing,
  fetchObservations,
} from "@/lib/api";
import { AwarenessSnapshot, Briefing, Observation } from "@/lib/types";

export interface UseAwarenessOptions {
  /** Called for observations the backend judged worth interrupting for. */
  onSpeak?: (spoken: string) => void;
  /** How often to refresh the hardware snapshot, in ms. */
  snapshotIntervalMs?: number;
}

export interface UseAwarenessReturn {
  observations: Observation[];
  snapshot: AwarenessSnapshot | null;
  activeConditions: string[];
  connected: boolean;
  dismiss: (observationId: string) => void;
  dismissAll: () => void;
  getBriefing: () => Promise<Briefing | null>;
}

/** How many unacknowledged observations to keep on screen at once. */
const MAX_VISIBLE = 4;

/**
 * Subscribes to what Jarvis notices about the machine.
 *
 * Live observations arrive over SSE; the snapshot is polled separately so the
 * UI still shows current telemetry when nothing noteworthy is happening.
 */
export function useAwareness({
  onSpeak,
  snapshotIntervalMs = 15000,
}: UseAwarenessOptions = {}): UseAwarenessReturn {
  const [observations, setObservations] = useState<Observation[]>([]);
  const [snapshot, setSnapshot] = useState<AwarenessSnapshot | null>(null);
  const [activeConditions, setActiveConditions] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);

  const onSpeakRef = useRef(onSpeak);
  useEffect(() => {
    onSpeakRef.current = onSpeak;
  }, [onSpeak]);

  const addObservation = useCallback((observation: Observation) => {
    setObservations((prev) => {
      // A newer observation of the same kind replaces the older one, so a
      // condition that escalates does not stack up two cards.
      const withoutKind = prev.filter((o) => o.kind !== observation.kind);
      if (observation.resolved) return withoutKind;
      return [...withoutKind, observation].slice(-MAX_VISIBLE);
    });
  }, []);

  // Live stream of observations.
  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") return;

    const source = new EventSource(AWARENESS_STREAM_URL);

    source.addEventListener("ready", () => setConnected(true));
    source.addEventListener("observation", (event) => {
      try {
        const observation = JSON.parse((event as MessageEvent).data) as Observation;
        addObservation(observation);
        if (observation.speak && observation.spoken) {
          onSpeakRef.current?.(observation.spoken);
        }
      } catch {
        /* a malformed frame must not kill the stream */
      }
    });
    source.onerror = () => setConnected(false);

    return () => {
      source.close();
      setConnected(false);
    };
  }, [addObservation]);

  // Snapshot polling, plus a backfill of anything noticed before we connected.
  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const status = await fetchAwarenessStatus();
        if (cancelled) return;
        setSnapshot(status.snapshot);
        setActiveConditions(status.monitor.active_conditions);
      } catch {
        /* the tray simply goes stale if the backend is down */
      }
    };

    void (async () => {
      await refresh();
      try {
        const recent = await fetchObservations(0, MAX_VISIBLE);
        if (cancelled) return;
        recent.observations
          .filter((o) => !o.acknowledged && !o.resolved)
          .forEach(addObservation);
      } catch {
        /* backfill is best-effort */
      }
    })();

    const timer = window.setInterval(refresh, snapshotIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [addObservation, snapshotIntervalMs]);

  const dismiss = useCallback((observationId: string) => {
    setObservations((prev) => prev.filter((o) => o.id !== observationId));
    void acknowledgeObservationApi(observationId).catch(() => null);
  }, []);

  const dismissAll = useCallback(() => {
    setObservations((prev) => {
      prev.forEach((o) => void acknowledgeObservationApi(o.id).catch(() => null));
      return [];
    });
  }, []);

  const getBriefing = useCallback(async () => {
    try {
      return await fetchBriefing();
    } catch {
      return null;
    }
  }, []);

  return {
    observations,
    snapshot,
    activeConditions,
    connected,
    dismiss,
    dismissAll,
    getBriefing,
  };
}
