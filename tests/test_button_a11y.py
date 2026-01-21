import sys
import unittest
from unittest.mock import MagicMock

class MockCanvas(MagicMock):
    def __init__(self, master=None, **kwargs):
        super().__init__()
        self.master = master
        if 'takefocus' in kwargs:
            self.takefocus = kwargs['takefocus']

    def _get_child_mock(self, **kw):
        return MagicMock(**kw)

mock_tk = MagicMock()
mock_tk.Canvas = MockCanvas

sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()

import gui

class TestStyledButtonA11y(unittest.TestCase):
    def setUp(self):
        self.parent = MagicMock()
        self.btn = gui.StyledButton(self.parent, "Test")

    def test_takefocus_init(self):
        passed_to_init = getattr(self.btn, 'takefocus', None) == 1

        configured = False
        for call in self.btn.configure.call_args_list:
             if 'takefocus' in call.kwargs and call.kwargs['takefocus'] == 1:
                configured = True

        self.assertTrue(passed_to_init or configured, "takefocus=1 should be set via init or configure")

    def test_bindings(self):
        """Test that necessary accessibility bindings are present."""
        bind_calls = [args[0] for args, _ in self.btn.bind.call_args_list]

        self.assertIn("<Return>", bind_calls, "Should bind <Return> key")
        self.assertIn("<space>", bind_calls, "Should bind <space> key")
        self.assertIn("<FocusIn>", bind_calls, "Should bind <FocusIn> event")
        self.assertIn("<FocusOut>", bind_calls, "Should bind <FocusOut> event")

    def test_initial_focus_state(self):
        """Test that focused state is initialized."""
        val = self.btn.focused
        self.assertIsInstance(val, bool, "focused attribute should be boolean")
        self.assertFalse(val, "focused should be False")

    def test_focus_visuals(self):
        """Test that focus events trigger redraw and visual changes."""
        # Reset mocks
        self.btn.delete.reset_mock()
        self.btn.create_line.reset_mock()

        # Simulate FocusIn
        self.btn._on_focus_in(None)

        self.assertTrue(self.btn.focused)
        self.btn.delete.assert_called_with("all")

        # Verify that create_line was called (because focused=True -> border=ACCENT_GLOW (truthy) -> _rounded_rect uses outline)
        # Note: In _draw, if focused, border is set. _rounded_rect is called with border.
        # _rounded_rect calls create_line if outline is present.
        self.assertTrue(self.btn.create_line.called, "create_line should be called for focus ring")

        # Simulate FocusOut
        self.btn.create_line.reset_mock()
        self.btn._on_focus_out(None)

        self.assertFalse(self.btn.focused)
        # In _draw, if not focused (and not hovered/accent), border might be default.
        # Default border is "#30363d". This is also truthy.
        # So create_line should still be called (now that we added lines for all borders).
        self.assertTrue(self.btn.create_line.called, "create_line should be called for normal border")

if __name__ == '__main__':
    unittest.main()
