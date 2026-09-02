/** Jest stub for react-router-dom when the package is unavailable in test env. */
const React = require("react");

const mockNavigate = jest.fn();
const mockSetSearchParams = jest.fn();
let mockParams = {};
let mockSearchParams = new URLSearchParams();

function __setMockParams(params) {
  mockParams = params ?? {};
}

function __setMockSearchParams(params) {
  mockSearchParams =
    params instanceof URLSearchParams ? params : new URLSearchParams(params ?? "");
}

function __resetRouterMocks() {
  mockNavigate.mockReset();
  mockSetSearchParams.mockReset();
  mockParams = {};
  mockSearchParams = new URLSearchParams();
}

module.exports = {
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  Link: ({ children, to, ...rest }) =>
    React.createElement("a", { href: to, ...rest }, children),
  NavLink: ({ children, to, className, ...rest }) => {
    const resolved =
      typeof className === "function" ? className({ isActive: false }) : className;
    return React.createElement("a", { href: to, className: resolved, ...rest }, children);
  },
  BrowserRouter: ({ children }) => children,
  MemoryRouter: ({ children }) => children,
  Routes: ({ children }) => children,
  Route: ({ element }) => element,
  Navigate: () => null,
  useLocation: () => ({ pathname: "/", search: "", hash: "", state: null }),
  __mockNavigate: mockNavigate,
  __setMockParams,
  __setMockSearchParams,
  __resetRouterMocks,
};
