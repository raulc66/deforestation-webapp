import { render, screen, fireEvent } from "@testing-library/react";
import OrganizationSelector from "../OrganizationSelector";

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: jest.fn(),
}));

const { useOrganization } = require("@/context/OrganizationContext");

describe("OrganizationSelector", () => {
  it("shows single organization name when only one org", () => {
    useOrganization.mockReturnValue({
      organizations: [{ id: "org-1", name: "Personal Workspace", role: "owner" }],
      currentOrganization: { id: "org-1", name: "Personal Workspace", role: "owner" },
      selectedOrgId: "org-1",
      setSelectedOrgId: jest.fn(),
      loading: false,
    });
    render(<OrganizationSelector />);
    expect(screen.getByTestId("organization-name")).toHaveTextContent("Personal Workspace");
    expect(screen.getByTestId("organization-role")).toHaveTextContent("owner");
  });

  it("renders select when multiple organizations available", () => {
    const setSelectedOrgId = jest.fn();
    useOrganization.mockReturnValue({
      organizations: [
        { id: "org-1", name: "Alpha Forestry", role: "owner" },
        { id: "org-2", name: "Beta Team", role: "member" },
      ],
      currentOrganization: { id: "org-1", name: "Alpha Forestry", role: "owner" },
      selectedOrgId: "org-1",
      setSelectedOrgId,
      loading: false,
    });
    render(<OrganizationSelector />);
    fireEvent.change(screen.getByTestId("organization-select"), { target: { value: "org-2" } });
    expect(setSelectedOrgId).toHaveBeenCalledWith("org-2");
  });
});
