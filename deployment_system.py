"""
Deployment & Handover System

Handles production readiness:
- Database schema generation
- Authentication system
- Payment integration
- Deployment scripts
"""

from __future__ import annotations
import logging
from typing import Any, Optional, Dict
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DatabaseSchema(BaseModel):
    """Database schema for generated website"""
    tables: Dict[str, Any] = Field(default_factory=dict)
    relationships: list[str] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)
    migrations: list[str] = Field(default_factory=list)


class AuthConfig(BaseModel):
    """Authentication configuration"""
    provider: str = Field(default="local", description="local, oauth, jwt")
    user_fields: list[str] = Field(default_factory=list)
    session_config: Dict[str, Any] = Field(default_factory=dict)
    middleware_config: Dict[str, Any] = Field(default_factory=dict)


class PaymentConfig(BaseModel):
    """Payment integration configuration"""
    provider: str = Field(default="stripe", description="stripe, paypal, local")
    api_config: Dict[str, Any] = Field(default_factory=dict)
    webhook_config: Dict[str, Any] = Field(default_factory=dict)
    payment_methods: list[str] = Field(default_factory=list)


class DeploymentConfig(BaseModel):
    """Deployment configuration"""
    platform: str = Field(default="vercel", description="vercel, netlify, docker, custom")
    environment_vars: Dict[str, str] = Field(default_factory=dict)
    build_commands: list[str] = Field(default_factory=list)
    deployment_scripts: list[str] = Field(default_factory=list)


class DeploymentPackage(BaseModel):
    """Complete deployment package"""
    database_schema: DatabaseSchema
    auth_config: AuthConfig
    payment_config: Optional[PaymentConfig] = None
    deployment_config: DeploymentConfig
    readme: str = Field(default="")
    docker_compose: str = Field(default="")
    env_file: str = Field(default="")


