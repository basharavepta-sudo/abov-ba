import unittest
from unittest.mock import MagicMock
import sys

# Mock tkinter modules BEFORE importing gui
mock_tk = MagicMock()

# Create a base class for StyledButton to inherit from
class MockCanvas:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.bind_calls = []
        self.configure_calls = []
        self.focus_set_called = False

    def bind(self, event, command, add=None):
        self.bind_calls.append((event, command))

    def configure(self, **kwargs):
        self.configure_calls.append(kwargs)

    def focus_set(self):
        self.focus_set_called = True

    # Add other methods used by StyledButton
    def delete(self, *args): pass
    def create_arc(self, *args, **kwargs): pass
    def create_rectangle(self, *args, **kwargs): pass
    def create_text(self, *args, **kwargs): pass
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 0
    def winfo_height(self): return 0
    def after(self, ms, func=None, *args): return "after_id"
    def after_cancel(self, id): pass

mock_tk.Canvas = MockCanvas
sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()

# Now import gui
import gui

class TestStyledButton(unittest.TestCase):
    def test_accessibility_bindings(self):
        parent = MagicMock()
        btn = gui.StyledButton(parent, "Test")

        # Access the recorded calls from our MockCanvas base
        bound_events = [event for event, _ in btn.bind_calls]
        print(f"Bound events: {bound_events}")

        self.assertIn('<Enter>', bound_events)
        self.assertIn('<Leave>', bound_events)
        self.assertIn('<Button-1>', bound_events)

        # These should fail initially
        self.assertIn('<FocusIn>', bound_events, "Missing FocusIn binding for keyboard focus visual")
        self.assertIn('<FocusOut>', bound_events, "Missing FocusOut binding for keyboard focus visual")
        self.assertIn('<Return>', bound_events, "Missing Return key binding for activation")
        self.assertIn('<space>', bound_events, "Missing Space key binding for activation")

    def test_takefocus_configuration(self):
        parent = MagicMock()
        btn = gui.StyledButton(parent, "Test")

        # Check takefocus in configure calls
        found_takefocus = False
        for kwargs in btn.configure_calls:
            if kwargs.get('takefocus') == 1:
                found_takefocus = True

        # Also check if it was passed to init
        if btn.kwargs.get('takefocus') == 1:
            found_takefocus = True

        self.assertTrue(found_takefocus, "Button should accept focus (takefocus=1)")

    def test_click_sets_focus(self):
        parent = MagicMock()
        btn = gui.StyledButton(parent, "Test")
        # Trigger click event handler
        btn._on_click(MagicMock())
        self.assertTrue(btn.focus_set_called, "Clicking button should set focus")

if __name__ == '__main__':
    unittest.main()
