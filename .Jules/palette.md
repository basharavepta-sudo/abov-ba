## 2024-05-22 - Custom Canvas Buttons Accessibility
**Learning:** `tk.Canvas` widgets used as buttons are invisible to keyboard users by default. They require `takefocus=1` and explicit key bindings (`<Return>`, `<space>`) to function like standard buttons.
**Action:** Always add `takefocus=1` and visual focus indicators (e.g., border color change on `<FocusIn>`) when creating custom canvas-based interactive elements.
