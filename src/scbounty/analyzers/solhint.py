from scbounty.analyzers.base import AvailabilityOnlyAdapter


class SolhintAdapter(AvailabilityOnlyAdapter):
    name = "solhint"
    executable = "solhint"
