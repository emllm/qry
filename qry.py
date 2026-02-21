"""Legacy script entrypoint for qry.

Prefer:
  - ``python -m qry``
  - ``qry`` (console script)
"""

import sys

from qry.cli.commands import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
