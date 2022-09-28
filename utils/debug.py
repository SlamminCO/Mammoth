import sys
import datetime


class DebugPrinter:
    def __init__(self, name: str, allow_printing: bool) -> None:
        self.name = name
        self.allow_printing = allow_printing

    def dprint(self, *objects, sep=" ", end="\n", file=sys.stdout, flush=False):
        if not self.allow_printing:
            return

        d = datetime.date.today()
        t = datetime.datetime.now()
        prefix = (
            f"{d.year}-{d.month}-{d.day} {t.hour}:{t.minute}:{t.second} | {self.name} |"
        )
        objects = [prefix, *objects]

        print(*objects, sep=sep, end=end, file=file, flush=flush)
