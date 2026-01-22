## 2024-05-23 - Tkinter Canvas Accessibility
**Learning:** Custom Tkinter widgets inheriting from `tk.Canvas` are not keyboard-accessible by default. They require explicit `takefocus=1` and key bindings (`<Return>`, `<space>`, `<FocusIn>`, `<FocusOut>`) to support keyboard users.
**Action:** Always verify keyboard accessibility for custom canvas-based widgets and add focus management logic.
