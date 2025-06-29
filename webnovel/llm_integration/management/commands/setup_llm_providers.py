from django.core.management.base import BaseCommand
from llm_integration.models import LLMProvider
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Set up default LLM provider configurations'

    def handle(self, *args, **options):
        self.stdout.write("Setting up LLM provider configurations...")
        
        # Default provider configurations with cost estimates (per 1K tokens)
        providers_config = {
            "openai": {
                "display_name": "OpenAI",
                "default_model": "gpt-3.5-turbo",
                "available_models": [
                    "gpt-4o",
                    "gpt-4o-mini", 
                    "gpt-4-turbo",
                    "gpt-3.5-turbo",
                    "gpt-4"
                ],
                "cost_per_1k_tokens": 0.002,  # Approximate cost for gpt-3.5-turbo
                "api_key_configured": bool(os.getenv("OPENAI_API_KEY"))
            },
            "anthropic": {
                "display_name": "Anthropic",
                "default_model": "claude-3-sonnet-20240229",
                "available_models": [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307"
                ],
                "cost_per_1k_tokens": 0.015,  # Approximate cost for claude-3-sonnet
                "api_key_configured": bool(os.getenv("ANTHROPIC_API_KEY"))
            },
            "google": {
                "display_name": "Google",
                "default_model": "gemini-pro",
                "available_models": [
                    "gemini-1.5-pro",
                    "gemini-1.5-flash",
                    "gemini-pro",
                    "gemini-pro-vision"
                ],
                "cost_per_1k_tokens": 0.001,  # Approximate cost for gemini-pro
                "api_key_configured": bool(os.getenv("GOOGLE_API_KEY"))
            },
            "cohere": {
                "display_name": "Cohere",
                "default_model": "command",
                "available_models": [
                    "command",
                    "command-light",
                    "command-nightly"
                ],
                "cost_per_1k_tokens": 0.005,  # Approximate cost for command
                "api_key_configured": bool(os.getenv("COHERE_API_KEY"))
            },
            "mistral": {
                "display_name": "Mistral AI",
                "default_model": "mistral-large-latest",
                "available_models": [
                    "mistral-large-latest",
                    "mistral-medium-latest",
                    "mistral-small-latest"
                ],
                "cost_per_1k_tokens": 0.014,  # Approximate cost for mistral-large
                "api_key_configured": bool(os.getenv("MISTRAL_API_KEY"))
            },
            "ollama": {
                "display_name": "Ollama (Local)",
                "default_model": "llama2",
                "available_models": [
                    "llama2",
                    "llama2:13b",
                    "llama2:70b",
                    "mistral",
                    "codellama",
                    "neural-chat"
                ],
                "cost_per_1k_tokens": 0.0,  # Free local models
                "api_key_configured": True  # No API key needed for local
            }
        }
        
        created_count = 0
        updated_count = 0
        
        for provider_name, config in providers_config.items():
            provider, created = LLMProvider.objects.get_or_create(
                name=provider_name,
                defaults={
                    'display_name': config['display_name'],
                    'default_model': config['default_model'],
                    'available_models': config['available_models'],
                    'cost_per_1k_tokens': config['cost_per_1k_tokens'],
                    'api_key_configured': config['api_key_configured'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created provider: {provider.display_name}")
                )
            else:
                # Update existing provider with new information
                provider.display_name = config['display_name']
                provider.default_model = config['default_model']
                provider.available_models = config['available_models']
                provider.cost_per_1k_tokens = config['cost_per_1k_tokens']
                provider.api_key_configured = config['api_key_configured']
                provider.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"↻ Updated provider: {provider.display_name}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSetup complete! Created {created_count} providers, updated {updated_count} providers."
            )
        )
        
        # Show current provider status
        self.stdout.write("\nCurrent provider status:")
        for provider in LLMProvider.objects.all():
            status = "✓" if provider.api_key_configured else "✗"
            self.stdout.write(f"  {status} {provider.display_name} ({provider.name})") 