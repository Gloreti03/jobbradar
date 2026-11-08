import { useQuery } from "@tanstack/react-query";
import { api, qk } from "@/api";

export function useProfileQuery() {
  return useQuery({ queryKey: qk.profile, queryFn: api.getProfile });
}
