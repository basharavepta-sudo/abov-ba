## 2026-02-03 - Custom Canvas Button Accessibility
**Learning:** Custom Tkinter widgets inheriting from `Canvas` lack native keyboard accessibility (focus, activation). They require explicit `takefocus=1` and bindings for `<Return>`, `<space>`, `<FocusIn>`, and `<FocusOut>` to function like standard buttons.
**Action:** Always verify keyboard accessibility on custom widgets by checking for focus rings and keyboard activation during the design phase.
