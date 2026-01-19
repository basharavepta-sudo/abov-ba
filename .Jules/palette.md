## 2026-01-19 - Canvas Widget Accessibility
**Learning:** Custom `tkinter` widgets (like `StyledButton` inheriting from `Canvas`) lack default keyboard accessibility. They miss focus rings and keyboard activation support.
**Action:** When creating or modifying custom `Canvas` widgets, always explicitly set `takefocus=1`, implement `FocusIn`/`FocusOut` handlers for visual feedback, and bind `<Return>`/`<space>` to the action.
