"""
Deep Research Agents for AI Web Agency

Implements LLM-powered research agents for:
- Competitor analysis
- Local SEO research
- Menu/service extraction from assets
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field, ValidationError
from agentic_planner import ModelJsonPlanner, PlannerGenerationError, parse_json_object
from agentic_external_tools import build_research_tool_executor, research_tool_schemas

logger = logging.getLogger(__name__)


class CompetitorAnalysis(BaseModel):
    """Results from competitor analysis research"""
    competitors: list[str] = Field(default_factory=list, description="Identified competitor names")
    competitor_strengths: list[str] = Field(default_factory=list, description="Common strengths among competitors")
    competitor_weaknesses: list[str] = Field(default_factory=list, description="Common weaknesses among competitors")
    market_gaps: list[str] = Field(default_factory=list, description="Identified market gaps/opportunities")
    pricing_insights: str = Field(default="", description="Pricing strategy insights")
    differentiation_opportunities: list[str] = Field(default_factory=list, description="Ways to differentiate from competitors")
    grounded: bool = Field(
        default=False,
        description="Whether this used real web_search/read_page data, not just LLM inference from the business name/location alone.",
    )


class LocalSEOResearch(BaseModel):
    """Results from local SEO research"""
    target_keywords: list[str] = Field(default_factory=list, description="High-value SEO keywords")
    local_search_terms: list[str] = Field(default_factory=list, description="Location-specific search terms")
    content_recommendations: list[str] = Field(default_factory=list, description="Content ideas for SEO")
    directory_listings: list[str] = Field(default_factory=list, description="Recommended directory listings")
    review_strategy: str = Field(default="", description="Review generation strategy")
    local_optimization_tips: list[str] = Field(default_factory=list, description="Local SEO optimization tips")
    grounded: bool = Field(
        default=False,
        description="Whether this used real web_search/read_page data, not just LLM inference from the business name/location alone.",
    )


class MenuServiceExtraction(BaseModel):
    """Results from menu/service extraction from assets"""
    items: list[dict] = Field(default_factory=list, description="Extracted menu items or services")
    categories: list[str] = Field(default_factory=list, description="Service or menu categories")
    pricing_info: dict[str, Any] = Field(default_factory=dict, description="Pricing information")
    special_offers: list[str] = Field(default_factory=list, description="Special offers or promotions")
    business_highlights: list[str] = Field(default_factory=list, description="Key business highlights from assets")


class ResearchAgent:
    """Base class for research agents"""

    def __init__(self, planner: ModelJsonPlanner):
        self.planner = planner

    async def research(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute research and return results"""
        raise NotImplementedError

    async def _generate_grounded(self, prompt: str, schema: type, max_new_tokens: int = 900):
        """Runs the prompt through real web_search/read_page tool-calling instead of
        pure LLM guesswork -- the model decides for itself whether real data is worth
        fetching (see agentic_external_tools.research_tool_schemas). Sets the result's
        `grounded` field so downstream consumers (code_generator.py) can tell fabricated
        output apart from output actually backed by a real search/page fetch."""
        research_executor, research_calls = build_research_tool_executor()
        raw = await asyncio.to_thread(
            self.planner.generate_with_tools,
            prompt,
            research_tool_schemas(),
            research_executor,
            max_new_tokens=max_new_tokens,
            max_iterations=6,
            timeout=60.0,
        )
        parsed = parse_json_object(raw)
        result = schema.model_validate(parsed)
        result.grounded = bool(research_calls["calls"])
        return result


class CompetitorAnalysisAgent(ResearchAgent):
    """Research agent for competitor analysis"""
    
    async def research(self, context: dict[str, Any]) -> CompetitorAnalysis:
        """Analyze competitors based on business profile and location"""
        business_name = context.get("name", "")
        location = context.get("location", "")
        details = context.get("details", "")
        vertical = context.get("vertical", "unknown")
        
        prompt = f"""
        Analyze the competitive landscape for this business:

        Business Name: {business_name}
        Location: {location}
        Business Type: {vertical}
        Business Details: {details}

        Identify:
        1. Likely competitors in the same location and vertical
        2. Common strengths these competitors have
        3. Common weaknesses or gaps in the market
        4. Pricing insights based on typical market rates
        5. Differentiation opportunities for this business

        You have two optional tools: web_search(query) to find real competitors in this
        location/vertical, and read_page(url) to read a specific real competitor's site (from
        search results, or this business's own existing website if one was given). Use them if
        real data would make this analysis more accurate -- naming real competitors you found
        via search is far more useful than guessing plausible-sounding names. If you skip the
        tools, keep insights general (market patterns, not invented specific competitor names).

        Return STRICT JSON matching this schema: {{"competitors": [], "competitor_strengths": [],
        "competitor_weaknesses": [], "market_gaps": [], "pricing_insights": "", "differentiation_opportunities": []}}
        """

        try:
            return await self._generate_grounded(prompt, CompetitorAnalysis)
        except (PlannerGenerationError, ValidationError, ValueError) as e:
            logger.error(f"Competitor analysis failed: {e}")
            return CompetitorAnalysis()


