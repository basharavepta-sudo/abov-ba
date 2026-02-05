## 2024-05-22 - Tkinter Custom Widget Accessibility
**Learning:** Custom `Canvas`-based buttons in Tkinter completely lack keyboard accessibility (tab navigation and activation) by default, excluding keyboard-only users.
**Action:** Always add `takefocus=1`, `<FocusIn/Out>` visual handlers, and `<Return>/<space>` bindings when creating custom interactive widgets in Tkinter.
