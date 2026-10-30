# Design system

## Surface

A dark review workspace for inspecting an append-only timeline, reconstructed listing state and selected event. Keep visible copy sparse and preserve the reading order.

## Visual direction

Broad visual reference: [Great UI](https://www.great-ui.com/). Independently authored styling uses charcoal surfaces, local Geist typography, rounded controls and restrained orange selection. No reference component code, branding or page assets are included.

## Tokens

- Canvas: `#0a0a0a`; workspace: `#111111`; raised surface: `#171717`
- Text: `#ededed`; secondary: `#aaaaaa`; quiet: `#999999`
- Border: `#303030`; soft border: `#242424`
- Accent: `#f57c26`; accent wash: `#2c2016`
- Body: local Geist variable, system sans fallback; data: system monospace
- Page width: 1180px; breakpoint: 760px
- Controls: 12px corners and minimum 44px hit area; workspace: 20px corners

## Interaction

Preserve native keyboard replay, visible focus, explicit Unknown values and accessible names. Brief button press feedback respects reduced motion. The replay API and event semantics are unchanged.

## Responsive behavior

Stack timeline and inspector below 760px. Long JSON wraps within its own scroll region. Screenshots are full-page captures; browser viewport dimensions need not equal image dimensions.

## Verification

Checked at 1440×950 and 375×812 viewports: no horizontal overflow, aligned timeline markers, loaded local Geist, and minimum 44px controls. Preview images are full-page content captures.