class DatabaseSchemaGenerator:
    """Generates database schema based on BuildSpec"""
    
    def generate_schema(self, build_spec: dict[str, Any]) -> DatabaseSchema:
        """Generate database schema from BuildSpec"""
        business = build_spec.get("business", {})
        vertical = business.get("vertical", "unknown")
        features = build_spec.get("includedFeatures", [])
        
        tables = {
            "users": {
                "fields": [
                    "id: UUID PRIMARY KEY",
                    "email: VARCHAR(255) UNIQUE NOT NULL",
                    "password_hash: VARCHAR(255) NOT NULL",
                    "created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    "updated_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                ]
            },
            "business_profile": {
                "fields": [
                    "id: UUID PRIMARY KEY",
                    "user_id: UUID REFERENCES users(id)",
                    "name: VARCHAR(255) NOT NULL",
                    "location: VARCHAR(255)",
                    "contact_email: VARCHAR(255)",
                    "phone_number: VARCHAR(50)",
                    "business_hours: TEXT",
                    "created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                ]
            }
        }
        
        # Add vertical-specific tables
        if vertical == "restaurant":
            tables["menu_items"] = {
                "fields": [
                    "id: UUID PRIMARY KEY",
                    "business_id: UUID REFERENCES business_profile(id)",
                    "name: VARCHAR(255) NOT NULL",
                    "description: TEXT",
                    "price: DECIMAL(10,2)",
                    "category: VARCHAR(100)",
                    "available: BOOLEAN DEFAULT TRUE",
                ]
            }
            tables["orders"] = {
                "fields": [
                    "id: UUID PRIMARY KEY",
                    "business_id: UUID REFERENCES business_profile(id)",
                    "user_id: UUID REFERENCES users(id)",
                    "total: DECIMAL(10,2)",
                    "status: VARCHAR(50) DEFAULT 'pending'",
                    "created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                ]
            }
        elif vertical == "clinic":
            tables["appointments"] = {
                "fields": [
                    "id: UUID PRIMARY KEY",
                    "business_id: UUID REFERENCES business_profile(id)",
                    "user_id: UUID REFERENCES users(id)",
                    "appointment_time: TIMESTAMP NOT NULL",
                    "status: VARCHAR(50) DEFAULT 'scheduled'",
                    "notes: TEXT",
                ]
            }
        elif vertical in ["repair_service", "service"]:
            tables["service_requests"] = {
                "fields": [
                    "id: UUID PRIMARY KEY",
                    "business_id: UUID REFERENCES business_profile(id)",
                    "user_id: UUID REFERENCES users(id)",
                    "description: TEXT",
                    "status: VARCHAR(50) DEFAULT 'pending'",
                    "priority: VARCHAR(50) DEFAULT 'normal'",
                    "created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                ]
            }
        
        # Add feature-specific tables
        for feature in features:
            feature_label = feature.get("label", "").lower()
            if "booking" in feature_label or "appointment" in feature_label:
                if "appointments" not in tables:
                    tables["appointments"] = {
                        "fields": [
                            "id: UUID PRIMARY KEY",
                            "business_id: UUID REFERENCES business_profile(id)",
                            "user_id: UUID REFERENCES users(id)",
                            "appointment_time: TIMESTAMP NOT NULL",
                            "status: VARCHAR(50) DEFAULT 'scheduled'",
                        ]
                    }
            elif "order" in feature_label:
                if "orders" not in tables:
                    tables["orders"] = {
                        "fields": [
                            "id: UUID PRIMARY KEY",
                            "business_id: UUID REFERENCES business_profile(id)",
                            "user_id: UUID REFERENCES users(id)",
                            "total: DECIMAL(10,2)",
                            "status: VARCHAR(50) DEFAULT 'pending'",
                        ]
                    }
        
        relationships = [
            "users.id -> business_profile.user_id",
            "business_profile.id -> menu_items.business_id",
            "business_profile.id -> orders.business_id",
            "business_profile.id -> appointments.business_id",
            "business_profile.id -> service_requests.business_id",
        ]
        
        indexes = [
            "CREATE INDEX idx_users_email ON users(email)",
            "CREATE INDEX idx_business_profile_user_id ON business_profile(user_id)",
            "CREATE INDEX idx_orders_business_id ON orders(business_id)",
            "CREATE INDEX idx_appointments_business_id ON appointments(business_id)",
        ]
        
        migrations = [
            "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"",
        ]
        
        return DatabaseSchema(
            tables=tables,
            relationships=relationships,
            indexes=indexes,
            migrations=migrations
        )


class AuthSystemGenerator:
    """Generates authentication system configuration"""
    
    def generate_auth_config(self, build_spec: dict[str, Any]) -> AuthConfig:
        """Generate authentication configuration"""
        business = build_spec.get("business", {})
        
        return AuthConfig(
            provider="local",
            user_fields=[
                "email",
                "password",
                "name",
                "phone",
            ],
            session_config={
                "secret_key": "{{SECRET_KEY}}",
                "algorithm": "HS256",
                "access_token_expire_minutes": 30,
                "refresh_token_expire_days": 7,
            },
            middleware_config={
                "protected_routes": ["/dashboard", "/profile", "/admin"],
                "public_routes": ["/", "/login", "/register", "/api/auth"],
            }
        )


class PaymentSystemGenerator:
    """Generates payment integration configuration"""
    
    def generate_payment_config(self, build_spec: dict[str, Any]) -> Optional[PaymentConfig]:
        """Generate payment configuration if needed"""
        features = build_spec.get("includedFeatures", [])
        
        # Check if payment features are needed
        needs_payment = any(
            "order" in f.get("label", "").lower() or "payment" in f.get("label", "").lower()
            for f in features
        )
        
        if not needs_payment:
            return None
        
        return PaymentConfig(
            provider="stripe",
            api_config={
                "publishable_key": "{{STRIPE_PUBLISHABLE_KEY}}",
                "secret_key": "{{STRIPE_SECRET_KEY}}",
                "webhook_secret": "{{STRIPE_WEBHOOK_SECRET}}",
            },
            webhook_config={
                "endpoint": "/api/webhooks/stripe",
                "events": ["payment_intent.succeeded", "payment_intent.failed"],
            },
            payment_methods=["card", "us_bank_account"]
        )


class DeploymentScriptGenerator:
    """Generates deployment scripts and configuration"""
    
    def generate_deployment_config(self, build_spec: dict[str, Any]) -> DeploymentConfig:
        """Generate deployment configuration"""
        return DeploymentConfig(
            platform="vercel",
            environment_vars={
                "DATABASE_URL": "{{DATABASE_URL}}",
                "SECRET_KEY": "{{SECRET_KEY}}",
                "STRIPE_PUBLISHABLE_KEY": "{{STRIPE_PUBLISHABLE_KEY}}",
                "STRIPE_SECRET_KEY": "{{STRIPE_SECRET_KEY}}",
            },
            build_commands=[
                "npm install",
                "npm run build",
            ],
            deployment_scripts=[
                "vercel --prod",
            ]
        )
    
    def generate_docker_compose(self, build_spec: dict[str, Any]) -> str:
        """Generate docker-compose.yml"""
        return """version: '3.8'

services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/mydb
      - SECRET_KEY=your-secret-key
    depends_on:
      - db
  
  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=mydb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
"""
    
    def generate_env_file(self, build_spec: dict[str, Any]) -> str:
        """Generate .env file template"""
        return """# Database
DATABASE_URL=postgresql://user:password@localhost:5432/mydb

# Authentication
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Payment (Stripe)
STRIPE_PUBLISHABLE_KEY=pk_test_your_key
STRIPE_SECRET_KEY=sk_test_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Application
NODE_ENV=production
PORT=3000
"""
    
    def generate_readme(self, build_spec: dict[str, Any]) -> str:
        """Generate README.md for deployment"""
        business = build_spec.get("business", {})
        vertical = business.get("vertical", "unknown")
        
        return f"""# {business.get('name', 'Generated Website')}

Generated website for {business.get('name', 'business')} - {vertical}

## Setup

1. Install dependencies:
```bash
npm install
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your values
```

3. Run database migrations:
```bash
npm run db:migrate
```

4. Start the development server:
```bash
npm run dev
```

## Deployment

### Vercel
```bash
vercel
```

### Docker
```bash
docker-compose up
```

## Features

This website includes:
- {', '.join([f.get('label', '') for f in build_spec.get('includedFeatures', [])])}

## Support

For issues or questions, contact {business.get('contact_email', 'support@example.com')}
"""


class DeploymentOrchestrator:
    """Orchestrates the complete deployment package generation"""
    
    def __init__(self):
        self.db_generator = DatabaseSchemaGenerator()
        self.auth_generator = AuthSystemGenerator()
        self.payment_generator = PaymentSystemGenerator()
        self.deployment_generator = DeploymentScriptGenerator()
    
    def generate_deployment_package(
        self,
        build_spec: dict[str, Any],
        output_dir: Optional[Path] = None
    ) -> DeploymentPackage:
        """Generate complete deployment package"""
        logger.info("Generating deployment package")
        
        database_schema = self.db_generator.generate_schema(build_spec)
        auth_config = self.auth_generator.generate_auth_config(build_spec)
        payment_config = self.payment_generator.generate_payment_config(build_spec)
        deployment_config = self.deployment_generator.generate_deployment_config(build_spec)
        
        readme = self.deployment_generator.generate_readme(build_spec)
        docker_compose = self.deployment_generator.generate_docker_compose(build_spec)
        env_file = self.deployment_generator.generate_env_file(build_spec)
        
        package = DeploymentPackage(
            database_schema=database_schema,
            auth_config=auth_config,
            payment_config=payment_config,
            deployment_config=deployment_config,
            readme=readme,
            docker_compose=docker_compose,
            env_file=env_file
        )
        
        # Write to disk if output_dir provided
        if output_dir:
            self.write_deployment_package(package, output_dir)
        
        return package
    
    def write_deployment_package(self, package: DeploymentPackage, output_dir: Path) -> None:
        """Write deployment package to disk"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write README
        (output_dir / "README.md").write_text(package.readme)
        
        # Write docker-compose
        (output_dir / "docker-compose.yml").write_text(package.docker_compose)
        
        # Write .env template
        (output_dir / ".env.example").write_text(package.env_file)
        
        # Write database schema
        import json
        (output_dir / "database_schema.json").write_text(
            json.dumps(package.database_schema.model_dump(), indent=2)
        )
        
        # Write auth config
        (output_dir / "auth_config.json").write_text(
            json.dumps(package.auth_config.model_dump(), indent=2)
        )
        
        # Write payment config if exists
        if package.payment_config:
            (output_dir / "payment_config.json").write_text(
                json.dumps(package.payment_config.model_dump(), indent=2)
            )
        
        # Write deployment config
        (output_dir / "deployment_config.json").write_text(
            json.dumps(package.deployment_config.model_dump(), indent=2)
        )
        
        logger.info(f"Deployment package written to {output_dir}")


if __name__ == "__main__":
    # Test deployment system
    test_build_spec = {
        "business": {
            "name": "Bella Napoli",
            "location": "San Francisco",
            "vertical": "restaurant",
            "contact_email": "hello@bellanapoli.example",
        },
        "includedFeatures": [
            {"label": "Online ordering"},
            {"label": "Menu display"},
            {"label": "User accounts"},
        ],
    }
    
    orchestrator = DeploymentOrchestrator()
    package = orchestrator.generate_deployment_package(test_build_spec)
    
    print("Deployment Package Generated:")
    print(f"Database tables: {list(package.database_schema.tables.keys())}")
    print(f"Auth provider: {package.auth_config.provider}")
    print(f"Payment config: {'Included' if package.payment_config else 'Not needed'}")
    print(f"Deployment platform: {package.deployment_config.platform}")
