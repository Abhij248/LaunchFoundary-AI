"""
Template + AI-Assisted Code Generation System

Generates website code using a hybrid approach:
- Base templates for common verticals (restaurant, clinic, service)
- AI customization based on BuildSpec
- Next.js/React + Tailwind output
"""

from __future__ import annotations
import logging
from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from agentic_planner import ModelJsonPlanner, PlannerGenerationError

logger = logging.getLogger(__name__)


class GeneratedCode(BaseModel):
    """Generated website code structure"""
    pages: dict[str, str] = Field(default_factory=dict, description="Generated page code by page name")
    components: dict[str, str] = Field(default_factory=dict, description="Generated component code")
    styles: str = Field(default="", description="Custom CSS/Tailwind configuration")
    config: dict[str, Any] = Field(default_factory=dict, description="Configuration files")
    html_preview: str = Field(default="", description="Static HTML preview with real business values")


class TemplateConfig(BaseModel):
    """Template configuration for code generation"""
    vertical: str
    pages: list[str]
    features: list[str]
    branding: dict[str, str]
    business_info: dict[str, Any]


# Base templates for different verticals
RESTAURANT_TEMPLATE = """
import React from 'react';
import Head from 'next/head';

export default function RestaurantPage({ business, branding }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>{business.name} - {business.location}</title>
        <meta name="description" content={business.unique_selling_points} />
      </Head>
      
      {/* Header */}
      <header style={{ backgroundColor: branding.primary_color }} className="text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold">{business.name}</h1>
          <p className="text-lg opacity-90">{business.location}</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-gray-100 to-gray-200">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold mb-4" style={{ color: branding.primary_color }}>
            Welcome to {business.name}
          </h2>
          <p className="text-xl text-gray-700 max-w-2xl mx-auto mb-8">
            {business.unique_selling_points}
          </p>
          <button 
            className="px-8 py-3 rounded-lg text-white font-semibold"
            style={{ backgroundColor: branding.accent_color }}
          >
            Order Now
          </button>
        </div>
      </section>

      {/* Menu Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Our Menu</h3>
          <div className="grid md:grid-cols-3 gap-6">
            {/* Menu items would be dynamically generated */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Signature Dish</h4>
              <p className="text-gray-600">Delicious description here</p>
              <p className="font-bold mt-2" style={{ color: branding.primary_color }}>$12.99</p>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-16 bg-gray-800 text-white">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Contact Us</h3>
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div>
              <h4 className="font-bold mb-2">Location</h4>
              <p className="text-gray-300">{business.location}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Hours</h4>
              <p className="text-gray-300">{business.business_hours}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Phone</h4>
              <p className="text-gray-300">{business.phone_number}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Email</h4>
              <p className="text-gray-300">{business.contact_email}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
"""

CLINIC_TEMPLATE = """
import React from 'react';
import Head from 'next/head';

export default function ClinicPage({ business, branding }) {
  return (
    <div className="min-h-screen bg-blue-50">
      <Head>
        <title>{business.name} - {business.location}</title>
        <meta name="description" content={business.unique_selling_points} />
      </Head>
      
      {/* Header */}
      <header style={{ backgroundColor: branding.primary_color }} className="text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold">{business.name}</h1>
          <p className="text-lg opacity-90">{business.location}</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-blue-100 to-blue-200">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold mb-4" style={{ color: branding.primary_color }}>
            Your Health, Our Priority
          </h2>
          <p className="text-xl text-gray-700 max-w-2xl mx-auto mb-8">
            {business.unique_selling_points}
          </p>
          <button 
            className="px-8 py-3 rounded-lg text-white font-semibold"
            style={{ backgroundColor: branding.accent_color }}
          >
            Book Appointment
          </button>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Our Services</h3>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">General Checkup</h4>
              <p className="text-gray-600">Comprehensive health assessments</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Specialist Care</h4>
              <p className="text-gray-600">Expert medical specialists</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Emergency Care</h4>
              <p className="text-gray-600">24/7 emergency services</p>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-16 bg-gray-800 text-white">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Contact Us</h3>
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div>
              <h4 className="font-bold mb-2">Location</h4>
              <p className="text-gray-300">{business.location}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Hours</h4>
              <p className="text-gray-300">{business.business_hours}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Phone</h4>
              <p className="text-gray-300">{business.phone_number}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Email</h4>
              <p className="text-gray-300">{business.contact_email}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
"""

