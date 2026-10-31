# DracoHatchery

A game in development. This repository currently contains art assets and a
small **text-only prototype** for testing the dragon genetics before the art is
hooked up. Python 3, standard library only.

## Play

```
python3 play.py              # random game
python3 play.py --seed 42    # repeatable game
python3 play.py --load savegame.json
```

Commands: `help`, `flock`, `view <dragon>`, `breed <a> <b>`, `name <dragon> <name>`,
`release <dragon>`, `next day`, `discoveries`, `save [file]`, `load [file]`, `quit`.
Dragons can be referred to by id number or name (quote names with spaces in `breed`).
Hidden debug command: `reveal <dragon>` shows both alleles per slot.

## Tests

```
python3 -m unittest
```

The tests simulate thousands of seeded breedings to check element odds
(same element, 40/40/20 recipes, 50/50 otherwise), Mendelian ratios
(e.g. two carriers show a recessive ~25% of the time), and the ~2% mutation rate.

## Layout

| Path | Purpose |
| --- | --- |
| `data/elements.json` | The 15 elements, combination recipes, ancestry marking names, discovery messages, and empty `palette` / `signature_decorations` placeholders |
| `data/parts.json` | Body slots and variants. Variant ids (e.g. `tail_long`) are meant to match future sprite filenames. `"mutation": true` marks mutation-only variants |
| `data/config.json` | Element inheritance odds, mutation chance, aging days, rest days, flock cap, starter dragons and weights |
| `dracohatchery/genetics.py` | Pure genetics rules (element rolls, allele inheritance, dominance, mutation, markings) |
| `dracohatchery/game.py` | Game state and actions (`Game`), save/load; no printing or input, so a graphical version can reuse it |
| `dracohatchery/models.py` | The `Dragon` data object |
| `dracohatchery/cli.py` | The text interface only |
| `tests/` | Unit and statistical tests |

## Rule notes

- Eggs hatch immediately into hatchlings after the Gene Pool scene.
- If a dragon's two alleles for a slot are different but have the same dominance
  (two dominants, or two different recessives), one is picked at random at
  hatching and stored, so it never changes.
- Each dragon stores its parents' elements, so ancestry markings from
  grandparents still work after ancestors are released.
- Saves are JSON and include the random generator state, so a seeded game
  stays repeatable across save/load.
