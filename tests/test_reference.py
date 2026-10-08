# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
from verification.reference import ReferencePosition
from tests import test_simulator


class ReferenceContractTests(test_simulator.PositionTests):
    """Identical literal expectations at a separately implemented rule seam."""
    position_type = ReferencePosition
