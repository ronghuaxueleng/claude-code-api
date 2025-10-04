"""Model provider configuration and registry."""

from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class ProviderType(str, Enum):
    """Supported model provider types."""
    ANTHROPIC = "anthropic"
    MOONSHOT = "moonshot"
    OPENAI = "openai"
    CUSTOM = "custom"


class ModelProvider(BaseModel):
    """Model provider configuration."""
    name: str = Field(..., description="Provider name")
    type: ProviderType = Field(..., description="Provider type")
    base_url: str = Field(..., description="Base URL for the provider")
    api_key_env: str = Field(..., description="Environment variable name for API key")
    model_prefix: Optional[str] = Field(None, description="Model name prefix")
    supported_models: List[str] = Field(default_factory=list, description="List of supported models")
    description: Optional[str] = Field(None, description="Provider description")


class ProviderRegistry:
    """Registry for model providers."""
    
    def __init__(self):
        self.providers: Dict[str, ModelProvider] = {}
        self._initialize_default_providers()
    
    def _initialize_default_providers(self):
        """Initialize default model providers."""
        # Anthropic (official)
        self.register_provider(ModelProvider(
            name="anthropic",
            type=ProviderType.ANTHROPIC,
            base_url="https://api.anthropic.com",
            api_key_env="ANTHROPIC_API_KEY",
            supported_models=[
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ],
            description="Official Anthropic Claude API"
        ))
        
        # Moonshot (Chinese provider)
        self.register_provider(ModelProvider(
            name="moonshot",
            type=ProviderType.MOONSHOT,
            base_url="https://api.moonshot.cn/anthropic/",
            api_key_env="ANTHROPIC_API_KEY",
            supported_models=[
                "kimi-k2-turbo-preview",
                "kimi-k2-0905-preview",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022"
            ],
            description="Moonshot AI Claude API (Chinese provider)"
        ))
        
        # OpenAI (if they support Claude-compatible API)
        self.register_provider(ModelProvider(
            name="openai",
            type=ProviderType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            supported_models=[
                "gpt-4",
                "gpt-3.5-turbo"
            ],
            description="OpenAI API (for GPT models)"
        ))
        
        # BigModel (Chinese provider)
        self.register_provider(ModelProvider(
            name="bigmodel",
            type=ProviderType.ANTHROPIC,
            base_url="https://open.bigmodel.cn/api/anthropic",
            api_key_env="ANTHROPIC_API_KEY",
            supported_models=[
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ],
            description="BigModel Claude API (Chinese provider)"
        ))
        
        # DeepSeek (Chinese provider)
        self.register_provider(ModelProvider(
            name="deepseek",
            type=ProviderType.ANTHROPIC,
            base_url="https://api.deepseek.com/anthropic",
            api_key_env="ANTHROPIC_API_KEY",
            supported_models=[
                "deepseek-chat",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022"
            ],
            description="DeepSeek Claude API (Chinese provider)"
        ))
        
        # Siliconflow (Chinese provider)
        self.register_provider(ModelProvider(
            name="siliconflow",
            type=ProviderType.ANTHROPIC,
            base_url="https://api.siliconflow.cn/",
            api_key_env="ANTHROPIC_API_KEY",
            supported_models=[
                "zai-org/GLM-4.5",
                "zai-org/GLM-4.5-Air",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022"
            ],
            description="Siliconflow Claude API (Chinese provider)"
        ))
    
    def register_provider(self, provider: ModelProvider):
        """Register a new model provider."""
        self.providers[provider.name] = provider
    
    def get_provider(self, name: str) -> Optional[ModelProvider]:
        """Get provider by name."""
        return self.providers.get(name)
    
    def get_provider_by_model(self, model: str) -> Optional[ModelProvider]:
        """Get provider that supports the given model."""
        for provider in self.providers.values():
            if model in provider.supported_models:
                return provider
        return None
    
    def get_all_providers(self) -> List[ModelProvider]:
        """Get all registered providers."""
        return list(self.providers.values())
    
    def get_provider_config(self, model: str, custom_base_url: Optional[str] = None, 
                          custom_api_key: Optional[str] = None) -> Dict[str, str]:
        """Get provider configuration for a model."""
        provider = self.get_provider_by_model(model)
        
        if not provider:
            # Fallback to default configuration
            return {
                "ANTHROPIC_BASE_URL": custom_base_url or "https://api.anthropic.com",
                "ANTHROPIC_API_KEY": custom_api_key or "",
                "ANTHROPIC_MODEL": model
            }
        
        # Use custom values if provided, otherwise use provider defaults
        base_url = custom_base_url or provider.base_url
        api_key = custom_api_key or ""
        
        return {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_API_KEY": api_key,
            "ANTHROPIC_MODEL": model
        }


# Global provider registry instance
provider_registry = ProviderRegistry()


def get_provider_config_for_model(
    model: str, 
    custom_base_url: Optional[str] = None,
    custom_api_key: Optional[str] = None
) -> Dict[str, str]:
    """Get provider configuration for a specific model."""
    return provider_registry.get_provider_config(model, custom_base_url, custom_api_key)


def get_supported_models() -> List[str]:
    """Get all supported models across all providers."""
    models = set()
    for provider in provider_registry.get_all_providers():
        models.update(provider.supported_models)
    return sorted(list(models))


def get_provider_info() -> Dict[str, Dict[str, any]]:
    """Get information about all providers."""
    return {
        provider.name: {
            "type": provider.type,
            "base_url": provider.base_url,
            "api_key_env": provider.api_key_env,
            "supported_models": provider.supported_models,
            "description": provider.description
        }
        for provider in provider_registry.get_all_providers()
    }
