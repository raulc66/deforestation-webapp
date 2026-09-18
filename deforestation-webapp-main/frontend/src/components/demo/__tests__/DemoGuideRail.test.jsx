import { render, screen, fireEvent } from "@testing-library/react";
import DemoGuideRail from "../DemoGuideRail";

const GUIDE = [
  { id: "forests", title: "Your monitored forests", body: "These stands are watched." },
  { id: "changed", title: "What changed", body: "Signals appear on the map." },
  { id: "investigate", title: "Investigate", body: "Open a disturbance." },
];

describe("DemoGuideRail", () => {
  it("keeps every step in the DOM and expands only the active step", () => {
    const onSelect = jest.fn();
    render(
      <DemoGuideRail guide={GUIDE} currentStep="forests" onSelect={onSelect} />
    );
    expect(screen.getByTestId("demo-guide-step-forests")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("demo-guide-step-body-forests")).toHaveTextContent(
      "These stands are watched."
    );
    expect(screen.queryByTestId("demo-guide-step-body-changed")).not.toBeInTheDocument();
    expect(screen.getByTestId("demo-guide-step-changed")).toBeInTheDocument();
    expect(screen.getByTestId("demo-guide-step-investigate")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("demo-guide-step-investigate"));
    expect(onSelect).toHaveBeenCalledWith("investigate");
  });

  it("compacts inactive steps below xl while keeping the full desktop intro in the DOM", () => {
    render(<DemoGuideRail guide={GUIDE} currentStep="forests" />);
    const intro = screen.getByTestId("demo-guide-intro");
    expect(intro).toHaveClass("hidden", "xl:block");
    expect(screen.getByTestId("demo-guide-rail")).toHaveClass("p-3", "xl:p-4");
    expect(screen.getByTestId("demo-guide-step-changed")).toHaveClass("py-0.5", "xl:py-2");
    expect(screen.getByTestId("demo-guide-step-forests")).toHaveClass("py-2");
  });
});
