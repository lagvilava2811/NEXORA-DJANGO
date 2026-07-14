# NEXORA Design System

## Direction

NEXORA pairs a restrained commerce interface with selective cinematic moments. Discovery and checkout stay familiar and fast; hero and technology-story surfaces use controlled depth, video, and scroll reveals. Georgian, English, and Russian are first-class layouts.

## Colour and themes

All storefront colours are semantic CSS tokens expressed in OKLCH. Dark and light themes have equivalent surface, text, border, focus, success, warning, and error roles. The interface avoids pure black, pure white, gradient text, and colour-only status signals. User preference is persisted; the operating-system preference is the initial fallback.

## Typography and layout

The product UI uses a dependable system sans stack. Large brand statements may use an editorial serif treatment; controls never do. Body text is limited to a readable line length. Desktop surfaces follow a 12-column logic and mobile surfaces a 4-column logic. Listings use a filter rail, product pages are media-led, checkout is focused, and administration favours dense predictable tables.

## Components and state

Interactive components define default, hover, focus-visible, active, disabled, loading, success, warning, and error states. Minimum pointer targets are 44 by 44 CSS pixels where practical. Icon-only controls always have accessible names; decorative SVGs are hidden from assistive technology. Drawers restore focus and close with Escape.

## Media

Published product media is local, SKU-scoped, model-matched, verified, checksum-tracked, and attributed. The local technology video has a poster, visible pause control, no audio dependency, and a reduced-motion fallback. A product card never substitutes an unrelated category or stock image.

## Motion

Commerce transitions use approximately 150–250 ms. Brand reveals may use 500–800 ms transform and opacity motion. Layout properties are not animated. `prefers-reduced-motion: reduce` disables decorative movement, smooth scrolling, video autoplay, and tilt behaviour.

## Accessibility release bar

The target is WCAG 2.2 AA: visible focus, skip navigation, semantic landmarks, keyboard-operable controls, explicit form labels, associated validation errors, live regions for asynchronous changes, adequate contrast, meaningful alternatives, and no horizontal overflow at 320 CSS pixels. Automated checks supplement, but do not replace, keyboard and screen-reader smoke tests.

## Bans

No repeated placeholder imagery, fictional products presented as real, autoplay audio, bounce easing, nested decorative cards, broken external media dependencies, inaccessible icon controls, or undocumented visual exceptions.