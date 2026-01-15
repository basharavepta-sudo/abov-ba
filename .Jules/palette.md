## 2024-05-22 - Custom Widget Accessibility
**Learning:** Custom Tkinter widgets (inheriting from `Canvas` or `Frame`) are invisible to keyboard navigation by default. They require explicit `takefocus=1` and key bindings for `<Return>`/`<space>` to match standard button behavior.
**Action:** Always verify keyboard reachability when styling custom controls. Add focus indicators (visual rings) that persist even when not hovering.

## 2024-05-22 - Headless GUI Verification
**Learning:** In headless environments (CI/CD), verification of GUI changes can be achieved via static analysis (AST parsing) or mocking `tkinter`, even if the app itself cannot launch.
**Action:** Use `ast` module to verify presence of accessibility attributes (`takefocus`) and event bindings when visual verification isn't possible.
