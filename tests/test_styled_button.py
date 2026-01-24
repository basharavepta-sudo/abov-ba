import sys
import unittest
from unittest.mock import MagicMock, patch, call

# Mock tkinter modules
mock_tk = MagicMock()
mock_ttk = MagicMock()

class MockCanvas(MagicMock):
    def __init__(self, master=None, **kwargs):
        super().__init__()
        self._init_kwargs = kwargs

        self.bind = MagicMock()
        self.delete = MagicMock()
        self.create_arc = MagicMock()
        self.create_rectangle = MagicMock()
        self.create_text = MagicMock()
        self.focus_set = MagicMock()
        self.configure = MagicMock()
        self.winfo_rootx = MagicMock(return_value=0)
        self.winfo_rooty = MagicMock(return_value=0)
        self.winfo_height = MagicMock(return_value=10)

mock_tk.Canvas = MockCanvas

sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.ttk'] = mock_ttk
mock_tk.messagebox = MagicMock()

import gui

class TestStyledButtonAccessibility(unittest.TestCase):
    def setUp(self):
        self.parent = MagicMock()
        self.command = MagicMock()
        self.btn = gui.StyledButton(self.parent, "Test", command=self.command)

    def test_initial_accessibility_state(self):
        # Verify takefocus=1 is passed to init
        takefocus = self.btn._init_kwargs.get('takefocus')
        self.assertEqual(takefocus, 1, "StyledButton should be focusable by default")

    def test_key_bindings_present(self):
        bound_events = []
        for c in self.btn.bind.mock_calls:
            _, args, _ = c
            if args:
                bound_events.append(args[0])

        required = ['<Return>', '<space>', '<FocusIn>', '<FocusOut>', '<Button-1>']
        for req in required:
            self.assertIn(req, bound_events, f"Event {req} should be bound")

    def test_focus_visuals(self):
        # Simulate FocusIn
        self.btn._on_focus_in(None)
        self.assertTrue(self.btn.focused)
        # Check if _draw was called (implied, but let's check internal state)

        # Simulate FocusOut
        self.btn._on_focus_out(None)
        self.assertFalse(self.btn.focused)

    def test_keyboard_activation(self):
        # Simulate Return key
        self.btn._on_key_invoke(None)
        self.command.assert_called_once()

        self.command.reset_mock()
        # Simulate Space key
        self.btn._on_key_invoke(None)
        self.command.assert_called_once()

    def test_mouse_focus(self):
        # Clicking should set focus
        self.btn._on_click(None)
        self.btn.focus_set.assert_called_once()
        self.command.assert_called()

    def test_disabled_state_accessibility(self):
        # Disable button
        self.btn.set_disabled(True)
        # Check configure call for takefocus=0
        # self.btn.configure is a Mock
        # We look for call with takefocus=0

        # Depending on how configure is called. gui.py: self.configure(takefocus=0 if disabled else 1)
        self.btn.configure.assert_called_with(takefocus=0)

        # Enable button
        self.btn.set_disabled(False)
        self.btn.configure.assert_called_with(takefocus=1)

if __name__ == '__main__':
    unittest.main()
