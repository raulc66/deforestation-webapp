import { render, screen } from "@testing-library/react";
import EvidenceIndicator from "../EvidenceIndicator";

describe("EvidenceIndicator", () => {
  it("renders multi-source evidence compactly", () => {
    render(
      <EvidenceIndicator
        summary={{
          providers: ["NASA FIRMS", "Copernicus EMS"],
          evidence_state: "multi_source",
          strongest_correlation_strength: 0.87,
          source_availability: {
            "nasa.firms": "healthy",
            "cems.rapid_mapping": "healthy",
          },
        }}
      />
    );

    expect(screen.getByText(/NASA FIRMS · Copernicus EMS/)).toBeInTheDocument();
    expect(screen.getByText(/Multi-source/)).toBeInTheDocument();
    expect(screen.getByText(/0.87/)).toBeInTheDocument();
  });

  it("shows degraded source status without negative evidence language", () => {
    render(
      <EvidenceIndicator
        summary={{
          providers: ["NASA FIRMS"],
          evidence_state: "degraded_source",
          source_availability: { "nasa.firms": "failed" },
        }}
      />
    );

    expect(screen.getByTestId("evidence-degraded-sources")).toHaveTextContent("degraded");
    expect(screen.queryByText(/No FIRMS evidence/i)).not.toBeInTheDocument();
  });
});
