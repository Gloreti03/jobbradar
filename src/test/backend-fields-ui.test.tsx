import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RequirementEvidence } from "@/components/radar/RequirementEvidence";
import { DocumentWarnings } from "@/components/radar/DocumentWarnings";
import { ScanFunnel } from "@/components/radar/ScanFunnel";

afterEach(cleanup);

describe("Optional backend fields", () => {
  it("supports an older application without inventing requirement evidence", () => {
    render(<RequirementEvidence />);
    expect(screen.getByText(/no requirement evidence map/i)).toBeInTheDocument();
    expect(screen.queryByRole("blockquote")).not.toBeInTheDocument();
  });

  it("shows required/preferred status and exact quotes supplied by the backend", () => {
    render(<RequirementEvidence items={[
      { requirement: "Python analysis", importance: "required", status: "met", evidence: ["Automated data cleaning with Python and pandas"] },
      { requirement: "Production deployment", importance: "nice_to_have", status: "missing", evidence: [] },
      { requirement: "Norwegian", importance: "required", status: "partial", evidence: ["Norwegian A2"] },
    ]} />);
    expect(screen.getByText("Python analysis")).toBeInTheDocument();
    expect(screen.getByText("“Automated data cleaning with Python and pandas”")).toBeInTheDocument();
    expect(screen.getByText("Not evidenced")).toBeInTheDocument();
    expect(screen.getByText("Partially supported")).toBeInTheDocument();
    expect(screen.getByText(/Nice to have/)).toBeInTheDocument();
    expect(screen.getByText("No supporting quote was supplied.")).toBeInTheDocument();
  });

  it("hides upload warnings when the backend has none", () => {
    const { rerender } = render(<DocumentWarnings />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    rerender(<DocumentWarnings warnings={["exams.pdf: text could not be read"]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("exams.pdf: text could not be read");
  });

  it("does not render a funnel when it is null or absent", () => {
    const { container, rerender } = render(<ScanFunnel funnel={null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ScanFunnel />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the backend counts, including zero, without estimating missing results", () => {
    render(<ScanFunnel funnel={{ total: 398, recent: 200, location: 180, language: 80, keywords: 40, deduplicated: 35, live: 30, ranked: 0 }} />);
    expect(screen.getByText("398")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("Still open")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(8);
  });

  it("hides a contradictory zero ranked count when results exist", () => {
    render(<ScanFunnel resultCount={15} funnel={{ total: 398, recent: 200, location: 180, language: 80, keywords: 40, deduplicated: 35, live: 24, ranked: 0 }} />);
    expect(screen.queryByText("Ranked")).not.toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText(/ranking count is temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
  });
});
