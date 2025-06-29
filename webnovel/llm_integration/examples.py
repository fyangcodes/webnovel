"""
Example usage of LLM provider switching functionality with LangChain

This script demonstrates how to:
1. Initialize the LLM service with different providers using LangChain
2. Switch between providers dynamically
3. Use LangChain chains and memory
4. Test different models from the same provider
5. Handle provider-specific configurations
"""

from llm_integration.services import LLMTranslationService
import os


def example_basic_usage():
    """Basic usage examples with LangChain"""
    print("=== Basic LLM Provider Usage Examples (LangChain) ===\n")
    
    # Example 1: Initialize with OpenAI
    print("1. Initializing with OpenAI...")
    openai_service = LLMTranslationService(
        provider="openai",
        model="gpt-3.5-turbo",
        api_key="your-openai-api-key"
    )
    print(f"   Provider: {openai_service.provider}")
    print(f"   Model: {openai_service.model}")
    print(f"   LLM Type: {type(openai_service.llm).__name__}\n")
    
    # Example 2: Initialize with Anthropic
    print("2. Initializing with Anthropic...")
    anthropic_service = LLMTranslationService(
        provider="anthropic",
        model="claude-3-sonnet-20240229",
        api_key="your-anthropic-api-key"
    )
    print(f"   Provider: {anthropic_service.provider}")
    print(f"   Model: {anthropic_service.model}")
    print(f"   LLM Type: {type(anthropic_service.llm).__name__}\n")
    
    # Example 3: Switch provider dynamically
    print("3. Switching provider dynamically...")
    service = LLMTranslationService(provider="openai")
    print(f"   Initial provider: {service.provider}")
    
    service.switch_provider("anthropic", api_key="your-anthropic-api-key")
    print(f"   Switched to: {service.provider}")
    print(f"   Current model: {service.model}\n")


def example_langchain_chains():
    """Demonstrate LangChain chains and advanced features"""
    print("=== LangChain Chains and Advanced Features ===\n")
    
    service = LLMTranslationService(provider="openai", api_key="your-openai-api-key")
    
    # Example 1: Basic chain
    print("1. Basic LangChain chain:")
    chain = service.get_chain()
    response = chain.invoke({"input": "Explain quantum computing in simple terms"})
    print(f"   Response: {response[:100]}...\n")
    
    # Example 2: Custom prompt template
    print("2. Custom prompt template:")
    from langchain_core.prompts import ChatPromptTemplate
    
    custom_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful coding assistant. Always provide code examples."),
        ("user", "Explain {topic} with a code example")
    ])
    
    custom_chain = service.get_chain(custom_prompt)
    response = custom_chain.invoke({"topic": "Python decorators"})
    print(f"   Response: {response[:150]}...\n")
    
    # Example 3: Memory chain
    print("3. Memory chain with conversation history:")
    memory_chain, memory = service.get_memory_chain()
    
    # First message
    response1 = memory_chain.invoke({"input": "My name is Alice"})
    print(f"   Response 1: {response1}")
    
    # Second message (should remember the name)
    response2 = memory_chain.invoke({"input": "What's my name?"})
    print(f"   Response 2: {response2}\n")


def example_translation_comparison():
    """Compare translation quality across different providers"""
    print("=== Translation Quality Comparison ===\n")
    
    test_text = "The quick brown fox jumps over the lazy dog."
    target_language = "es"  # Spanish
    
    providers_to_test = [
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-3-sonnet-20240229"),
        ("google", "gemini-pro"),
    ]
    
    for provider, model in providers_to_test:
        print(f"Testing {provider.upper()} with {model}...")
        try:
            service = LLMTranslationService(
                provider=provider,
                model=model,
                api_key=f"your-{provider}-api-key"
            )
            
            translated = service.translate_text(test_text, target_language)
            print(f"   Original: {test_text}")
            print(f"   Translated: {translated}")
            print()
            
        except Exception as e:
            print(f"   Error: {str(e)}\n")


def example_provider_management():
    """Show provider management features"""
    print("=== Provider Management Features ===\n")
    
    service = LLMTranslationService()
    
    # List available providers
    print("Available providers:")
    providers = service.get_available_providers()
    for provider in providers:
        print(f"  - {provider}")
    print()
    
    # List models for specific providers
    for provider in ["openai", "anthropic", "ollama"]:
        print(f"{provider.upper()} models:")
        models = service.get_provider_models(provider)
        for model in models:
            print(f"  - {model}")
        print()


