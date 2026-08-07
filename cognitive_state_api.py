from agentic_models import (
    WebsiteAgentState,
)

class CognitiveStateAPI:

    def __init__(
        self,
        state: WebsiteAgentState,
    ):

        self.state = state


    def get_active_strategy_candidates(
        self,
    ):

        return (
            self.state
            .strategy_hypotheses
        )


    def get_uncertainty_level(
        self,
    ):

        return (
            self.state
            .uncertainty_score
        )
