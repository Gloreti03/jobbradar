import { createFileRoute, Link } from "@tanstack/react-router";
import { MessagesSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/radar/shared";

// Integration placeholder: Interview, VoiceInterview and Feedback are owned by another teammate.
// Their screens replace this component and use POST /interview/{application_id}/start|turn|feedback.
export const Route = createFileRoute("/interview/$applicationId")({
  head: () => ({
    meta: [
      { title: "Interview practice — RADAR" },
      { name: "description", content: "Practice a mock interview for your application." },
      { property: "og:title", content: "Interview practice — RADAR" },
      { property: "og:description", content: "Practice a mock interview for your application." },
    ],
  }),
  component: InterviewPlaceholder,
});

function InterviewPlaceholder() {
  const { applicationId } = Route.useParams();
  return (
    <EmptyState
      icon={<MessagesSquare className="size-6" />}
      title="Interview practice is coming soon"
      body="A mock interview based on the CV and cover letter you submitted will appear here."
      action={
        <Button asChild variant="outline">
          <Link to="/applications/$id" params={{ id: applicationId }}>Back to application</Link>
        </Button>
      }
    />
  );
}
