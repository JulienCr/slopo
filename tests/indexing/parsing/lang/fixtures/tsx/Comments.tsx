/**
 * Renders a greeting banner.
 * @param name the person to greet
 */
function Banner(name: string): JSX.Element {
  // wrap in a span for styling
  const label = `Hi, ${name}`; /* trailing note */
  const docsUrl = "https://example.com/* not a comment */";
  return <span>{label}</span>;
}
