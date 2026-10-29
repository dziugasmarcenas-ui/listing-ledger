# Design system

## Surface

Operate mode: a daylight review workspace for examining how listing observations arrive and how the backend reconstructs state. The timeline is the primary artifact; the listing projection and selected event are its reading aids.

## Visual direction

Use a warm paper ground, deep ink, quiet mineral rules, and one muted vermilion accent. Typography is a confident system sans for headings and body, with a restrained system monospace only for IDs, timestamps, sequence numbers, and JSON. Keep the page open and editorial: broad margins, ruled sections, a continuous timeline, and one unboxed inspector area. No gradients, glass, nested cards, photography, or decorative dashboard metrics.

## Tokens

- Paper: `#f7f5f0`; raised paper: `#fffefa`
- Ink: `#24231f`; secondary ink: `#625f58`; quiet ink: `#6e6a62`
- Rule: `#d8d4cb`; soft rule: `#e9e5dc`
- Accent: `#a33d31`; accent wash: `#f3e8e4`
- Positive state: `#315e49`; unavailable state: `#8b463c`
- Body face: system sans stack; data face: system monospace stack
- Page measure: 1180px maximum; reading measure: 68ch
- Spacing unit: 4px; section rhythm: 32–56px
- Corners: 4px for controls, 2px for tags; avoid rounded panel containers

## Interaction

Controls have clear labels, visible focus, and at least 44px hit areas. Selection and replay update synchronously from the visitor’s perspective; keyboard stepping has no animation. Buttons use a brief 120ms press response. Respect reduced motion. Error states explain the failure and offer a retry. Empty states explain how to load a fictional demo.

## Responsive behavior

At 760px and below, stack the timeline and inspector in reading order, keep controls full-width where useful, and allow long identifiers and JSON to wrap or scroll inside their own region. The page remains usable at 375px without horizontal page overflow.
