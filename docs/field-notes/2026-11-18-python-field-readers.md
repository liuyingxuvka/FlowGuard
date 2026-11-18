# Python field readers in impact reports

FlowGuard 5.0.1 reported `0 red, 3 impact` while reviewing the new
appearance preference in PEMEL Aging Studio. One impact read:

> Settings.__post_init__ now writes Settings.appearance; 0 other writers,
> 0 readers of Settings

The application reads this value during startup, live Settings refresh and
JSON persistence. The three paths include a chained attribute, a local alias
and a directly annotated parameter.

In 5.0.1 the impact count in `intent/owners.py` uses Prisma queries and SQL
table readers. The Python extractor records attribute loads in
`symbol_reads`. Those loads are outside this count, so “0 readers” leaves
the caller with an incomplete picture of Python impact coverage. The
finding concerns reader coverage. The writer impact itself is valid.

## Reproduction

The following fixture reproduced the same `0 readers` message with
`flowguard check --static --base HEAD`. Commit the fixture in a disposable
repository, then replace the `pass` in `__post_init__` with the assignment
in its comment and run the check.

```python
from dataclasses import asdict, dataclass, replace


@dataclass
class Settings:
    appearance: str = "light"

    def __post_init__(self):
        pass  # Changed version: self.appearance = self.appearance.strip()


@dataclass
class Controller:
    settings: Settings


def direct(settings: Settings):
    return settings.appearance


def chained(controller: Controller):
    return controller.settings.appearance


def aliased(controller: Controller):
    settings = controller.settings
    return settings.appearance


def serialized(settings: Settings):
    return asdict(settings)


def replacement(settings: Settings):
    return replace(settings, appearance="dark")
```

Label the present reader count as database coverage and report Python
coverage separately. A Python extension can start with reads from directly
annotated receivers and then handle proven chains and local aliases.
`asdict` can appear as a consumer of the whole object. Track `replace` as
construction of a new preferences value. Class identity matters because
the app also has a separate widget named `SettingsDialog.appearance`.
