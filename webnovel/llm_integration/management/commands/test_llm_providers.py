from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from llm_integration.services import LLMTranslationService
import json


class Command(BaseCommand):
    help = 'Test different LLM providers and switch between them using LangChain'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            help='LLM provider to test (openai, anthropic, google, cohere, ollama)',
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model to test',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for the provider',
        )
        parser.add_argument(
            '--list-providers',
            action='store_true',
            help='List all available providers and their models',
        )
        parser.add_argument(
            '--test-translation',
            action='store_true',
            help='Test translation functionality',
        )
        parser.add_argument(
            '--test-chain',
            action='store_true',
            help='Test LangChain chain functionality',
        )

    def handle(self, *args, **options):
        if options['list_providers']:
            self.list_providers()
            return

        provider = options['provider'] or settings.LLM_PROVIDER
        model = options['model']
        api_key = options['api_key']

        if not provider:
            raise CommandError('Please specify a provider or set LLM_PROVIDER in settings')

        self.stdout.write(f"Testing LLM provider: {provider}")
        
        # Initialize service with specified provider
        llm_service = LLMTranslationService(
            provider=provider,
            model=model,
            api_key=api_key
        )

        # Test basic functionality
        self.test_basic_functionality(llm_service)

        if options['test_translation']:
            self.test_translation(llm_service)

        if options['test_chain']:
            self.test_chain(llm_service)

    def list_providers(self):
        """List all available providers and their models"""
        self.stdout.write(self.style.SUCCESS('Available LLM Providers:'))
        
        llm_service = LLMTranslationService()
        providers = llm_service.get_available_providers()
        
        for provider in providers:
            self.stdout.write(f"\n{provider.upper()}:")
            models = llm_service.get_provider_models(provider)
            for model in models:
                self.stdout.write(f"  - {model}")
            
            # Check if API key is configured
            provider_config = getattr(settings, 'LLM_PROVIDERS', {}).get(provider, {})
            api_key = provider_config.get('api_key', '')
            if api_key:
                self.stdout.write(self.style.SUCCESS(f"  ✓ API key configured"))
            else:
                self.stdout.write(self.style.WARNING(f"  ✗ No API key configured"))

    def test_basic_functionality(self, llm_service):
        """Test basic LLM functionality"""
        self.stdout.write("Testing basic LLM functionality...")
        
        test_prompt = "Hello! Please respond with 'Hello from {provider}!'"
        
        try:
            from langchain_core.messages import HumanMessage
            
            messages = [HumanMessage(content=test_prompt)]
            
            response = llm_service._call_llm(messages, temperature=0.1, max_tokens=50)
            self.stdout.write(self.style.SUCCESS(f"✓ Success! Response: {response}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))

    def test_translation(self, llm_service):
        """Test translation functionality"""
        self.stdout.write("Testing translation functionality...")
        
        test_text = "Hello, how are you today?"
        target_language = "es"  # Spanish
        
        try:
            translated = llm_service.translate_text(test_text, target_language)
            self.stdout.write(self.style.SUCCESS(f"✓ Translation successful!"))
            self.stdout.write(f"Original: {test_text}")
            self.stdout.write(f"Translated: {translated}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Translation error: {str(e)}"))

    def test_chain(self, llm_service):
        """Test LangChain chain functionality"""
        self.stdout.write("Testing LangChain chain functionality...")
        
        try:
            # Test basic chain
            chain = llm_service.get_chain()
            response = chain.invoke({"input": "What is 2+2?"})
            self.stdout.write(self.style.SUCCESS(f"✓ Chain test successful!"))
            self.stdout.write(f"Response: {response}")
            
            # Test memory chain
            memory_chain, memory = llm_service.get_memory_chain()
            self.stdout.write(self.style.SUCCESS(f"✓ Memory chain created successfully!"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Chain test error: {str(e)}"))

    def switch_provider(self, llm_service, new_provider, new_api_key=None, new_model=None):
        """Switch to a different provider"""
        self.stdout.write(f"Switching from {llm_service.provider} to {new_provider}...")
        
        try:
            llm_service.switch_provider(new_provider, new_api_key, new_model)
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully switched to {new_provider}"))
            self.stdout.write(f"Current model: {llm_service.model}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error switching provider: {str(e)}")) 