def example_advanced_workflows():
    """Show advanced LangChain workflows"""
    print("=== Advanced LangChain Workflows ===\n")
    
    service = LLMTranslationService(provider="openai", api_key="your-openai-api-key")
    
    # Example 1: Structured output with Pydantic
    print("1. Structured output with Pydantic:")
    try:
        from langchain_core.pydantic_v1 import BaseModel, Field
        from langchain_core.output_parsers import PydanticOutputParser
        
        class TranslationAnalysis(BaseModel):
            original_text: str = Field(description="The original text")
            translated_text: str = Field(description="The translated text")
            confidence_score: float = Field(description="Confidence score 0-1")
            key_terms: list = Field(description="Key terms found in the text")
        
        parser = PydanticOutputParser(pydantic_object=TranslationAnalysis)
        
        prompt = f"""
        Analyze and translate the following text to Spanish:
        "Hello world, this is a test message."
        
        {parser.get_format_instructions()}
        """
        
        response = service.llm.invoke(prompt)
        print(f"   Structured response: {response.content[:200]}...\n")
        
    except Exception as e:
        print(f"   Error: {str(e)}\n")
    
    # Example 2: Tool usage
    print("2. Tool usage example:")
    try:
        from langchain_core.tools import tool
        
        @tool
        def get_weather(location: str) -> str:
            """Get the weather for a location"""
            return f"Weather in {location}: Sunny, 25°C"
        
        # This would be used with an agent in a real scenario
        print("   Tool defined: get_weather")
        print("   (In a real scenario, this would be used with LangChain agents)\n")
        
    except Exception as e:
        print(f"   Error: {str(e)}\n")


def example_error_handling():
    """Show error handling and fallback strategies"""
    print("=== Error Handling and Fallbacks ===\n")
    
    # Example with invalid API key
    print("1. Testing with invalid API key...")
    try:
        service = LLMTranslationService(
            provider="openai",
            api_key="invalid-key"
        )
        result = service.translate_text("Hello", "es")
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error caught: {str(e)}")
    print()
    
    # Example with fallback provider
    print("2. Testing fallback strategy...")
    providers = ["openai", "anthropic", "google"]
    
    for provider in providers:
        try:
            service = LLMTranslationService(
                provider=provider,
                api_key=f"your-{provider}-api-key"
            )
            result = service.translate_text("Hello", "es")
            print(f"   Success with {provider}: {result}")
            break  # Use first successful provider
        except Exception as e:
            print(f"   Failed with {provider}: {str(e)}")
            continue
    print()


def example_environment_configuration():
    """Show how to configure providers via environment variables"""
    print("=== Environment Configuration ===\n")
    
    # Example environment variables
    env_vars = {
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "your-openai-key",
        "ANTHROPIC_API_KEY": "your-anthropic-key",
        "GOOGLE_API_KEY": "your-google-key",
        "LLM_MODEL_NAME": "gpt-4o",
    }
    
    print("Environment variables to set:")
    for key, value in env_vars.items():
        print(f"  {key}={value}")
    print()
    
    print("Usage in code:")
    print("  # Will use environment variables automatically")
    print("  service = LLMTranslationService()")
    print("  print(f'Provider: {service.provider}')")
    print("  print(f'Model: {service.model}')")
    print("  print(f'LLM Type: {type(service.llm).__name__}')")


def example_ollama_local():
    """Show how to use Ollama for local models"""
    print("=== Ollama Local Models ===\n")
    
    try:
        service = LLMTranslationService(
            provider="ollama",
            model="llama2"
        )
        
        print("Using Ollama with local Llama2 model:")
        response = service.translate_text("Hello world", "es")
        print(f"   Translated: {response}")
        
        # Test chain with Ollama
        chain = service.get_chain()
        response = chain.invoke({"input": "What is machine learning?"})
        print(f"   Chain response: {response[:100]}...")
        
    except Exception as e:
        print(f"   Error: {str(e)}")
        print("   Note: Make sure Ollama is installed and running locally")
    print()


if __name__ == "__main__":
    print("LLM Provider Switching Examples with LangChain\n")
    print("=" * 60)
    
    example_basic_usage()
    example_langchain_chains()
    example_provider_management()
    example_advanced_workflows()
    example_error_handling()
    example_environment_configuration()
    example_ollama_local()
    
    print("\n" + "=" * 60)
    print("Note: Replace 'your-*-api-key' with actual API keys to test")
    print("For production use, set API keys via environment variables")
    print("LangChain provides additional features like:")
    print("- Agents and tools")
    print("- Vector stores and embeddings")
    print("- Document loaders and processors")
    print("- Advanced prompt engineering") 