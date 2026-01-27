## 2024-10-24 - Custom Tkinter Widgets & Accessibility
**Learning:** Custom `tkinter` widgets inheriting from `Canvas` or `Frame` are not keyboard accessible by default. They require explicit `takefocus=1` configuration and bindings for `<Return>`, `<space>`, `<FocusIn>`, and `<FocusOut>` to function like native buttons.
**Action:** Always verify `takefocus` and key bindings when creating custom interactive widgets in `tkinter`.