SERVICE_TEMPLATE = """
import React from 'react';
import Head from 'next/head';

export default function ServicePage({ business, branding }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>{business.name} - {business.location}</title>
        <meta name="description" content={business.unique_selling_points} />
      </Head>
      
      {/* Header */}
      <header style={{ backgroundColor: branding.primary_color }} className="text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold">{business.name}</h1>
          <p className="text-lg opacity-90">{business.location}</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-orange-100 to-orange-200">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold mb-4" style={{ color: branding.primary_color }}>
            Expert Services You Can Trust
          </h2>
          <p className="text-xl text-gray-700 max-w-2xl mx-auto mb-8">
            {business.unique_selling_points}
          </p>
          <button 
            className="px-8 py-3 rounded-lg text-white font-semibold"
            style={{ backgroundColor: branding.accent_color }}
          >
            Get a Quote
          </button>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Our Services</h3>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Repair Services</h4>
              <p className="text-gray-600">Fast and reliable repairs</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Maintenance</h4>
              <p className="text-gray-600">Preventive maintenance plans</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Emergency Service</h4>
              <p className="text-gray-600">24/7 emergency support</p>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-16 bg-gray-800 text-white">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Contact Us</h3>
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div>
              <h4 className="font-bold mb-2">Service Area</h4>
              <p className="text-gray-300">{business.location}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Hours</h4>
              <p className="text-gray-300">{business.business_hours}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Phone</h4>
              <p className="text-gray-300">{business.phone_number}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Email</h4>
              <p className="text-gray-300">{business.contact_email}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
"""


