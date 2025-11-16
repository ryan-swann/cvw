#!/usr/bin/env python3
"""
Wally Synthesis Configuration Manager
====================================

Handles loading and management of machine-specific configurations for
the Wally synthesis engine.
"""

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class MachineConfig:
    """Loaded machine configuration"""
    raw_config: dict[str, Any]
    name: str
    description: str

    def get_tool_paths(self, tool_name: str, subtool: str) -> list:
        """Get tool paths for a specific tool"""
        return self.raw_config.get('tools', {}).get(tool_name, {}).get(subtool, {}).get('paths', [])

    def get_tool_executable(self, tool_name: str, subtool: str) -> str:
        """Get executable name for a tool"""
        return self.raw_config.get('tools', {}).get(tool_name, {}).get(subtool, {}).get('executable', '')

    def get_technology_config(self, tech_name: str) -> dict[str, Any]:
        """Get technology configuration"""
        return self.raw_config.get('technologies', {}).get(tech_name, {})

    def get_environment_vars(self) -> dict[str, str]:
        """Get all environment variables"""
        env_vars = self.raw_config.get('environment', {}).copy()
        additional = env_vars.pop('additional_env', {})
        env_vars.update(additional)
        return env_vars

    def get_synthesis_defaults(self) -> dict[str, Any]:
        """Get synthesis default parameters"""
        return self.raw_config.get('synthesis', {}).get('defaults', {})

    def get_feature_modes(self) -> dict[str, str]:
        """Get feature mode mappings"""
        return self.raw_config.get('synthesis', {}).get('feature_modes', {})

    def get_compile_options(self, optimization_mode: str = 'standard') -> list:
        """Get compilation options for given mode"""
        return self.raw_config.get('synthesis', {}).get('compile_options', {}).get(optimization_mode, ['compile_ultra'])


class ConfigManager:
    """Manages machine-specific synthesis configurations"""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent / "configs"
        self.config_dir = Path(config_dir)
        self._configs_cache = {}

    def _load_config_file(self, config_file: Path) -> dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_file) as f:
                config = json.load(f)

            # Expand environment variables in paths
            config = self._expand_env_vars(config)
            return config

        except Exception as e:
            raise RuntimeError(f"Failed to load config {config_file}: {e}")

    def _expand_env_vars(self, config: dict[str, Any]) -> dict[str, Any]:
        """Recursively expand environment variables in config"""
        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Handle ${VAR} and ${VAR:-default} syntax
            import re

            def replace_var(match):
                var_expr = match.group(1)
                if ':-' in var_expr:
                    var_name, default = var_expr.split(':-', 1)
                    return os.environ.get(var_name, default)
                else:
                    return os.environ.get(var_expr, match.group(0))

            return re.sub(r'\$\{([^}]+)\}', replace_var, config)
        else:
            return config

    def get_available_configs(self) -> list:
        """Get list of available configuration names"""
        configs = []
        if self.config_dir.exists():
            for config_file in self.config_dir.glob("*.json"):
                if config_file.stem not in ['template']:
                    configs.append(config_file.stem)
        return sorted(configs)

    def detect_machine_config(self) -> Optional[str]:
        """Auto-detect machine configuration based on hostname"""
        hostname = socket.gethostname()

        # Check environment variable first
        env_config = os.environ.get('WALLY_MACHINE_CONFIG')
        if env_config and self._config_exists(env_config):
            return env_config

        # Check hostname matching
        for config_name in self.get_available_configs():
            try:
                config = self._load_config_file(self.config_dir / f"{config_name}.json")
                hostnames = config.get('machine_info', {}).get('hostnames', [])

                # Check for exact match or wildcard
                if hostname in hostnames or '*' in hostnames:
                    return config_name

                # Check for partial matches (e.g., avatar.hmc.edu matches avatar)
                for pattern in hostnames:
                    if pattern != '*' and (pattern in hostname or hostname.startswith(pattern)):
                        return config_name

            except Exception:
                continue

        # Fallback to generic-linux if it exists
        if self._config_exists('generic-linux'):
            return 'generic-linux'

        return None

    def _config_exists(self, config_name: str) -> bool:
        """Check if a configuration exists"""
        return (self.config_dir / f"{config_name}.json").exists()

    def load_config(self, config_name: Optional[str] = None) -> MachineConfig:
        """Load machine configuration"""
        # Auto-detect if not specified
        if config_name is None:
            config_name = self.detect_machine_config()

        if config_name is None:
            raise RuntimeError("No suitable machine configuration found. Create a config or use --machine-config")

        # Check cache
        if config_name in self._configs_cache:
            return self._configs_cache[config_name]

        config_file = self.config_dir / f"{config_name}.json"
        if not config_file.exists():
            available = ", ".join(self.get_available_configs())
            raise RuntimeError(f"Configuration '{config_name}' not found. Available: {available}")

        # Load configuration
        raw_config = self._load_config_file(config_file)

        machine_config = MachineConfig(
            raw_config=raw_config,
            name=config_name,
            description=raw_config.get('description', f"Configuration: {config_name}")
        )

        # Cache it
        self._configs_cache[config_name] = machine_config

        return machine_config

    def validate_config(self, config: MachineConfig, verbose: bool = False) -> list:
        """Validate configuration and return list of issues"""
        issues = []

        # Check required tools exist
        dc_paths = config.get_tool_paths('synopsys', 'dc_shell')
        dc_executable = config.get_tool_executable('synopsys', 'dc_shell')

        dc_found = False
        for path in dc_paths:
            dc_path = Path(path) / dc_executable
            if dc_path.exists():
                dc_found = True
                if verbose:
                    print(f"✅ Found Design Compiler: {dc_path}")
                break

        if not dc_found:
            issues.append(f"Design Compiler not found in any of: {dc_paths}")

        # Check technology libraries
        for tech_name, tech_config in config.raw_config.get('technologies', {}).items():
            lib_path = Path(tech_config.get('lib_path', ''))
            lib_name = tech_config.get('lib_name', '')

            if lib_path.exists():
                lib_file = lib_path / lib_name
                if lib_file.exists():
                    if verbose:
                        print(f"✅ Found {tech_name} library: {lib_file}")
                else:
                    issues.append(f"Technology {tech_name} library file missing: {lib_file}")
            else:
                issues.append(f"Technology {tech_name} library path missing: {lib_path}")

        return issues


if __name__ == '__main__':
    # Test configuration loading
    manager = ConfigManager()

    print("Available configurations:")
    for config_name in manager.get_available_configs():
        print(f"  {config_name}")

    print(f"\nDetected configuration: {manager.detect_machine_config()}")

    # Load and validate
    try:
        config = manager.load_config()
        print(f"\nLoaded: {config.name} - {config.description}")

        issues = manager.validate_config(config, verbose=True)
        if issues:
            print("\n⚠️  Configuration issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ Configuration validated successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
