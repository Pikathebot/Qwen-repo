"use client";

import { useCallback, useEffect, useState } from "react";
import {
  clearPersonaOverridesApi,
  fetchPersona,
  setPersonaApi,
  setPersonaOverridesApi,
} from "@/lib/api";
import { PersonaOverrides, PersonaStatus } from "@/lib/types";

export interface UsePersonaReturn {
  persona: PersonaStatus | null;
  isLoading: boolean;
  error: string | null;
  selectPersona: (personaId: string) => Promise<void>;
  applyOverrides: (overrides: PersonaOverrides) => Promise<void>;
  resetOverrides: () => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * Tracks the assistant's active persona — the voice and manner it replies in.
 * The tool protocol is unaffected by this; only presentation changes.
 */
export function usePersona(): UsePersonaReturn {
  const [persona, setPersona] = useState<PersonaStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (action: () => Promise<PersonaStatus>) => {
    try {
      setError(null);
      setPersona(await action());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Persona request failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refresh = useCallback(() => run(fetchPersona), [run]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    persona,
    isLoading,
    error,
    selectPersona: useCallback(
      (personaId: string) => run(() => setPersonaApi(personaId)),
      [run]
    ),
    applyOverrides: useCallback(
      (overrides: PersonaOverrides) => run(() => setPersonaOverridesApi(overrides)),
      [run]
    ),
    resetOverrides: useCallback(() => run(clearPersonaOverridesApi), [run]),
    refresh,
  };
}
