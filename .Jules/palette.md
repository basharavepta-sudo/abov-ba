## 2024-10-12 - Custom Tkinter Widgets and Accessibility
**Learning:** Custom widgets inheriting from `tk.Canvas` are invisible to keyboard users by default. They lack `takefocus` and do not emit semantic events, making them a "black hole" for accessibility.
**Action:** Always verify `takefocus=1`, implement `<FocusIn>/<FocusOut>` visual states, and bind `<Return>/<space>` for activation when creating custom interactive widgets in Tkinter.
