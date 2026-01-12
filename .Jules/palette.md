## 2024-05-23 - Custom Widgets and Keyboard Accessibility

**Learning:** When subclassing `tk.Canvas` to create custom widgets (like buttons), they are not keyboard-accessible by default. They require:
1. `takefocus=1` passed to `__init__`.
2. Explicit bindings for `<Return>` and `<space>` to trigger actions.
3. Visual focus indication (e.g., binding `<FocusIn>`/`<FocusOut>` to redraw borders).
Without these, users relying on keyboard navigation cannot interact with the UI elements, breaking accessibility.

**Action:** Always verify `takefocus` and keyboard bindings for any custom widget inheriting from `Canvas` or `Frame`.
