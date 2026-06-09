# AShare Agent Frontend Design

## Reference

Reference site: `https://remihuang.com`

Observed visual language:

- Warm paper canvas: primary background is near-white cream `#fdfbf5`, with a subtle paper/noise layer and very low-opacity blue/red radial wash.
- Editorial typography: serif display type for large statements, Inter-style sans text for body, JetBrains Mono-style text for navigation, labels, and operational metadata.
- Ink-first palette: black text `#1a1a1a`, muted gray `#666666`, deep blue `#1d3a8a` as the main accent. Color is sparse and intentional.
- Hard UI edges: inputs and buttons use square or nearly square corners, 1px dark borders, and minimal shadows.
- Layout rhythm: generous first-screen whitespace, fixed top navigation, section dividers, strong asymmetry, and large content blocks instead of dense boxed dashboards.
- Personality details: underlines, arrows, small handwritten-looking accent notes, and blue line details provide human texture without turning the page into decoration.

## Applied Direction

This project is still an operational quant dashboard, so the design is adapted rather than copied.

- The dark left rail is replaced with a paper-toned top command bar inspired by the reference site's fixed nav.
- The cycle title becomes an editorial hero using a serif display stack.
- Agent/service state becomes compact mono metadata chips.
- Panels keep the dashboard's information density but move to paper surfaces, hard borders, and restrained blue/black accents.
- Risk and warning states remain clearly colored because trading workflow state must be instantly distinguishable.
- Charts and trace details use deep blue instead of teal to match the reference and reduce palette spread.

## Tokens

```css
--paper: #fdfbf5;
--paper-deep: #f4efe4;
--ink: #1a1a1a;
--ink-soft: #666666;
--ink-blue: #1d3a8a;
--line: rgba(26, 26, 26, 0.2);
--danger: #9f2339;
--warning: #805600;
--good: #0b735f;
```

## Implementation Notes

- Use mono labels for navigation, metrics captions, table headers, and agent metadata.
- Use serif only for the main cycle title and large numeric metrics.
- Avoid gradients as dominant brand treatment. Background washes must stay below 5% opacity.
- Keep controls rectangular and compact.
- Preserve responsive behavior: the top command bar wraps on tablet and stacks on mobile.