class LocalSEOAgent(ResearchAgent):
    """Research agent for local SEO optimization"""
    
    async def research(self, context: dict[str, Any]) -> LocalSEOResearch:
        """Generate local SEO recommendations"""
        business_name = context.get("name", "")
        location = context.get("location", "")
        details = context.get("details", "")
        vertical = context.get("vertical", "unknown")
        target_audience = context.get("target_audience", "")
        
        prompt = f"""
        Generate local SEO recommendations for this business:

        Business Name: {business_name}
        Location: {location}
        Business Type: {vertical}
        Business Details: {details}
        Target Audience: {target_audience}

        Provide:
        1. High-value SEO keywords for this business
        2. Local search terms customers might use
        3. Content ideas that would improve local SEO
        4. Directory listings they should claim
        5. Review generation strategy
        6. Local optimization tips specific to their location and business type

        You have two optional tools: web_search(query) to check what's actually ranking for
        this business's likely search terms in this location, and read_page(url) to inspect a
        specific real page. Use them if real search data would sharpen the keyword/content
        recommendations; otherwise general location-and-vertical-based SEO advice is fine.

        Return STRICT JSON matching this schema: {{"target_keywords": [], "local_search_terms": [],
        "content_recommendations": [], "directory_listings": [], "review_strategy": "", "local_optimization_tips": []}}
        """

        try:
            return await self._generate_grounded(prompt, LocalSEOResearch)
        except (PlannerGenerationError, ValidationError, ValueError) as e:
            logger.error(f"Local SEO research failed: {e}")
            return LocalSEOResearch()


class MenuServiceExtractionAgent(ResearchAgent):
    """Research agent for extracting menu/service information from assets"""
    
    async def research(self, context: dict[str, Any]) -> MenuServiceExtraction:
        """Extract menu/service information from uploaded assets"""
        business_name = context.get("name", "")
        vertical = context.get("vertical", "unknown")
        assets = context.get("assets", [])
        asset_lines = []
        for i, asset in enumerate(assets):
            parsed = asset.get("parsed") or asset
            info = parsed.get("extracted_business_info") or {}
            signals = parsed.get("business_signals") or []
            items_visible = info.get("services_or_items") or info.get("menu_items") or []
            description = (
                asset.get("description")
                or parsed.get("description")
                or parsed.get("asset_type", "")
            )
            parts = [f"Asset {i+1} ({description or 'uploaded file'}):"]
            if items_visible:
                parts.append(f"  Items/services visible: {', '.join(str(x) for x in items_visible[:20])}")
            if signals:
                parts.append(f"  Business signals: {'; '.join(str(s) for s in signals[:10])}")
            if not items_visible and not signals:
                raw_text = asset.get("raw_text") or asset.get("text") or ""
                if raw_text:
                    parts.append(f"  Raw text: {raw_text[:500]}")
                else:
                    parts.append("  (no extractable content)")
            asset_lines.append("\n".join(parts))
        asset_descriptions = "\n".join(asset_lines) or "No asset content available."
        
        prompt = f"""
        Extract menu or service information from these business assets:
        
        Business Name: {business_name}
        Business Type: {vertical}
        
        Assets:
        {asset_descriptions}
        
        Extract:
        1. Individual menu items or services with descriptions
        2. Categories for organizing items/services
        3. Pricing information if available
        4. Any special offers or promotions mentioned
        5. Key business highlights or unique features
        
        Structure the extracted information clearly for website use.
        """
        
        try:
            result = await asyncio.to_thread(
                self.planner.generate_model,
                prompt,
                MenuServiceExtraction,
                2500,
            )
            return result
        except PlannerGenerationError as e:
            logger.error(f"Menu/service extraction failed: {e}")
            return MenuServiceExtraction()


class ResearchOrchestrator:
    """Orchestrates multiple research agents and combines results"""
    
    def __init__(self, planner: ModelJsonPlanner):
        self.competitor_agent = CompetitorAnalysisAgent(planner)
        self.seo_agent = LocalSEOAgent(planner)
        self.extraction_agent = MenuServiceExtractionAgent(planner)
    
    async def run_research(
        self,
        business_profile: dict[str, Any],
        assets: list[dict[str, Any]] = None,
        run_competitor: bool = True,
        run_seo: bool = True,
        run_extraction: bool = True
    ) -> dict[str, Any]:
        """Run selected research agents and return combined results"""
        results = {}
        context = {
            **business_profile,
            "assets": assets or [],
            "vertical": business_profile.get("vertical", "unknown")
        }
        
        if run_competitor:
            logger.info("Running competitor analysis...")
            results["competitor_analysis"] = await self.competitor_agent.research(context)
        
        if run_seo:
            logger.info("Running local SEO research...")
            results["local_seo"] = await self.seo_agent.research(context)
        
        if run_extraction and assets:
            logger.info("Running menu/service extraction...")
            results["menu_extraction"] = await self.extraction_agent.research(context)
        
        return results


if __name__ == "__main__":
    import asyncio
    
    async def test_research_agents():
        planner = ModelJsonPlanner()
        orchestrator = ResearchOrchestrator(planner)
        
        test_profile = {
            "name": "Bella Napoli",
            "location": "San Francisco",
            "details": "Family Italian restaurant serving pizza, pasta, desserts",
            "vertical": "restaurant",
            "target_audience": "Families and young professionals"
        }
        
        results = await orchestrator.run_research(
            business_profile=test_profile,
            run_competitor=True,
            run_seo=True,
            run_extraction=False
        )
        
        print("Research Results:")
        print(f"Competitor Analysis: {results.get('competitor_analysis')}")
        print(f"Local SEO: {results.get('local_seo')}")
    
    asyncio.run(test_research_agents())
