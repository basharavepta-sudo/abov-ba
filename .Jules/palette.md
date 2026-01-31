## 2026-01-31 - [Custom Canvas Buttons Accessibility]
**Learning:** Custom `tk.Canvas` widgets used as buttons (like `StyledButton`) completely lack keyboard accessibility (Tab focus, Space/Enter activation) and screen reader support by default.
**Action:** Always verify `takefocus=1` and bind `<FocusIn>`, `<FocusOut>`, `<space>`, and `<Return>` when encountering custom canvas-based controls.
