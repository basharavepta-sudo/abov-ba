## 2024-05-22 - [Custom Canvas Buttons Require Manual Accessibility]
**Learning:** Custom UI widgets drawn on `tk.Canvas` (like `StyledButton`) do not inherit native OS focus behaviors. They must explicitly implement `takefocus=1`, focus event bindings (`<FocusIn>`, `<FocusOut>`), and keyboard activation (`<Return>`, `<space>`).
**Action:** When creating or modifying custom canvas-based widgets, always verify that keyboard users can navigate to them (Tab) and activate them (Enter/Space), and ensure a visual focus indicator is drawn.
