## 2026-02-02 - Tkinter Custom Widget Accessibility
**Learning:** Custom `tkinter` widgets inheriting from `Canvas` or `Frame` are not focusable by default. They require `takefocus=1`, explicit `<FocusIn>`/`<FocusOut>` handlers for visual feedback, and `<Return>`/`<space>` bindings for activation.
**Action:** Always check `takefocus` and key bindings when encountering custom `tkinter` widgets. Add focus rings manually in the draw method.
