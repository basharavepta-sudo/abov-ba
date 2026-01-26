## 2026-01-26 - Custom Canvas Widget Accessibility

**Learning:** Custom `tkinter` widgets inheriting from `Canvas` (like `StyledButton`) do not have native keyboard focus or activation support, and `create_arc` based rounded rectangles can have "pacman" artifacts when adding borders.
**Action:** Explicitly set `takefocus=1`, implement `<FocusIn>`/`<FocusOut>` handlers for visual focus rings, bind `<Return>`/`<space>` for activation, and use separate `create_line` calls for clean borders on rounded shapes.
