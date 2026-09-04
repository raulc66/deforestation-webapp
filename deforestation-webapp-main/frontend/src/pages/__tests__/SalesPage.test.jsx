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
    expect(screen.getByTestId("license-developer")).toHaveTextContent("$349");
    expect(screen.getByTestId("license-commercial")).toHaveTextContent("$899");
    expect(screen.getByTestId("license-commercial")).toHaveTextContent(/Recommended/i);
    expect(screen.getByTestId("license-agency")).toHaveTextContent("$1,799");
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
});
