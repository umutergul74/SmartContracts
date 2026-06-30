"""External analyzer adapters with uniform, non-fatal results."""

from scbounty.analyzers.aderyn import AderynAdapter
from scbounty.analyzers.echidna import EchidnaAdapter
from scbounty.analyzers.foundry import FoundryAdapter
from scbounty.analyzers.halmos import HalmosAdapter
from scbounty.analyzers.medusa import MedusaAdapter
from scbounty.analyzers.mythril import MythrilAdapter
from scbounty.analyzers.semgrep import SemgrepAdapter
from scbounty.analyzers.slither import SlitherAdapter
from scbounty.analyzers.solhint import SolhintAdapter

__all__ = [
    "AderynAdapter",
    "EchidnaAdapter",
    "FoundryAdapter",
    "HalmosAdapter",
    "MedusaAdapter",
    "MythrilAdapter",
    "SemgrepAdapter",
    "SlitherAdapter",
    "SolhintAdapter",
]
