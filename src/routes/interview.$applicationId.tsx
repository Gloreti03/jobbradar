import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api, qk } from "@/api";
import { ErrorState, LoadingState } from "@/components/radar/shared";
import { Interview } from "@/components/radar/Interview";

// D — Mock interview (owner: Matilde): text mode + feedback, based on the snapshot saved with "I applied".
export const Route = createFileRoute("/interview/$applicationId")({
  head: () => ({
    meta: [
      { title: "Interview practice — RADAR" },
      { name: "description", content: "Practice a mock interview for your application." },
      { property: "og:title", content: "Interview practice — RADAR" },
      { property: "og:description", content: "Practice a mock interview for your application." },
    ],
  }),
  component: InterviewPage,
});

function InterviewPage() {
  const id = Number(Route.useParams().applicationId);
  const q = useQuery({ queryKey: qk.application(id), queryFn: () => api.getApplication(id) });
  if (q.isPending) return <LoadingState label="Loading application…" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return <Interview app={q.data} />;
}
