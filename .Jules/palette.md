## 2026-02-04 - [Accessibility] Custom Tkinter Buttons
**Learning:** Custom buttons inheriting from `tk.Canvas` are inaccessible by default. They need explicit `takefocus=1` and bindings for `<Return>`, `<space>`, and Focus events to support keyboard navigation.
**Action:** Always check `StyledButton` or similar custom widgets for `takefocus` and key bindings when auditing Tkinter apps.
