# Sentinel UI Design System – Dark Neon

## Brand & Style
The brand personality is technical, secure, and elite, evoking a digital‑vault feel. The aesthetic leverages **Glassmorphism** and **Minimalism**, using deep obsidian surfaces with neon accents.

## Colors (Neon Palette)
```yaml
namedColors:
  background: '#0A0A0B'            # true black base
  surface: '#121214'               # subtle lift
  primary: '#007AFF'               # electric blue – primary actions, focus
  secondary: '#39FF14'             # neon green – success, active states
  tertiary: '#FF375F'              # pink‑red – destructive/urgent
  on-primary: '#FFFFFF'
  on-secondary: '#FFFFFF'
  on-surface: '#E5E5E5'
  outline: 'rgba(255,255,255,0.08)'
```

## Typography
```yaml
fontFamily: Inter
styles:
  display-lg: {fontSize: 48px, fontWeight: 700, lineHeight: 56px, letterSpacing: -0.02em}
  headline-lg: {fontSize: 32px, fontWeight: 600, lineHeight: 40px, letterSpacing: -0.01em}
  body-lg: {fontSize: 16px, fontWeight: 400, lineHeight: 24px, letterSpacing: -0.01em}
  label-md: {fontSize: 12px, fontWeight: 600, lineHeight: 16px, letterSpacing: 0.02em}
```

## Spacing & Shape
```yaml
spacing:
  base: 8px
  sm: 4px
  md: 16px
  lg: 24px
  xl: 32px
  margin: 40px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
```

## Elevation – Glassmorphism
- **Level 1 (Cards)** – `rgba(255,255,255,0.03)` background, `backdrop-filter: blur(20px)`, `1px solid rgba(255,255,255,0.08)`.
- **Level 2 (Modals)** – `rgba(255,255,255,0.06)` background, `blur(32px)`, outer glow `0 0 8px #007AFF@5%`.

## Component Tokens (summary)
- **Buttons** – Primary: solid `#007AFF` with white text. Ghost: 8% white border, hover adds blur.
- **Active Indicators** – Neon‑green with `box-shadow: 0 0 8px #39FF14`.
- **Inputs** – Semi‑transparent, 1px border, focus → electric‑blue border + 2px glow.
- **Cards** – Glass surface, rounded `0.5rem`, backdrop blur 12‑20px.
- **Lists / Tables** – Row divider `rgba(255,255,255,0.05)`, hover brightens.

---

*This DESIGN.md will be uploaded to the Stitch project and used to generate a design system.*
