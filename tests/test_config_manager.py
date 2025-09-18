"""
Unit tests for configuration management system.
"""

import pytest
import os
import tempfile
import yaml
import json
from unittest.mock import patch, mock_open

from ozb_deal_filter.services.config_manager import ConfigurationManager
from ozb_deal_filter.models.config import Configuration


class TestConfigurationManager:
    """Test ConfigurationManager functionality."""
    
    def create_temp_config(self, config_data: dict, file_format: str = "yaml") -> str:
        """Create a temporary configuration file."""
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=f'.{file_format}', 
            delete=False,
            encoding='utf-8'
        ) as f:
            if file_format == "json":
                json.dump(config_data, f, indent=2)
            else:
                yaml.dump(config_data, f, default_flow_style=False)
            return f.name
    
    def get_valid_config_data(self) -> dict:
        """Get valid configuration data for testing."""
        return {
            "rss_feeds": [
                "https://www.ozbargain.com.au/deals/feed"
            ],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.txt",
                "max_price": 500.0,
                "min_discount_percentage": 20.0,
                "categories": ["Electronics"],
                "keywords": ["laptop"],
                "min_authenticity_score": 0.6
            },
            "llm_provider": {
                "type": "local",
                "local": {
                    "model": "llama2",
                    "docker_image": "ollama/ollama"
                }
            },
            "messaging_platform": {
                "type": "telegram",
                "telegram": {
                    "bot_token": "test-token",
                    "chat_id": "test-chat"
                }
            },
            "system": {
                "polling_interval": 120,
                "max_concurrent_feeds": 5
            }
        }
    
    def test_load_valid_yaml_config(self):
        """Test loading valid YAML configuration."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            config = manager.load_config()
            
            assert isinstance(config, Configuration)
            assert config.rss_feeds == ["https://www.ozbargain.com.au/deals/feed"]
            assert config.user_criteria.max_price == 500.0
            assert config.llm_provider.type == "local"
            assert config.messaging_platform.type == "telegram"
            assert config.polling_interval == 120
        finally:
            os.unlink(config_file)
    
    def test_load_valid_json_config(self):
        """Test loading valid JSON configuration."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "json")
        
        try:
            manager = ConfigurationManager(config_file)
            config = manager.load_config()
            
            assert isinstance(config, Configuration)
            assert config.rss_feeds == ["https://www.ozbargain.com.au/deals/feed"]
            assert config.user_criteria.max_price == 500.0
        finally:
            os.unlink(config_file)
    
    def test_environment_variable_expansion(self):
        """Test environment variable expansion in configuration."""
        config_data = self.get_valid_config_data()
        config_data["messaging_platform"]["telegram"]["bot_token"] = "${TEST_BOT_TOKEN}"
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            with patch.dict(os.environ, {"TEST_BOT_TOKEN": "expanded-token"}):
                manager = ConfigurationManager(config_file)
                config = manager.load_config()
                
                assert config.messaging_platform.telegram["bot_token"] == "expanded-token"
        finally:
            os.unlink(config_file)
    
    def test_missing_environment_variable_raises_error(self):
        """Test that missing environment variable raises error."""
        config_data = self.get_valid_config_data()
        config_data["messaging_platform"]["telegram"]["bot_token"] = "${MISSING_VAR}"
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            with pytest.raises(ValueError, match="Environment variable 'MISSING_VAR' not found"):
                manager.load_config()
        finally:
            os.unlink(config_file)
    
    def test_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_file = f.name
        
        try:
            manager = ConfigurationManager(config_file)
            with pytest.raises(ValueError, match="Invalid YAML"):
                manager.load_config()
        finally:
            os.unlink(config_file)
    
    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json content}')
            config_file = f.name
        
        try:
            manager = ConfigurationManager(config_file)
            with pytest.raises(ValueError, match="Invalid JSON"):
                manager.load_config()
        finally:
            os.unlink(config_file)
    
    def test_missing_config_file_raises_error(self):
        """Test that missing configuration file raises error."""
        manager = ConfigurationManager("nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            manager.load_config()
    
    def test_invalid_config_data_raises_error(self):
        """Test that invalid configuration data raises error."""
        config_data = {
            "rss_feeds": [],  # Empty feeds list - invalid
            "user_criteria": {
                "prompt_template": "",  # Empty template - invalid
                "min_authenticity_score": 2.0  # Invalid score > 1
            }
        }
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            with pytest.raises(ValueError):
                manager.load_config()
        finally:
            os.unlink(config_file)
    
    def test_get_config_loads_if_not_cached(self):
        """Test that get_config loads configuration if not cached."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            # First call should load
            config1 = manager.get_config()
            # Second call should return cached
            config2 = manager.get_config()
            
            assert config1 is config2  # Same object reference
        finally:
            os.unlink(config_file)
    
    def test_reload_if_changed_detects_modification(self):
        """Test that reload_if_changed detects file modifications."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            manager.load_config()
            
            # Modify the file
            import time
            time.sleep(0.1)  # Ensure different timestamp
            config_data["system"]["polling_interval"] = 180
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)
            
            # Should detect change and reload
            reloaded = manager.reload_if_changed()
            assert reloaded is True
            
            config = manager.get_config()
            assert config.polling_interval == 180
        finally:
            os.unlink(config_file)
    
    def test_reload_if_changed_no_change(self):
        """Test that reload_if_changed returns False when no change."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            manager.load_config()
            
            # No modification
            reloaded = manager.reload_if_changed()
            assert reloaded is False
        finally:
            os.unlink(config_file)
    
    def test_validate_config_file_valid(self):
        """Test validation of valid configuration file."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)  # Provide explicit path
            result = manager.validate_config_file(config_file)
            assert result is True
        finally:
            os.unlink(config_file)
    
    def test_validate_config_file_invalid(self):
        """Test validation of invalid configuration file."""
        config_data = {"rss_feeds": []}  # Invalid - empty feeds
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)  # Provide explicit path
            with pytest.raises(ValueError, match="Configuration validation failed"):
                manager.validate_config_file(config_file)
        finally:
            os.unlink(config_file)
    
    def test_validate_nonexistent_file_raises_error(self):
        """Test validation of nonexistent file raises error."""
        # Create a dummy config file for the manager
        config_data = self.get_valid_config_data()
        dummy_config = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(dummy_config)
            with pytest.raises(ValueError, match="Configuration file not found"):
                manager.validate_config_file("nonexistent.yaml")
        finally:
            os.unlink(dummy_config)
    
    def test_get_config_template(self):
        """Test getting configuration template."""
        # Create a dummy config file for the manager
        config_data = self.get_valid_config_data()
        dummy_config = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(dummy_config)
            template = manager.get_config_template()
            
            assert isinstance(template, dict)
            assert "rss_feeds" in template
            assert "user_criteria" in template
            assert "llm_provider" in template
            assert "messaging_platform" in template
            assert "system" in template
            
            # Verify template structure
            assert isinstance(template["rss_feeds"], list)
            assert len(template["rss_feeds"]) > 0
            assert isinstance(template["user_criteria"], dict)
            assert "prompt_template" in template["user_criteria"]
        finally:
            os.unlink(dummy_config)
    
    @patch('ozb_deal_filter.services.config_manager.os.path.exists')
    def test_find_config_file_finds_first_existing(self, mock_exists):
        """Test that _find_config_file finds first existing file."""
        # Mock that config/config.yaml exists
        mock_exists.side_effect = lambda path: path == "config/config.yaml"
        
        manager = ConfigurationManager()
        assert manager.config_path == "config/config.yaml"
    
    @patch('ozb_deal_filter.services.config_manager.os.path.exists')
    def test_find_config_file_suggests_example(self, mock_exists):
        """Test that _find_config_file suggests using example file."""
        # Mock that only example file exists
        mock_exists.side_effect = lambda path: path == "config/config.example.yaml"
        
        with pytest.raises(ValueError, match="copy 'config/config.example.yaml'"):
            ConfigurationManager()
    
    @patch('ozb_deal_filter.services.config_manager.os.path.exists')
    def test_find_config_file_no_files_found(self, mock_exists):
        """Test that _find_config_file raises error when no files found."""
        mock_exists.return_value = False
        
        with pytest.raises(ValueError, match="No configuration file found"):
            ConfigurationManager()
    
    def test_reload_if_changed_handles_invalid_config(self):
        """Test that reload_if_changed handles invalid config gracefully."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            original_config = manager.load_config()
            
            # Corrupt the file
            import time
            time.sleep(0.1)
            with open(config_file, 'w') as f:
                f.write("invalid: yaml: [")
            
            # Should not reload due to error, should keep original config
            reloaded = manager.reload_if_changed()
            assert reloaded is False
            
            current_config = manager.get_config()
            assert current_config is original_config
        finally:
            os.unlink(config_file)
    
    def test_load_configuration_protocol_method(self):
        """Test the protocol interface load_configuration method."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        dummy_config = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(dummy_config)
            config = manager.load_configuration(config_file)
            
            assert isinstance(config, Configuration)
            assert config.rss_feeds == ["https://www.ozbargain.com.au/deals/feed"]
            assert manager.config_path == config_file
        finally:
            os.unlink(config_file)
            os.unlink(dummy_config)
    
    def test_validate_configuration_protocol_method(self):
        """Test the protocol interface validate_configuration method."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            config = manager.load_config()
            
            # Should validate successfully
            result = manager.validate_configuration(config)
            assert result is True
        finally:
            os.unlink(config_file)
    
    def test_reload_configuration_protocol_method(self):
        """Test the protocol interface reload_configuration method."""
        config_data = self.get_valid_config_data()
        config_file = self.create_temp_config(config_data, "yaml")
        
        try:
            manager = ConfigurationManager(config_file)
            manager.load_config()
            
            # Modify the file
            import time
            time.sleep(0.1)
            config_data["system"]["polling_interval"] = 240
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)
            
            # Use protocol method to reload
            manager.reload_configuration()
            
            config = manager.get_config()
            assert config.polling_interval == 240
        finally:
            os.unlink(config_file)