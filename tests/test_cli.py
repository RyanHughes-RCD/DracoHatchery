"""Smoke test of the text interface with scripted input."""

import unittest

from dracohatchery.cli import TextUI
from dracohatchery.game import Game


def run_script(lines, seed=1):
    inputs = iter(lines)
    output = []
    ui = TextUI(Game.new_game(seed=seed), input_fn=lambda prompt="": next(inputs),
                output_fn=lambda *a: output.append(" ".join(str(x) for x in a)))
    ui.run()
    return ui, "\n".join(output)


class TextUITests(unittest.TestCase):
    def test_breed_confirm_and_view(self):
        ui, out = run_script(["breed Cinder Brook", "y", "view 7", "reveal 7", "quit"])
        self.assertIn("Element odds: Fire 40%, Water 40%, Steam 20%", out)
        self.assertIn("Gene Pool", out)
        self.assertEqual(len(ui.game.flock), 7)
        self.assertIn("[debug] Genes of #7", out)

    def test_breed_declined(self):
        ui, out = run_script(["breed 1 2", "n", "quit"])
        self.assertEqual(len(ui.game.flock), 6)

    def test_help_hides_reveal(self):
        _, out = run_script(["help", "quit"])
        self.assertNotIn("reveal", out)

    def test_view_hides_genes(self):
        _, out = run_script(["view Cinder", "quit"])
        self.assertNotIn("(D)", out)
        self.assertIn("Traits:", out)

    def test_errors_are_friendly(self):
        _, out = run_script(["view Nobody", "breed 1", "next day", "next day", "quit"])
        self.assertIn("No dragon called 'Nobody'", out)
        self.assertIn("Usage: breed", out)
        self.assertIn("day 3", out)


if __name__ == "__main__":
    unittest.main()
