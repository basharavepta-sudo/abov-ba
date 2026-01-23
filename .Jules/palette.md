## 2024-05-22 - Canvas Button Accessibility
**Learning:** Custom buttons built with `tkinter.Canvas` are invisible to keyboard users by default because they lack a tab stop and keyboard activation bindings.
**Action:** Always set `takefocus=1`, bind `<FocusIn>`/`<FocusOut>` for visual indicators, and bind `<Return>`/`<space>` for activation when creating custom interactive widgets.
