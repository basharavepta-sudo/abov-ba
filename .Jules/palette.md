## 2024-06-03 - Custom Tkinter Button Accessibility
**Learning:** Custom 'tkinter.Canvas' based buttons are invisible to keyboard users by default, lacking focus states and activation keys.
**Action:** Always implement 'takefocus=1', focus bindings, and key bindings (Space/Return) when building custom widgets.
