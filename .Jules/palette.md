## 2024-03-24 - Accessibility Trap in Canvas Buttons
**Learning:** Custom buttons drawn with `tk.Canvas` completely bypass standard accessibility features. They are invisible to keyboard navigation (Tab order) and do not react to activation keys (Enter/Space) unless explicitly programmed.
**Action:** Always add `takefocus=1` to the canvas constructor and manually bind `<FocusIn>`, `<FocusOut>`, `<Return>`, and `<space>` events. Visually indicate focus state (e.g., changing border color) in the draw loop.
