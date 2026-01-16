# Palette's Journal

## 2024-05-22 - Custom Tkinter Widgets & Accessibility

**Learning:** Custom UI widgets built on `tk.Canvas` completely bypass standard accessibility features. They are invisible to tab navigation and screen readers unless explicitly configured with `takefocus=1` and keyboard bindings.

**Action:** When inspecting legacy or "modern" Tkinter apps, always audit custom widgets for `takefocus` and `<Return>`/`<space>` bindings. Add focus rings (`FocusIn`/`FocusOut`) to ensure sighted keyboard users can track their position.
