## 2024-05-22 - Tkinter Custom Widget Accessibility
**Learning:** Custom `Canvas` widgets in Tkinter lack default keyboard accessibility. They require explicit `takefocus=1` configuration and `FocusIn`/`FocusOut` bindings to track state, plus manual drawing of focus indicators.
**Action:** When creating or auditing custom Tkinter widgets, verify `takefocus` is enabled and visual focus states are implemented via event bindings.
