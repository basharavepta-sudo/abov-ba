import sys
import unittest
from unittest.mock import MagicMock

# Create a dummy Canvas class to replace tkinter.Canvas
class DummyCanvas:
    def __init__(self, parent, **kwargs):
        self.parent = parent
        self.kwargs = kwargs
        self.bindings = []
        self.config_calls = []

    def bind(self, event, handler):
        self.bindings.append(event)

    def create_arc(self, *args, **kwargs): pass
    def create_rectangle(self, *args, **kwargs): pass
    def create_text(self, *args, **kwargs): pass
    def delete(self, *args): pass

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)
        self.config_calls.append(kwargs)

# Mock tkinter module
mock_tk = MagicMock()
mock_tk.Canvas = DummyCanvas  # Replace Canvas with our dummy
sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()

# Now import gui
import gui

class TestStyledButtonAccessibility(unittest.TestCase):
    def test_accessibility_bindings(self):
        parent = MagicMock()
        btn = gui.StyledButton(parent, "Test")

        # Check bindings recorded in our dummy base
        print(f"Found bindings: {btn.bindings}")

        self.assertIn("<FocusIn>", btn.bindings, "Missing <FocusIn> binding")
        self.assertIn("<FocusOut>", btn.bindings, "Missing <FocusOut> binding")
        self.assertIn("<Return>", btn.bindings, "Missing <Return> binding")
        self.assertIn("<space>", btn.bindings, "Missing <space> binding")

    def test_takefocus_configuration(self):
        parent = MagicMock()
        btn = gui.StyledButton(parent, "Test")

        # Check if takefocus was passed to super().__init__ (stored in kwargs)
        print(f"Init kwargs: {btn.kwargs}")
        self.assertEqual(btn.kwargs.get('takefocus'), 1, "takefocus should be set to 1 by default")

    def test_disabled_state_updates_takefocus(self):
        parent = MagicMock()
        btn = gui.StyledButton(parent, "Test")

        # Initially enabled
        btn.set_disabled(True)
        self.assertEqual(btn.kwargs.get('takefocus'), 0, "Should disable focus when disabled")

        btn.set_disabled(False)
        self.assertEqual(btn.kwargs.get('takefocus'), 1, "Should enable focus when enabled")

if __name__ == "__main__":
    unittest.main()
