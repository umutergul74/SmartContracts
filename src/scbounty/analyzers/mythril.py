from scbounty.analyzers.base import AvailabilityOnlyAdapter


class MythrilAdapter(AvailabilityOnlyAdapter):
    name = "mythril"
    executable = "myth"
