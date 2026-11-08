import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { cacheUploadedProfile } from "@/lib/upload-profile-cache";
import type { ProfileOut } from "@/types";
import fixture from "@/mocks/profile.json";

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  client.setQueryData(["profile"], fixture);
  for (const key of [
    ["radar", "last"],
    ["applications"],
    ["application", 1],
    ["job", 2],
    ["interview", 1],
    ["future-user-data"],
  ]) {
    client.setQueryData(key, "previous person's data");
  }
  return client;
}

describe("Profile upload cache", () => {
  it("keeps only the uploaded profile after the backend reports a person change", async () => {
    const client = setup();
    const next: ProfileOut = {
      ...(structuredClone(fixture) as ProfileOut),
      reset: true,
      profile: { ...fixture.profile, name: "New Candidate" },
    };
    await cacheUploadedProfile(client, next);
    expect(
      client
        .getQueryCache()
        .getAll()
        .map((q) => q.queryKey),
    ).toEqual([["profile"]]);
    expect(client.getQueryData(["profile"])).toEqual(next);
    client.clear();
  });

  it.each([false, undefined])(
    "preserves applications and interviews when reset is %s",
    async (reset) => {
      const client = setup();
      const next: ProfileOut = {
        ...(structuredClone(fixture) as ProfileOut),
        ...(reset === undefined ? {} : { reset }),
      };
      await cacheUploadedProfile(client, next);
      expect(client.getQueryData(["profile"])).toEqual(next);
      expect(client.getQueryData(["radar", "last"])).toBeNull();
      expect(client.getQueryData(["applications"])).toBe("previous person's data");
      expect(client.getQueryData(["interview", 1])).toBe("previous person's data");
      client.clear();
    },
  );

  it("cancels in-flight requests so late data cannot reappear after a reset", async () => {
    const client = setup();
    let resolveOld!: (value: string) => void;
    let oldSignal!: AbortSignal;
    const request = client
      .fetchQuery({
        queryKey: ["job", 9],
        queryFn: ({ signal }) => {
          oldSignal = signal;
          return new Promise<string>((resolve) => {
            resolveOld = resolve;
          });
        },
      })
      .catch(() => undefined);
    await cacheUploadedProfile(client, {
      ...(structuredClone(fixture) as ProfileOut),
      reset: true,
    });
    expect(oldSignal.aborted).toBe(true);
    resolveOld("late data from previous person");
    await request;
    expect(client.getQueryData(["job", 9])).toBeUndefined();
    expect(client.getQueryCache().getAll()).toHaveLength(1);
    client.clear();
  });
});
