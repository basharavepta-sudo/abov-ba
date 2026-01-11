## 2024-05-22 - [Custom Canvas Buttons Accessibility]
**Learning:** Custom buttons drawn on `tk.Canvas` are invisible to keyboard users by default. They require manual implementation of `takefocus=1`, focus event handling (`<FocusIn>`, `<FocusOut>`), and keyboard activation (`<Return>`, `<space>`).
**Action:** Always verify `takefocus` and keyboard bindings when creating or modifying custom widget classes that inherit from `tk.Canvas` or `tk.Frame`. Use visual indicators (like borders or glow effects) to denote focus state.
