import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, qk } from "@/api";
import { CVDocument } from "@/components/radar/Documents";
import { ErrorState, LoadingState } from "@/components/radar/shared";

export const Route = createFileRoute("/print/cv/$id")({
  head: () => ({
    meta: [
      { title: "CV — JobbRadar" },
      { name: "description", content: "Printable A4 CV." },
      { property: "og:title", content: "CV — JobbRadar" },
      { property: "og:description", content: "Printable A4 CV." },
    ],
  }),
  component: PrintCV,
});

function PrintCV() {
  const id = Number(Route.useParams().id);
  const q = useQuery({
    queryKey: qk.application(id),
    queryFn: () => api.getApplication(id),
    staleTime: 0,
  });
  const printed = useRef(false);
  useEffect(() => {
    if (q.isSuccess && !printed.current) {
      printed.current = true;
      setTimeout(() => window.print(), 500);
    }
  }, [q.isSuccess]);
  if (q.isPending) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return (
    <div className="a4-sheet">
      <CVDocument cv={q.data.cv} />
    </div>
  );
}
