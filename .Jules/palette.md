## 2024-05-22 - Custom Canvas Button Accessibility
**Learning:** Custom `tkinter` widgets inheriting from `Canvas` (like `StyledButton`) are not keyboard-accessible by default. They require explicit `takefocus=1` configuration and bindings for `<FocusIn>`, `<FocusOut>`, `<Return>`, and `<space>` to function like native buttons.
**Action:** Always verify `takefocus` and keyboard bindings when encountering or creating custom `Canvas`-based interactive elements. Ensure focus visual states are manually drawn since `highlightthickness` might be disabled.
