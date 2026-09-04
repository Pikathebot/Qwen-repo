"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createRoutineApi,
  deleteRoutineApi,
  fetchRoutines,
  runRoutineNowApi,
  updateRoutineApi,
} from "@/lib/api";
import { Routine, RoutineInput } from "@/lib/types";

export interface UseRoutinesReturn {
  routines: Routine[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createRoutine: (input: RoutineInput) => Promise<void>;
  updateRoutine: (id: string, input: Partial<RoutineInput>) => Promise<void>;
  deleteRoutine: (id: string) => Promise<void>;
  runNow: (id: string) => Promise<void>;
}

/** Manages the time-triggered briefings/messages Jarvis fires on its own. */
export function useRoutines(): UseRoutinesReturn {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchRoutines();
      setRoutines(data.routines);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load routines");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createRoutine = useCallback(
    async (input: RoutineInput) => {
      await createRoutineApi(input);
      await refresh();
    },
    [refresh]
  );

  const updateRoutine = useCallback(
    async (id: string, input: Partial<RoutineInput>) => {
      await updateRoutineApi(id, input);
      await refresh();
    },
    [refresh]
  );

  const deleteRoutine = useCallback(
    async (id: string) => {
      await deleteRoutineApi(id);
      await refresh();
    },
    [refresh]
  );

  const runNow = useCallback(async (id: string) => {
    await runRoutineNowApi(id);
  }, []);

  return { routines, isLoading, error, refresh, createRoutine, updateRoutine, deleteRoutine, runNow };
}
