## 2024-05-23 - Custom Tkinter Button Accessibility
**Learning:** Custom buttons inheriting from `tk.Canvas` are invisible to keyboard navigation by default. They require `takefocus=1`, `<FocusIn>/<FocusOut>` handlers for visual feedback, and explicit `<Return>`/`<space>` bindings to trigger actions.
**Action:** When creating custom Tkinter widgets, always check `takefocus` configuration and implement full keyboard support (visual + functional).
