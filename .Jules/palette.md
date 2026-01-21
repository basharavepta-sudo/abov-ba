## 2024-05-21 - Custom Canvas Button Accessibility
**Learning:** Custom tkinter widgets based on Canvas require manual implementation of focus management (`takefocus=1`, focus bindings) and visual focus rings. Standard widgets (Button) handle this, but Canvas does not.
**Action:** When styling custom buttons with Canvas, always implement `_on_focus_in` and `_on_focus_out` handlers and map Return/Space keys.

## 2024-05-21 - Rounded Rectangle Borders in Tkinter
**Learning:** The helper `_rounded_rect` composed of arcs and rects only outlines the corners if `create_rectangle` uses `outline=""`. Manual `create_line` segments are needed for full borders.
**Action:** Verify full border rendering when using composite shapes for UI elements.
