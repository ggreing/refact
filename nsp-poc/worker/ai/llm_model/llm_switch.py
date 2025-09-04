# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

logger = logging.getLogger(__name__)


class LLMModelSwitch:
    """LLM model dynamic switch class"""
    
    def __init__(self):
        self.model_mapping = {
            # OpenAI Models
            "gpt-4": OpenAIModel,
            "gpt-4-turbo": OpenAIModel,
            "gpt-3.5-turbo": OpenAIModel,
            "gpt-4o": OpenAIModel,
            "gpt-4o-mini": OpenAIModel,
            "gpt-5": OpenAIModel,
            "gpt-4.1-nano": OpenAIModel,
            
            
            # Anthropic Models
            "claude-3-opus": AnthropicModel,
            "claude-3-sonnet": AnthropicModel,
            "claude-3-haiku": AnthropicModel,
            "claude-3-5-sonnet": AnthropicModel,
            
            # Google Models
            "gemini-pro": GoogleModel,
            "gemini-1.5-pro": GoogleModel,
            "gemini-1.5-flash": GoogleModel,
        }
    
    def get_model(self, model_name: str, **kwargs) -> Any:
        """
        Get LLM model instance by model name
        
        Args:
            model_name: Model name to use
            **kwargs: Additional parameters for model initialization
            
        Returns:
            Initialized LLM model instance
            
        Raises:
            ValueError: If model name is not supported
        """
        if model_name not in self.model_mapping:
            available_models = list(self.model_mapping.keys())
            raise ValueError(
                f"Unsupported model: {model_name}\n"
                f"Available models: {available_models}"
            )
        
        model_class = self.model_mapping[model_name]
        
        # Special handling for Google models
        if model_class == GoogleModel:
            google_provider = GoogleProvider(**kwargs)
            return GoogleModel(model_name, provider=google_provider)
        
        return model_class(model_name, **kwargs)
    
    def list_available_models(self) -> Dict[str, list]:
        """List available models grouped by provider"""
        openai_models = [name for name, cls in self.model_mapping.items() if cls == OpenAIModel]
        anthropic_models = [name for name, cls in self.model_mapping.items() if cls == AnthropicModel]
        google_models = [name for name, cls in self.model_mapping.items() if cls == GoogleModel]
        
        return {
            "openai": openai_models,
            "anthropic": anthropic_models,
            "google": google_models
        }


# Global instance
llm_switch = LLMModelSwitch()


def csms_ai_model(model_name: str, **kwargs) -> Any:
    """
    Simple model switch function
    
    Usage:
        model = csms_ai_model("gpt-4", api_key="your_key")
        model = csms_ai_model("claude-3-sonnet", api_key="your_key")
        model = csms_ai_model("gemini-pro", api_key="your_google_api_key")
        model = csms_ai_model("gemini-1.5-flash", vertexai=True)
    """
    return llm_switch.get_model(model_name, **kwargs)


def get_available_models() -> Dict[str, list]:
    """Get available model list"""
    return llm_switch.list_available_models()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    # Usage example
    logger.info("Available models:")
    models = get_available_models()
    for provider, model_list in models.items():
        logger.info(f"\n{provider.upper()}:")
        for model in model_list:
            logger.info(f"  - {model}")
    
    # Model switch example
    try:
        model = csms_ai_model("gpt-4")
        logger.info(f"\nSuccessfully loaded model: {model}")
    except Exception as e:
        logger.error(f"\nModel loading failed: {e}", exc_info=True)