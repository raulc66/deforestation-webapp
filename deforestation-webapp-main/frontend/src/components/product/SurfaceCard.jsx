/**
 * Restrained surface container — replaces generic glass/card-flat for intelligence UI.
 */
export default function SurfaceCard({
  children,
  className = "",
  variant = "default",
  testId,
  as: Tag = "div",
}) {
  const variantClass =
    variant === "inset"
      ? "fw-surface-inset"
      : variant === "emphasis"
        ? "fw-surface-emphasis"
        : "fw-surface";

  return (
    <Tag
      className={`${variantClass} ${className}`.trim()}
      data-testid={testId}
    >
      {children}
    </Tag>
  );
}
