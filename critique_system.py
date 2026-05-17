"""
Critique & Debate Loop System

Multi-agent review system for evaluating generated websites:
- UX critique agent
- Accessibility critique agent
- Conversion critique agent
- Security critique agent
- Performance critique agent
- Debate/consensus mechanism
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from agentic_planner import ModelJsonPlanner, PlannerGenerationError

logger = logging.getLogger(__name__)


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return [str(value)]
    coerced: list[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            coerced.append(item)
        elif isinstance(item, dict):
            for key in ("suggestion", "description", "issue", "rationale", "name", "label", "text"):
                if key in item and isinstance(item[key], str):
                    coerced.append(item[key])
                    break
            else:
                parts = [f"{k}: {v}" for k, v in item.items() if isinstance(v, (str, int, float))]
                coerced.append("; ".join(parts) if parts else str(item))
        else:
            coerced.append(str(item))
    return coerced


class CritiqueReport(BaseModel):
    """Base model for critique reports"""
    agent_name: str
    score: int = Field(ge=0, le=100, description="Overall score out of 100")
    issues: List[str] = Field(default_factory=list, description="Identified issues")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    priority_issues: List[str] = Field(default_factory=list, description="High-priority issues")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in critique")

    @field_validator("issues", "suggestions", "priority_issues", mode="before")
    @classmethod
    def _coerce_base_lists(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)


class UXCritique(CritiqueReport):
    """UX-specific critique"""
    usability_issues: List[str] = Field(default_factory=list)
    navigation_issues: List[str] = Field(default_factory=list)
    visual_hierarchy_issues: List[str] = Field(default_factory=list)
    mobile_compatibility: str = Field(default="")


class AccessibilityCritique(CritiqueReport):
    """Accessibility-specific critique"""
    wcag_compliance: str = Field(default="")
    aria_issues: List[str] = Field(default_factory=list)
    color_contrast_issues: List[str] = Field(default_factory=list)
    keyboard_navigation: str = Field(default="")


class ConversionCritique(CritiqueReport):
    """Conversion-specific critique"""
    cta_issues: List[str] = Field(default_factory=list)
    funnel_issues: List[str] = Field(default_factory=list)
    trust_signals: List[str] = Field(default_factory=list)
    conversion_blocking_issues: List[str] = Field(default_factory=list)


class SecurityCritique(CritiqueReport):
    """Security-specific critique"""
    vulnerabilities: List[str] = Field(default_factory=list)
    data_privacy_issues: List[str] = Field(default_factory=list)
    authentication_issues: List[str] = Field(default_factory=list)
    input_validation_issues: List[str] = Field(default_factory=list)


class PerformanceCritique(CritiqueReport):
    """Performance-specific critique"""
    load_time_issues: List[str] = Field(default_factory=list)
    asset_optimization: List[str] = Field(default_factory=list)
    caching_issues: List[str] = Field(default_factory=list)
    code_efficiency: List[str] = Field(default_factory=list)

    @field_validator("load_time_issues", "asset_optimization", "caching_issues", "code_efficiency", mode="before")
    @classmethod
    def _coerce_perf_lists(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)


class DebateOutcome(BaseModel):
    """Result of debate between critique agents"""
    consensus_score: int = Field(ge=0, le=100, description="Overall consensus score")
    agreed_upon_issues: List[str] = Field(default_factory=list)
    disputed_issues: List[str] = Field(default_factory=list)
    final_recommendations: List[str] = Field(default_factory=list)
    approval_status: str = Field(default="needs_review", description="approved, needs_review, rejected")
    debate_summary: str = Field(default="")


class CritiqueAgent:
    """Base class for critique agents"""
    
    def __init__(self, planner: ModelJsonPlanner, agent_name: str):
        self.planner = planner
        self.agent_name = agent_name
    
    async def critique(self, code: str, build_spec: dict[str, Any]) -> CritiqueReport:
        """Execute critique and return report"""
        raise NotImplementedError


class UXCritiqueAgent(CritiqueAgent):
    """UX critique agent"""
    
    def __init__(self, planner: ModelJsonPlanner):
        super().__init__(planner, "UX Critique Agent")
    
    async def critique(self, code: str, build_spec: dict[str, Any]) -> UXCritique:
        """Critique UX aspects of generated code"""
        business = build_spec.get("business", {})
        vertical = business.get("vertical", "unknown")
        
        prompt = f"""
        Critique the UX of this generated website code for a {vertical} business:
        
        Business: {business.get('name', '')}
        Goal: {business.get('goal', '')}
        Target Audience: {business.get('target_audience', '')}
        
        Code snippet:
        {code[:2000]}
        
        Evaluate:
        1. Overall usability (0-100)
        2. Navigation clarity and structure
        3. Visual hierarchy and information architecture
        4. Mobile responsiveness
        5. User flow alignment with business goal
        
        Identify specific issues and provide actionable suggestions.
        """
        
        try:
            result = await asyncio.to_thread(
                self.planner.generate_model,
                prompt,
                UXCritique,
                2500,
            )
            result.agent_name = self.agent_name
            return result
        except PlannerGenerationError as e:
            logger.error(f"UX critique failed: {e}")
            return UXCritique(
                agent_name=self.agent_name,
                score=50,
                issues=["Unable to perform full UX critique"],
                suggestions=["Manual UX review recommended"]
            )


class AccessibilityCritiqueAgent(CritiqueAgent):
    """Accessibility critique agent"""
    
    def __init__(self, planner: ModelJsonPlanner):
        super().__init__(planner, "Accessibility Critique Agent")
    
    async def critique(self, code: str, build_spec: dict[str, Any]) -> AccessibilityCritique:
        """Critique accessibility aspects of generated code"""
        prompt = f"""
        Critique the accessibility of this generated website code:
        
        Code snippet:
        {code[:2000]}
        
        Evaluate:
        1. WCAG compliance level (A, AA, AAA, or none)
        2. ARIA attribute usage
        3. Color contrast ratios
        4. Keyboard navigation support
        5. Screen reader compatibility
        
        Identify specific accessibility violations and provide fixes.
        """
        
        try:
            result = await asyncio.to_thread(
                self.planner.generate_model,
                prompt,
                AccessibilityCritique,
                2500,
            )
            result.agent_name = self.agent_name
            return result
        except PlannerGenerationError as e:
            logger.error(f"Accessibility critique failed: {e}")
            return AccessibilityCritique(
                agent_name=self.agent_name,
                score=50,
                issues=["Unable to perform full accessibility critique"],
                suggestions=["Manual accessibility audit recommended"],
                wcag_compliance="unknown"
            )


class ConversionCritiqueAgent(CritiqueAgent):
    """Conversion critique agent"""
    
    def __init__(self, planner: ModelJsonPlanner):
        super().__init__(planner, "Conversion Critique Agent")
    
    async def critique(self, code: str, build_spec: dict[str, Any]) -> ConversionCritique:
        """Critique conversion aspects of generated code"""
        business = build_spec.get("business", {})
        goal = business.get("goal", "")
        
        prompt = f"""
        Critique the conversion optimization of this generated website code:
        
        Business Goal: {goal}
        
        Code snippet:
        {code[:2000]}
        
        Evaluate:
        1. CTA clarity and prominence
        2. Conversion funnel structure
        3. Trust signals and social proof
        4. Friction points in user journey
        5. Alignment with stated business goal
        
        Identify conversion blockers and provide optimization suggestions.
        """
        
        try:
            result = await asyncio.to_thread(
                self.planner.generate_model,
                prompt,
                ConversionCritique,
                2500,
            )
            result.agent_name = self.agent_name
            return result
        except PlannerGenerationError as e:
            logger.error(f"Conversion critique failed: {e}")
            return ConversionCritique(
                agent_name=self.agent_name,
                score=50,
                issues=["Unable to perform full conversion critique"],
                suggestions=["Manual conversion review recommended"]
            )


class SecurityCritiqueAgent(CritiqueAgent):
    """Security critique agent"""
    
    def __init__(self, planner: ModelJsonPlanner):
        super().__init__(planner, "Security Critique Agent")
    
    async def critique(self, code: str, build_spec: dict[str, Any]) -> SecurityCritique:
        """Critique security aspects of generated code"""
        prompt = f"""
        Critique the security of this generated website code:
        
        Code snippet:
        {code[:2000]}
        
        Evaluate:
        1. Common vulnerabilities (XSS, SQL injection, CSRF)
        2. Data privacy and handling
        3. Authentication and authorization
        4. Input validation and sanitization
        5. Sensitive data exposure
        
        Identify security risks and provide remediation steps.
        """
        
        try:
            result = await asyncio.to_thread(
                self.planner.generate_model,
                prompt,
                SecurityCritique,
                2500,
            )
            result.agent_name = self.agent_name
            return result
        except PlannerGenerationError as e:
            logger.error(f"Security critique failed: {e}")
            return SecurityCritique(
                agent_name=self.agent_name,
                score=50,
                issues=["Unable to perform full security critique"],
                suggestions=["Manual security audit recommended"]
            )


class PerformanceCritiqueAgent(CritiqueAgent):
    """Performance critique agent"""
    
    def __init__(self, planner: ModelJsonPlanner):
        super().__init__(planner, "Performance Critique Agent")
    
    async def critique(self, code: str, build_spec: dict[str, Any]) -> PerformanceCritique:
        """Critique performance aspects of generated code"""
        prompt = f"""
        Critique the performance of this generated website code:
        
        Code snippet:
        {code[:2000]}
        
        Evaluate:
        1. Load time optimization
        2. Asset optimization (images, CSS, JS)
        3. Caching strategy
        4. Code efficiency and bundle size
        5. Rendering performance
        
        Identify performance bottlenecks and provide optimization recommendations.
        """
        
        try:
            result = await asyncio.to_thread(
                self.planner.generate_model,
                prompt,
                PerformanceCritique,
                2500,
            )
            result.agent_name = self.agent_name
            return result
        except PlannerGenerationError as e:
            logger.error(f"Performance critique failed: {e}")
            return PerformanceCritique(
                agent_name=self.agent_name,
                score=50,
                issues=["Unable to perform full performance critique"],
                suggestions=["Manual performance audit recommended"]
            )


class CritiqueOrchestrator:
    """Orchestrates multiple critique agents and debate process"""
    
    def __init__(self, planner: ModelJsonPlanner):
        self.ux_agent = UXCritiqueAgent(planner)
        self.accessibility_agent = AccessibilityCritiqueAgent(planner)
        self.conversion_agent = ConversionCritiqueAgent(planner)
        self.security_agent = SecurityCritiqueAgent(planner)
        self.performance_agent = PerformanceCritiqueAgent(planner)
    
    async def run_critique(
        self,
        code: str,
        build_spec: dict[str, Any],
        agents: List[str] = None
    ) -> dict[str, Any]:
        """Run selected critique agents and return reports"""
        if agents is None:
            agents = ["ux", "accessibility", "conversion", "security", "performance"]
        
        results = {}
        
        if "ux" in agents:
            logger.info("Running UX critique...")
            results["ux"] = await self.ux_agent.critique(code, build_spec)
        
        if "accessibility" in agents:
            logger.info("Running accessibility critique...")
            results["accessibility"] = await self.accessibility_agent.critique(code, build_spec)
        
        if "conversion" in agents:
            logger.info("Running conversion critique...")
            results["conversion"] = await self.conversion_agent.critique(code, build_spec)
        
        if "security" in agents:
            logger.info("Running security critique...")
            results["security"] = await self.security_agent.critique(code, build_spec)
        
        if "performance" in agents:
            logger.info("Running performance critique...")
            results["performance"] = await self.performance_agent.critique(code, build_spec)
        
        return results
    
    async def run_debate(
        self,
        critique_reports: dict[str, CritiqueReport],
        build_spec: dict[str, Any]
    ) -> DebateOutcome:
        """Run debate process to reach consensus on critiques"""
        all_issues = []
        all_suggestions = []
        scores = []
        
        for agent_name, report in critique_reports.items():
            all_issues.extend(report.issues)
            all_suggestions.extend(report.suggestions)
            scores.append(report.score)
        
        # Calculate consensus score
        consensus_score = int(sum(scores) / len(scores)) if scores else 50
        
        # Determine approval status
        if consensus_score >= 80:
            approval_status = "approved"
        elif consensus_score >= 60:
            approval_status = "needs_review"
        else:
            approval_status = "rejected"
        
        # Identify priority issues (mentioned by multiple agents)
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        priority_issues = [issue for issue, count in issue_counts.items() if count > 1]
        
        outcome = DebateOutcome(
            consensus_score=consensus_score,
            agreed_upon_issues=priority_issues,
            disputed_issues=[],
            final_recommendations=all_suggestions[:10],  # Top 10 suggestions
            approval_status=approval_status,
            debate_summary=f"Consensus score: {consensus_score}/100. {len(critique_reports)} agents participated."
        )
        
        return outcome


if __name__ == "__main__":
    import asyncio
    
    async def test_critique_system():
        planner = ModelJsonPlanner()
        orchestrator = CritiqueOrchestrator(planner)
        
        test_code = """
        import React from 'react';
        export default function TestPage() {
            return <div>Hello World</div>;
        }
        """
        
        test_build_spec = {
            "business": {
                "name": "Test Business",
                "goal": "increase conversions",
                "vertical": "restaurant"
            }
        }
        
        reports = await orchestrator.run_critique(test_code, test_build_spec, agents=["ux", "security"])
        debate_outcome = await orchestrator.run_debate(reports, test_build_spec)
        
        print("Critique Reports:", reports)
        print("Debate Outcome:", debate_outcome)
    
    asyncio.run(test_critique_system())
