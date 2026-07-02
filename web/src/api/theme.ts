import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { C4Theme } from "../types";

export function useC4Theme(): UseQueryResult<C4Theme> {
  return useQuery<C4Theme>({
    queryKey: ["theme", "c4"],
    queryFn: () => apiGet<C4Theme>("/api/v1/theme/c4"),
    staleTime: 3_600_000, // 1 hour — theme changes rarely
  });
}
