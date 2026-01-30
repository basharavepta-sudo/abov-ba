## 2026-01-30 - [Accessibility in Custom Tkinter Widgets]
**Learning:** Custom widgets inheriting from `tk.Canvas` are not keyboard-accessible by default. They require explicit `takefocus=1` configuration and manual bindings for `<Return>`, `<space>`, and focus events to support keyboard navigation.
**Action:** Always check `takefocus` and keyboard bindings when creating or reviewing custom `tk.Canvas`-based interactive elements.
