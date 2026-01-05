## 2024-05-22 - Custom Tkinter Widget Accessibility
**Learning:** Custom Tkinter widgets inheriting from `tk.Canvas` or `tk.Frame` are NOT keyboard accessible by default. They require explicit `takefocus=1` and bindings for `<FocusIn>`, `<FocusOut>`, `<space>`, and `<Return>` to function like native buttons.
**Action:** When creating custom styled widgets in Tkinter, always add a `focused` state, visual indicators for focus in `_draw`, and standard keyboard event bindings.
