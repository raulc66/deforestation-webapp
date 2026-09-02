import EvidenceBlock, { EVIDENCE_LABELS, formatProviders } from "@/components/product/EvidenceBlock";

/** Compact evidence indicator for tables — delegates to EvidenceBlock. */
export default function EvidenceIndicator({ summary }) {
  if (!summary) return null;
  return <EvidenceBlock summary={summary} compact testId="evidence-indicator" />;
}

export { EVIDENCE_LABELS, formatProviders };
