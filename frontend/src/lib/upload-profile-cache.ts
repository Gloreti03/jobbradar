import type { QueryClient } from "@tanstack/react-query";
import type { ProfileOut } from "@/types";
import { qk } from "@/api";

export async function cacheUploadedProfile(client: QueryClient, profile: ProfileOut) {
  // Stop old requests before removing data, so late responses cannot restore
  // the previous person's profile, applications or interview in the cache.
  if (profile.reset) {
    await client.cancelQueries();
    client.removeQueries({
      predicate: (query) => !(query.queryKey.length === 1 && query.queryKey[0] === "profile"),
    });
  } else {
    await client.cancelQueries({ queryKey: qk.profile, exact: true });
    client.setQueryData(["radar", "last"], null);
  }
  client.setQueryData(qk.profile, profile);
}