class CodeGenerator:
    """Template + AI-assisted code generator"""
    
    def __init__(self, planner: Optional[ModelJsonPlanner] = None):
        self.planner = planner
        self.templates = {
            "restaurant": RESTAURANT_TEMPLATE,
            "clinic": CLINIC_TEMPLATE,
            "repair_service": SERVICE_TEMPLATE,
            "service": SERVICE_TEMPLATE,
        }
    
    def get_template_for_vertical(self, vertical: str) -> str:
        """Get base template for a given vertical"""
        return self.templates.get(vertical, self.templates["restaurant"])

    def generate_html_preview(self, build_spec: dict[str, Any]) -> str:
        """Generate a static HTML page with real business values substituted in"""
        business = build_spec.get("business", {})
        branding = business.get("branding", business)
        name = business.get("name", "Business")
        location = business.get("location", "")
        usp = business.get("unique_selling_points", "")
        hours = business.get("business_hours", "")
        phone = business.get("phone_number", "")
        email = business.get("contact_email", business.get("email", ""))
        vertical = business.get("vertical", "restaurant")
        primary = branding.get("primary_color", "#3b82f6")
        accent = branding.get("accent_color", "#f59e0b")
        cta = {"restaurant": "Order Now", "clinic": "Book Appointment"}.get(vertical, "Get a Quote")
        section_title = {"restaurant": "Our Menu", "clinic": "Our Services"}.get(vertical, "Our Services")
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            f"  <title>{name}</title>\n"
            "  <style>\n"
            "    *{box-sizing:border-box;margin:0;padding:0}\n"
            "    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb}\n"
            f"    header{{background:{primary};color:#fff;padding:1.5rem 2rem}}\n"
            "    header h1{font-size:2rem;font-weight:700}\n"
            "    header p{opacity:.8;margin-top:.25rem}\n"
            "    .hero{background:linear-gradient(135deg,#f3f4f6,#e5e7eb);padding:4rem 2rem;text-align:center}\n"
            f"    .hero h2{{font-size:2.25rem;font-weight:700;color:{primary};margin-bottom:1rem}}\n"
            "    .hero p{font-size:1.05rem;color:#374151;max-width:580px;margin:0 auto 1.5rem}\n"
            f"    .btn{{background:{accent};color:#fff;border:none;padding:.75rem 2rem;border-radius:.5rem;font-size:1rem;font-weight:600;cursor:pointer}}\n"
            "    .section{padding:3rem 2rem}\n"
            "    .section h3{font-size:1.5rem;font-weight:700;text-align:center;margin-bottom:1.5rem}\n"
            "    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;max-width:800px;margin:0 auto}\n"
            f"    .card{{background:#fff;border-radius:.75rem;box-shadow:0 1px 4px rgba(0,0,0,.08);padding:1.25rem}}\n"
            f"    .card h4{{font-weight:600;margin-bottom:.4rem;color:{primary}}}\n"
            "    .card p{font-size:.9rem;color:#6b7280}\n"
            "    .contact{background:#1f2937;color:#fff;padding:3rem 2rem}\n"
            "    .contact h3{font-size:1.5rem;font-weight:700;text-align:center;margin-bottom:1.5rem}\n"
            "    .cg{display:grid;grid-template-columns:repeat(2,1fr);gap:1.25rem;max-width:600px;margin:0 auto}\n"
            "    .ci h4{font-weight:600;margin-bottom:.2rem}\n"
            "    .ci p{color:#d1d5db;font-size:.9rem}\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <header>\n"
            f"    <h1>{name}</h1>\n"
            f"    <p>{location}</p>\n"
            "  </header>\n"
            "  <section class=\"hero\">\n"
            f"    <h2>Welcome to {name}</h2>\n"
            f"    <p>{usp}</p>\n"
            f"    <button class=\"btn\">{cta}</button>\n"
            "  </section>\n"
            "  <section class=\"section\">\n"
            f"    <h3>{section_title}</h3>\n"
            "    <div class=\"cards\">\n"
            f"      <div class=\"card\"><h4>Our Speciality</h4><p>{usp}</p></div>\n"
            f"      <div class=\"card\"><h4>Hours</h4><p>{hours}</p></div>\n"
            f"      <div class=\"card\"><h4>Get in Touch</h4><p>{phone}</p></div>\n"
            "    </div>\n"
            "  </section>\n"
            "  <section class=\"contact\">\n"
            "    <h3>Contact Us</h3>\n"
            "    <div class=\"cg\">\n"
            f"      <div class=\"ci\"><h4>Location</h4><p>{location}</p></div>\n"
            f"      <div class=\"ci\"><h4>Hours</h4><p>{hours}</p></div>\n"
            f"      <div class=\"ci\"><h4>Phone</h4><p>{phone}</p></div>\n"
            f"      <div class=\"ci\"><h4>Email</h4><p>{email}</p></div>\n"
            "    </div>\n"
            "  </section>\n"
            "</body>\n"
            "</html>"
        )
    
    def customize_template_with_ai(
        self,
        template: str,
        build_spec: dict[str, Any]
    ) -> str:
        """Use AI to customize template based on BuildSpec"""
        if not self.planner:
            logger.warning("No planner available, returning template without AI customization")
            return template
        
        business = build_spec.get("business", {})
        features = build_spec.get("includedFeatures", [])
        
        prompt = f"""
        Customize this React template based on the following business information:
        
        Business Name: {business.get('name', '')}
        Location: {business.get('location', '')}
        Goal: {business.get('goal', '')}
        Unique Selling Points: {business.get('unique_selling_points', '')}
        Target Audience: {business.get('target_audience', '')}
        Business Hours: {business.get('business_hours', '')}
        
        Features to include: {', '.join([f.get('label', '') for f in features])}
        
        Template:
        {template}
        
        Customize the template to:
        1. Better reflect the business's unique selling points
        2. Include relevant features from the BuildSpec
        3. Tailor content to the target audience
        4. Add appropriate sections based on the business goal
        
        Return the complete customized React code.
        """
        
        try:
            # For now, return template as-is since AI customization would require
            # a different approach (text generation vs structured JSON)
            # In a full implementation, this would use the planner for text generation
            logger.info("AI customization skipped - using base template")
            return template
        except Exception as e:
            logger.error(f"AI customization failed: {e}")
            return template
    
    def generate_code(
        self,
        build_spec: dict[str, Any],
        use_ai_customization: bool = True
    ) -> GeneratedCode:
        """Generate website code from BuildSpec"""
        business = build_spec.get("business", {})
        vertical = business.get("vertical", "restaurant")
        
        # Get base template
        template = self.get_template_for_vertical(vertical)
        
        # Customize with AI if requested
        if use_ai_customization:
            template = self.customize_template_with_ai(template, build_spec)
        
        # Generate page code
        pages = {
            "index": template,
        }
        
        # Generate components
        components = {}
        
        # Generate styles
        branding = business.get("branding", {})
        styles = f"""
module.exports = {{
  theme: {{
    extend: {{
      colors: {{
        primary: '{branding.get('primary_color', '#3b82f6')}',
        secondary: '{branding.get('secondary_color', '#1e40af')}',
        accent: '{branding.get('accent_color', '#f59e0b')}',
      }},
    }},
  }},
}}
"""
        
        # Generate config
        config = {
            "business": business,
            "vertical": vertical,
            "features": build_spec.get("includedFeatures", []),
        }
        
        html_preview = self.generate_html_preview(build_spec)

        return GeneratedCode(
            pages=pages,
            components=components,
            styles=styles,
            config=config,
            html_preview=html_preview,
        )


