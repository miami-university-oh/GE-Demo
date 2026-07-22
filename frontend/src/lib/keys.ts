// SVG elements with role="button" do not get native Enter/Space activation,
// so every interactive SVG shape shares this check in its keydown handler.
export function isActivateKey(e: { key: string }): boolean {
  return e.key === 'Enter' || e.key === ' ';
}
