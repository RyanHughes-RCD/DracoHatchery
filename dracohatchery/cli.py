"""Text interface. All game rules live in game.py / genetics.py; this file
only parses commands and prints results."""

import argparse
import shlex

from .game import Game, GameError

DEFAULT_SAVE = "savegame.json"

HELP = """Commands:
  help                     Show this help
  flock                    List your dragons
  view <dragon>            Look at a dragon
  breed <a> <b>            Breed two adult dragons in the Gene Pool
  name <dragon> <name>     Rename a dragon
  release <dragon>         Release a dragon into the wild
  next day                 Let a day pass (dragons age and rest)
  discoveries              Elements you have discovered
  save [file]              Save the game (default: savegame.json)
  load [file]              Load a saved game
  quit                     Leave the hatchery
Dragons can be named by id number or by name. Use quotes for names with spaces."""


class TextUI:
    def __init__(self, game, input_fn=input, output_fn=print):
        self.game = game
        self.input = input_fn
        self.out = output_fn
        self.running = True

    # Helpers -----------------------------------------------------------------

    @property
    def data(self):
        return self.game.data

    def el(self, element_id):
        return self.data.element_name(element_id)

    def label(self, dragon):
        return f"#{dragon.id} {dragon.name}"

    def describe_odds(self, odds):
        return ", ".join(f"{self.el(e)} {p * 100:.0f}%" for e, p in odds.items())

    # Loop --------------------------------------------------------------------

    def run(self):
        self.out("Welcome to the DracoHatchery! Type 'help' for commands.")
        self.out(f"Day {self.game.day}. You have {len(self.game.flock)} dragons.")
        while self.running:
            try:
                line = self.input("\n> ")
            except (EOFError, KeyboardInterrupt):
                self.out("")
                break
            self.handle(line)
        self.out("Farewell, keeper.")

    def handle(self, line):
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        if not parts:
            return
        cmd, args = parts[0].lower(), parts[1:]
        handler = {
            "help": self.cmd_help,
            "flock": self.cmd_flock,
            "view": self.cmd_view,
            "breed": self.cmd_breed,
            "name": self.cmd_name,
            "release": self.cmd_release,
            "next": self.cmd_next,
            "discoveries": self.cmd_discoveries,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
            "reveal": self.cmd_reveal,   # hidden debug command
        }.get(cmd)
        if handler is None:
            self.out(f"Unknown command '{cmd}'. Type 'help' for commands.")
            return
        try:
            handler(args)
        except GameError as e:
            self.out(str(e))

    def need(self, args, count, usage):
        if len(args) < count:
            raise GameError(f"Usage: {usage}")

    # Commands ----------------------------------------------------------------

    def cmd_help(self, args):
        self.out(HELP)

    def cmd_flock(self, args):
        g = self.game
        self.out(f"Day {g.day} - flock {len(g.flock)}/{g.flock_cap}")
        for d in g.flock:
            status = d.stage
            if d.is_adult and d.rest_days > 0:
                status += ", resting"
            self.out(f"  #{d.id:<3} {d.name:<22} {self.el(d.element):<10} {status}")

    def cmd_view(self, args):
        self.need(args, 1, "view <dragon>")
        d = self.game.get(" ".join(args))
        self.out(f"{self.label(d)}")
        self.out(f"  Element:    {self.el(d.element)}")
        age = f"{d.stage} ({d.age_days} day{'s' if d.age_days != 1 else ''} old)"
        if d.is_adult and d.rest_days > 0:
            age += ", resting"
        self.out(f"  Age:        {age}")
        self.out(f"  Generation: {d.generation}")
        self.out("  Traits:")
        for slot in self.data.slots:
            self.out(f"    {slot:<6} {self.data.variant_name(d.traits[slot])}")
        if d.markings:
            self.out("  Markings:")
            for m in d.markings:
                self.out(f"    {m['description']}")
        else:
            self.out("  Markings:   none")
        self.out(f"  Parents:    {self.parents_text(d)}")

    def parents_text(self, d):
        if not d.parent_ids:
            return "unknown (wild-born)"
        names = []
        for pid, pel in zip(d.parent_ids, d.parent_elements):
            parent = self.game.get_by_id(pid)
            if parent:
                names.append(f"{self.label(parent)} ({self.el(pel)})")
            else:
                names.append(f"#{pid} (released, {self.el(pel)})")
        return " and ".join(names)

    def cmd_breed(self, args):
        self.need(args, 2, "breed <a> <b>")
        a, b = self.game.get(args[0]), self.game.get(args[1])
        self.game.check_breed(a, b)
        odds = self.game.breed_odds(a, b)
        self.out(f"{a.name} ({self.el(a.element)}) + {b.name} ({self.el(b.element)})")
        self.out(f"Element odds: {self.describe_odds(odds)}")
        answer = self.input("Lead them to the Gene Pool? (y/n) ").strip().lower()
        if answer not in ("y", "yes"):
            self.out("You lead them back to the flock.")
            return
        result = self.game.breed(a, b)
        self.narrate_gene_pool(a, b, result)

    def narrate_gene_pool(self, a, b, result):
        child = result.child
        self.out("")
        self.out(f"{a.name} and {b.name} wade into the Gene Pool.")
        self.out(f"The pool blooms with {self.el(a.element)} and {self.el(b.element)} hues, "
                 "a swirling whirlpool of color and light spinning faster and faster...")
        if result.mutated_slots:
            self.out("A strange shimmer ripples across the surface. Something unexpected stirs...")
        self.out(f"The colors draw together into a glowing {self.el(child.element)} egg!")
        self.out("The shell cracks, and a hatchling tumbles out.")
        if result.new_discovery:
            self.out("")
            self.out("*** NEW ELEMENT DISCOVERED ***")
            self.out(self.data.elements[child.element]["discovery_message"])
        self.out("")
        self.out(f"Welcome, {self.label(child)}! ({len(self.game.flock)}/{self.game.flock_cap} in flock)")
        self.out(f"{a.name} and {b.name} will rest for a day.")

    def cmd_name(self, args):
        self.need(args, 2, "name <dragon> <name>")
        d = self.game.get(args[0])
        old = d.name
        self.game.rename(d, " ".join(args[1:]))
        self.out(f"{old} is now called {d.name}.")

    def cmd_release(self, args):
        self.need(args, 1, "release <dragon>")
        d = self.game.get(" ".join(args))
        answer = self.input(f"Release {d.name} forever? (y/n) ").strip().lower()
        if answer in ("y", "yes"):
            self.game.release(d)
            self.out(f"{d.name} spreads its wings and flies off into the wild.")
        else:
            self.out(f"{d.name} stays with the flock.")

    def cmd_next(self, args):
        if args and args[0].lower() != "day":
            raise GameError("Usage: next day")
        report = self.game.next_day()
        self.out(f"The sun rises on day {report.day}.")
        for d, stage in report.grew_up:
            self.out(f"  {d.name} has grown into a {stage}!")
        for d in report.rested:
            self.out(f"  {d.name} is rested and ready to breed.")

    def cmd_discoveries(self, args):
        total = len(self.data.elements)
        found = self.game.discovered
        self.out(f"Elements discovered: {len(found)}/{total}")
        for e in self.data.elements:
            mark = self.el(e) if e in found else "???"
            self.out(f"  {mark}")

    def cmd_save(self, args):
        path = args[0] if args else DEFAULT_SAVE
        try:
            self.game.save(path)
        except OSError as e:
            raise GameError(f"Could not save: {e}")
        self.out(f"Game saved to {path}.")

    def cmd_load(self, args):
        path = args[0] if args else DEFAULT_SAVE
        try:
            self.game = Game.load(path, self.data)
        except (OSError, ValueError, KeyError) as e:
            raise GameError(f"Could not load {path}: {e}")
        self.out(f"Game loaded from {path}. Day {self.game.day}.")

    def cmd_quit(self, args):
        self.running = False

    def cmd_reveal(self, args):
        """Debug: show both alleles per slot."""
        self.need(args, 1, "reveal <dragon>")
        d = self.game.get(" ".join(args))
        self.out(f"[debug] Genes of {self.label(d)}:")
        for slot in self.data.slots:
            genes = []
            for allele in d.alleles[slot]:
                v = self.data.variants[allele]
                tag = "D" if v["dominance"] == "dominant" else "r"
                if v.get("mutation"):
                    tag += ", mutation"
                genes.append(f"{v['name']} ({tag})")
            shown = self.data.variant_name(d.traits[slot])
            self.out(f"  {slot:<6} {' / '.join(genes):<45} -> {shown}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="DracoHatchery - text dragon breeding")
    parser.add_argument("--seed", type=int, default=None, help="random seed for a repeatable game")
    parser.add_argument("--load", metavar="FILE", help="start from a saved game")
    args = parser.parse_args(argv)
    game = Game.load(args.load) if args.load else Game.new_game(seed=args.seed)
    TextUI(game).run()


if __name__ == "__main__":
    main()