class CodeGenerationOrchestrator:
    """Orchestrates code generation process"""
    
    def __init__(self, planner: Optional[ModelJsonPlanner] = None):
        self.generator = CodeGenerator(planner)
    
    def generate_website(
        self,
        build_spec: dict[str, Any],
        output_dir: Optional[Path] = None
    ) -> GeneratedCode:
        """Generate complete website from BuildSpec"""
        logger.info(f"Generating website for vertical: {build_spec.get('business', {}).get('vertical', 'unknown')}")
        
        generated_code = self.generator.generate_code(build_spec)
        
        # Optionally write to disk
        if output_dir:
            self.write_code_to_disk(generated_code, output_dir)
        
        return generated_code
    
    def write_code_to_disk(self, code: GeneratedCode, output_dir: Path) -> None:
        """Write generated code to disk"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write pages
        pages_dir = output_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        for page_name, page_code in code.pages.items():
            (pages_dir / f"{page_name}.js").write_text(page_code)
        
        # Write components
        components_dir = output_dir / "components"
        components_dir.mkdir(exist_ok=True)
        for component_name, component_code in code.components.items():
            (components_dir / f"{component_name}.js").write_text(component_code)
        
        # Write styles
        (output_dir / "tailwind.config.js").write_text(code.styles)
        
        # Write config
        import json
        (output_dir / "config.json").write_text(json.dumps(code.config, indent=2))
        
        logger.info(f"Code written to {output_dir}")


if __name__ == "__main__":
    # Test code generation
    test_build_spec = {
        "business": {
            "name": "Bella Napoli",
            "location": "San Francisco",
            "goal": "increase online orders and table reservations",
            "unique_selling_points": "Family recipes passed down 3 generations, wood-fired pizza",
            "target_audience": "Families and young professionals",
            "business_hours": "11am-10pm daily",
            "phone_number": "+1 (415) 555-0123",
            "contact_email": "hello@bellanapoli.example",
            "vertical": "restaurant",
            "branding": {
                "primary_color": "#dc2626",
                "secondary_color": "#1e3a8a",
                "accent_color": "#f59e0b",
            },
        },
        "includedFeatures": [
            {"label": "Online ordering"},
            {"label": "Menu display"},
            {"label": "Contact form"},
        ],
    }
    
    orchestrator = CodeGenerationOrchestrator()
    generated = orchestrator.generate_website(test_build_spec)
    
    print("Generated Code:")
    print(f"Pages: {list(generated.pages.keys())}")
    print(f"Components: {list(generated.components.keys())}")
    print(f"Styles length: {len(generated.styles)}")
