from scbounty.analyzers.base import AvailabilityOnlyAdapter


class EchidnaAdapter(AvailabilityOnlyAdapter):
    name = "echidna"
    executable = "echidna-test"
