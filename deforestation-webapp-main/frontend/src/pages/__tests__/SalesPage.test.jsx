import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SalesPage from "../SalesPage";
import { COMMERCIAL } from "@/config/commercial";

describe("SalesPage", () => {
  it("renders the commercial landing page without authentication", () => {
    render(
      <MemoryRouter>
        <SalesPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("sales-page")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: /Build geospatial intelligence products without starting from zero/i,
      })
    ).toBeInTheDocument();
    expect(screen.queryByTestId("nav-dashboard")).not.toBeInTheDocument();
  });

  it("sends the primary demo CTA to the explore demo", () => {
    render(
      <MemoryRouter>
        <SalesPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("sales-cta-demo")).toHaveAttribute("href", "/explore");
    expect(screen.getByTestId("sales-cta-demo")).toHaveTextContent(/Explore demo/i);
    expect(screen.getByTestId("sales-cta-demo")).toHaveAttribute("href", COMMERCIAL.demoPath);
    expect(screen.getByTestId("sales-nav-demo")).toHaveAttribute("href", "/explore");
    expect(screen.getByTestId("sales-nav-demo")).toHaveTextContent(/Explore demo/i);
  });

  it("presents four license tiers at the listed prices", () => {
    render(
      <MemoryRouter>
        <SalesPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("license-developer")).toHaveTextContent("$199");
    expect(screen.getByTestId("license-commercial")).toHaveTextContent("$399");
    expect(screen.getByTestId("license-commercial")).toHaveTextContent(/Recommended/i);
    expect(screen.getByTestId("license-agency")).toHaveTextContent("$699");
    expect(screen.getByTestId("license-acquisition")).toHaveTextContent(/Contact/i);
  });

  it("does not claim illegal logging detection or live Stripe billing", () => {
    render(
      <MemoryRouter>
        <SalesPage />
      </MemoryRouter>
    );
    expect(screen.queryByText(/detect illegal logging/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI-powered satellite/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/disabled by default/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/subject to the final license agreement supplied with the product/i)
        .length
    ).toBeGreaterThan(0);
  });

  it("keeps the document on the light public canvas", () => {
    const { unmount } = render(
      <MemoryRouter>
        <SalesPage />
      </MemoryRouter>
    );
    expect(document.documentElement.classList.contains("sales-root")).toBe(true);
    expect(screen.getByTestId("sales-page")).toHaveClass("sales");
    unmount();
    expect(document.documentElement.classList.contains("sales-root")).toBe(false);
  });

  it("shows real product screenshots in the product showcase", () => {
    render(
      <MemoryRouter>
        <SalesPage />
      </MemoryRouter>
    );
    expect(screen.queryByText("Interface preview")).not.toBeInTheDocument();
    expect(screen.queryByText("Screenshot placeholder")).not.toBeInTheDocument();
    const commandCenter = screen.getByAltText(
      "ForestWatch Command Center showing active intelligence events and monitored regions"
    );
    const map = screen.getByAltText(
      "ForestWatch intelligence map showing monitored forest areas and geospatial overlays"
    );
    const investigation = screen.getByAltText(
      "ForestWatch investigation view showing evidence and intelligence details"
    );
    const alerts = screen.getByAltText(
      "ForestWatch alerts view showing demonstration policies and notification channels"
    );
    const landing = screen.getByAltText("ForestWatch commercial product landing page");
    expect(commandCenter).toHaveAttribute("src", "/sales/forestwatch-command-center.png");
    expect(map).toHaveAttribute("src", "/sales/forestwatch-intelligence-map.png");
    expect(investigation).toHaveAttribute("src", "/sales/forestwatch-investigation.png");
    expect(alerts).toHaveAttribute("src", "/sales/forestwatch-alerts.png");
    expect(landing).toHaveAttribute("src", "/sales/forestwatch-sales-page.png");
    expect(commandCenter).toHaveAttribute("loading", "eager");
    expect(map).toHaveAttribute("loading", "lazy");
    expect(investigation).toHaveAttribute("loading", "lazy");
    expect(alerts).toHaveAttribute("loading", "lazy");
    expect(landing).toHaveAttribute("loading", "lazy");
  });
});
