/**
 * Public commercial sales configuration.
 *
 * Purchase URLs are placeholders until Lemon Squeezy (or equivalent) checkout
 * links are issued. Set the REACT_APP_PURCHASE_* variables in frontend/.env
 * rather than scattering URLs in components.
 *
 * Lemon Squeezy: replace each empty/hash URL with the store checkout link
 * for that license SKU. Do not wire Stripe checkout here.
 */

const fromEnv = (name, fallback) => {
  const value = process.env[name];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
};

export const COMMERCIAL = {
  demoPath: "/explore",
  /** Published docs URL when available; in-page architecture is the fallback. */
  documentationUrl: fromEnv("REACT_APP_DOCS_URL", "#architecture"),
  architecturePath: "#architecture",
  licensesPath: "#licenses",
  faqPath: "#faq",
  platformPath: "#platform",

  developer: {
    id: "developer",
    name: "Developer",
    price: "$349",
    purchaseUrl: fromEnv("REACT_APP_PURCHASE_DEVELOPER_URL", "#licenses"),
  },
  commercial: {
    id: "commercial",
    name: "Commercial",
    price: "$899",
    recommended: true,
    purchaseUrl: fromEnv("REACT_APP_PURCHASE_COMMERCIAL_URL", "#licenses"),
  },
  agency: {
    id: "agency",
    name: "Agency",
    price: "$1,799",
    purchaseUrl: fromEnv("REACT_APP_PURCHASE_AGENCY_URL", "#licenses"),
  },
  acquisition: {
    id: "acquisition",
    name: "Acquisition",
    price: "Contact",
    contactUrl: fromEnv("REACT_APP_ACQUISITION_CONTACT_URL", "#licenses"),
  },
};
