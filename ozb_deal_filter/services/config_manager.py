"""
Configuration management system for the OzBargain Deal Filter.
"""

import os
import yaml
import json
from typing import Dict, Any, Optional
from pathlib import Path

from ..models.config import Configuration, UserCriteria, LLMProviderConfig, MessagingPlatformConfig


class ConfigurationManager:
    """Manages loading, validation, and reloading of system configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default paths.
        """
        self.config_path = config_path or self._find_config_file()
        self._config: Optional[Configuration] = None
        self._last_modified: Optional[float] = None
    
    def _find_config_file(self) -> str:
        """Find the configuration file in standard locations."""
        possible_paths = [
            "config/config.yaml",
            "config/config.yml", 
            "config/config.json",
            "config.yaml",
            "config.yml",
            "config.json"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If no config file found, use the example as template
        if os.path.exists("config/config.example.yaml"):
            raise ValueError(
                "No configuration file found. Please copy 'config/config.example.yaml' "
                "to 'config/config.yaml' and customize it for your needs."
            )
        
        raise ValueError(
            "No configuration file found. Please create a configuration file "
            "at one of these locations: " + ", ".join(possible_paths)
        )
    
    def load_config(self) -> Configuration:
        """
        Load configuration from file.
        
        Returns:
            Configuration object with validated settings.
            
        Raises:
            ValueError: If configuration is invalid or file cannot be read.
            FileNotFoundError: If configuration file doesn't exist.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.endswith('.json'):
                    raw_config = json.load(f)
                else:
                    raw_config = yaml.safe_load(f)
            
            # Expand environment variables
            raw_config = self._expand_env_vars(raw_config)
            
            # Convert to Configuration object
            config = self._parse_config(raw_config)
            
            # Validate configuration
            config.validate()
            
            # Update cache
            self._config = config
            self._last_modified = os.path.getmtime(self.config_path)
            
            return config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")
    
    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(obj, dict):
            return {key: self._expand_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Expand ${VAR_NAME} patterns
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ValueError(f"Environment variable '{var_name}' not found")
                return env_value
            return obj
        else:
            return obj
    
    def _parse_config(self, raw_config: Dict[str, Any]) -> Configuration:
        """Parse raw configuration dictionary into Configuration object."""
        try:
            # Parse user criteria
            user_criteria_data = raw_config.get("user_criteria", {})
            user_criteria = UserCriteria(
                prompt_template_path=user_criteria_data.get("prompt_template", ""),
                max_price=user_criteria_data.get("max_price"),
                min_discount_percentage=user_criteria_data.get("min_discount_percentage"),
                categories=user_criteria_data.get("categories", []),
                keywords=user_criteria_data.get("keywords", []),
                min_authenticity_score=user_criteria_data.get("min_authenticity_score", 0.5)
            )
            
            # Parse LLM provider config
            llm_data = raw_config.get("llm_provider", {})
            llm_provider = LLMProviderConfig(
                type=llm_data.get("type", ""),
                local=llm_data.get("local"),
                api=llm_data.get("api")
            )
            
            # Parse messaging platform config
            messaging_data = raw_config.get("messaging_platform", {})
            messaging_platform = MessagingPlatformConfig(
                type=messaging_data.get("type", ""),
                telegram=messaging_data.get("telegram"),
                whatsapp=messaging_data.get("whatsapp"),
                discord=messaging_data.get("discord"),
                slack=messaging_data.get("slack")
            )
            
            # Parse system settings
            system_data = raw_config.get("system", {})
            
            return Configuration(
                rss_feeds=raw_config.get("rss_feeds", []),
                user_criteria=user_criteria,
                llm_provider=llm_provider,
                messaging_platform=messaging_platform,
                polling_interval=system_data.get("polling_interval", 120),
                max_concurrent_feeds=system_data.get("max_concurrent_feeds", 10)
            )
            
        except KeyError as e:
            raise ValueError(f"Missing required configuration key: {e}")
        except Exception as e:
            raise ValueError(f"Error parsing configuration: {e}")
    
    def get_config(self) -> Configuration:
        """
        Get current configuration, loading if necessary.
        
        Returns:
            Current configuration object.
        """
        if self._config is None:
            return self.load_config()
        return self._config
    
    def reload_if_changed(self) -> bool:
        """
        Reload configuration if file has been modified.
        
        Returns:
            True if configuration was reloaded, False otherwise.
        """
        if not os.path.exists(self.config_path):
            return False
        
        current_modified = os.path.getmtime(self.config_path)
        
        if (self._last_modified is None or 
            current_modified > self._last_modified):
            try:
                self.load_config()
                return True
            except Exception:
                # If reload fails, keep current config
                return False
        
        return False
    
    def validate_config_file(self, config_path: str) -> bool:
        """
        Validate a configuration file without loading it.
        
        Args:
            config_path: Path to configuration file to validate.
            
        Returns:
            True if configuration is valid.
            
        Raises:
            ValueError: If configuration is invalid with detailed error message.
        """
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.json'):
                    raw_config = json.load(f)
                else:
                    raw_config = yaml.safe_load(f)
            
            # Expand environment variables (but don't fail on missing ones for validation)
            try:
                raw_config = self._expand_env_vars(raw_config)
            except ValueError:
                # For validation, we'll skip env var expansion if vars are missing
                pass
            
            # Parse and validate
            config = self._parse_config(raw_config)
            config.validate()
            
            return True
            
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")
    
    def get_config_template(self) -> Dict[str, Any]:
        """
        Get a template configuration dictionary.
        
        Returns:
            Dictionary with example configuration structure.
        """
        return {
            "rss_feeds": [
                "https://www.ozbargain.com.au/deals/feed",
                "https://www.ozbargain.com.au/cat/computing/feed"
            ],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.txt",
                "max_price": 500.0,
                "min_discount_percentage": 20.0,
                "categories": ["Electronics", "Computing"],
                "keywords": ["laptop", "phone", "tablet"],
                "min_authenticity_score": 0.6
            },
            "llm_provider": {
                "type": "local",
                "local": {
                    "model": "llama2",
                    "docker_image": "ollama/ollama"
                },
                "api": {
                    "provider": "openai",
                    "api_key": "${OPENAI_API_KEY}",
                    "model": "gpt-3.5-turbo"
                }
            },
            "messaging_platform": {
                "type": "telegram",
                "telegram": {
                    "bot_token": "${TELEGRAM_BOT_TOKEN}",
                    "chat_id": "${TELEGRAM_CHAT_ID}"
                },
                "discord": {
                    "webhook_url": "${DISCORD_WEBHOOK_URL}"
                }
            },
            "system": {
                "polling_interval": 120,
                "max_concurrent_feeds": 10
            }
        }