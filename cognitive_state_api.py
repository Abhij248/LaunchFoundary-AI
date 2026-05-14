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


    def get_failed_critiques(
        self,
    ):

        critiques = (
            self.state
            .critique_reports
        )

        return [
            critique
            for critique in critiques
            if critique.get(
                "severity",
                0,
            ) > 0.7
        ]


    def get_behavioral_conflicts(
        self,
    ):

        blend = (
            self.state
            .behavioral_blend
        )

        return blend.get(
            "conflict_notes",
            []
        )
    

    def get_simulation_failures(
        self,
    ):

        report = (
            self.state
            .simulation_report
        )

        return report.get(
            "systemic_issues",
            []
        )
    

    def get_uncertainty_level(
        self,
    ):

        return (
            self.state
            .uncertainty_score
        )
    

    def get_design_candidates(
        self,
    ):

        return (
            self.state
            .design_candidates
        )

    def get_reasoning_diversity(
            self,
        ):

            candidates = (
                self.state
                .candidate_history
            )

            return min(
                1.0,
                len(candidates) / 4,
            )
        

    def get_convergence_risk(
            self,
        ):

            uncertainty = (
                self.state
                .uncertainty_score
            )

            reflection = (
                self.state
                .reflection_report
            )

            diversity = (
                reflection
                .strategic_diversity
                if reflection
                else 5
            )

            return min(
                1.0,
                (
                    uncertainty * 0.6
                )
                +
                (
                    (10 - diversity)
                    / 10
                    * 0.4
                )
            )


    def get_hallucination_risk(
            self,
        ):

            fallback_count = len([
                note
                for note in (
                    self.state.reasoning_notes
                )
                if "fallback" in note.lower()
            ])

            return min(
                1.0,
                fallback_count / 6,
            )