## 2024-10-24 - Canvas Button Accessibility
**Learning:** Custom Tkinter widgets based on `Canvas` (like buttons) are not keyboard accessible by default. They require `takefocus=1` and explicit bindings for `<FocusIn>`, `<FocusOut>`, `<space>`, and `<Return>` to function like standard buttons.
**Action:** Always verify `takefocus=1` and keyboard bindings when creating or reviewing custom Canvas-based interactive controls.
