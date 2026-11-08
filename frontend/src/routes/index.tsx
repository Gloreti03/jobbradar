import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    throw redirect({ to: "/profile" });
  },
  head: () => ({
    meta: [
      { title: "JobbRadar — Job hunting in Oslo" },
      { name: "description", content: "Find English-friendly jobs in Oslo that fit your profile." },
      { property: "og:title", content: "JobbRadar — Job hunting in Oslo" },
      {
        property: "og:description",
        content: "Find English-friendly jobs in Oslo that fit your profile.",
      },
    ],
  }),
});
