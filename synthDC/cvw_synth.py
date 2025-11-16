#!/usr/bin/env python3
"""
CVW Synthesis Tool - Intuitive synthesis automation for CVW RISC-V processor

Simple, clear interface for running synthesis experiments on the complete CVW processor.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


class CVWSynthesizer:
    """Main synthesis controller for CVW processor"""

    def __init__(self, tech='sky130', verbose=False):
        self.tech = tech
        self.verbose = verbose
        self.base_path = Path(__file__).parent.parent
        self.synth_dir = self.base_path / "synthDC"

        # Technology defaults
        self.tech_defaults = {
            'sky130': {'freq': 330, 'sram': False},
            'sky90': {'freq': 870, 'sram': False},
            'tsmc28': {'freq': 2800, 'sram': False},
            'tsmc28psyn': {'freq': 2800, 'sram': True}
        }

        # Available configurations
        self.configs = ['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc']
        self.feature_modes = ['baseline', 'no_atomic', 'no_fpu', 'no_muldiv', 'no_priv', 'pmp_off']

        self._setup_environment()

    def _setup_environment(self):
        """Setup environment for synthesis"""
        # Set WALLY if not present
        if 'WALLY' not in os.environ:
            os.environ['WALLY'] = str(self.base_path)

        # Add Synopsys tools to PATH
        synopsys_paths = [
            "/opt/snps/syn/V-2023.12-SP5-3/bin",
            "/opt/snps/syn/W-2024.09-SP4-1/bin"  # Alternative version
        ]

        current_path = os.environ.get('PATH', '')
        for syn_path in synopsys_paths:
            if os.path.exists(syn_path) and syn_path not in current_path:
                os.environ['PATH'] = f"{syn_path}:{current_path}"
                break

    def _run_synthesis(self, config, freq, feature_mode='baseline', max_opt=False):
        """Run a single synthesis"""

        # Map feature modes to MOD parameter
        mod_map = {
            'baseline': 'orig',
            'no_atomic': 'noAtomic',
            'no_fpu': 'noFPU',
            'no_muldiv': 'noMulDiv',
            'no_priv': 'noPriv',
            'pmp_off': 'pmp0'
        }

        mod = mod_map.get(feature_mode, 'orig')
        use_sram = self.tech_defaults[self.tech]['sram']
        maxopt = 1 if max_opt else 0
        usesram = 1 if use_sram else 0

        # Build synthesis command
        cmd = [
            "make", "synth",
            "DESIGN=wallypipelinedcore",
            f"CONFIG={config}",
            f"MOD={mod}",
            f"TECH={self.tech}",
            "DRIVE=FLOP",
            f"FREQ={freq}",
            f"MAXOPT={maxopt}",
            f"USESRAM={usesram}",
            "MAXCORES=1"
        ]

        if self.verbose:
            print(f"Running: {' '.join(cmd)}")

        # Run synthesis
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=self.synth_dir,
                env=os.environ.copy(),
                capture_output=not self.verbose,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            elapsed = time.time() - start_time

            if result.returncode == 0:
                if self.verbose:
                    print(f"✓ SUCCESS: {config} @ {freq}MHz ({elapsed:.1f}s)")
                return {
                    'config': config,
                    'freq': freq,
                    'feature_mode': feature_mode,
                    'success': True,
                    'time': elapsed,
                    'error': None
                }
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                if self.verbose:
                    print(f"✗ FAILED: {config} @ {freq}MHz - {error_msg}")
                return {
                    'config': config,
                    'freq': freq,
                    'feature_mode': feature_mode,
                    'success': False,
                    'time': elapsed,
                    'error': error_msg
                }

        except subprocess.TimeoutExpired:
            if self.verbose:
                print(f"✗ TIMEOUT: {config} @ {freq}MHz")
            return {
                'config': config,
                'freq': freq,
                'feature_mode': feature_mode,
                'success': False,
                'time': 3600,
                'error': "Timeout after 1 hour"
            }
        except Exception as e:
            if self.verbose:
                print(f"✗ ERROR: {config} @ {freq}MHz - {e}")
            return {
                'config': config,
                'freq': freq,
                'feature_mode': feature_mode,
                'success': False,
                'time': 0,
                'error': str(e)
            }

    def synthesize_single(self, config='rv64gc', freq=None, feature_mode='baseline', max_opt=False):
        """Run single synthesis"""
        if freq is None:
            freq = self.tech_defaults[self.tech]['freq']

        print(f"🔧 Running single synthesis: {config} @ {freq}MHz on {self.tech}")
        result = self._run_synthesis(config, freq, feature_mode, max_opt)

        if result['success']:
            print(f"✅ Synthesis completed in {result['time']:.1f}s")
        else:
            print(f"❌ Synthesis failed: {result['error']}")

        return result

    def frequency_sweep(self, config='rv32e', base_freq=None, range_pct=20, steps=13):
        """Run frequency sweep around base frequency"""
        if base_freq is None:
            base_freq = self.tech_defaults[self.tech]['freq']

        # Generate frequency points
        min_freq = base_freq * (100 - range_pct) // 100
        max_freq = base_freq * (100 + range_pct) // 100
        freqs = [int(min_freq + (max_freq - min_freq) * i / (steps - 1)) for i in range(steps)]

        print(f"🔧 Running frequency sweep: {config} from {min_freq}-{max_freq}MHz ({steps} points)")

        results = []
        for freq in freqs:
            result = self._run_synthesis(config, freq)
            results.append(result)

        successful = sum(1 for r in results if r['success'])
        print(f"✅ Frequency sweep completed: {successful}/{len(results)} successful")

        return results

    def config_sweep(self, freq=None, configs=None):
        """Test all RISC-V configurations"""
        if freq is None:
            freq = self.tech_defaults[self.tech]['freq']
        if configs is None:
            configs = self.configs

        print(f"🔧 Running config sweep: {len(configs)} configurations @ {freq}MHz")

        results = []
        for config in configs:
            result = self._run_synthesis(config, freq)
            results.append(result)

        successful = sum(1 for r in results if r['success'])
        print(f"✅ Config sweep completed: {successful}/{len(results)} successful")

        return results

    def feature_sweep(self, config='rv64gc', freq=None, features=None):
        """Test feature ablation (what happens when we remove features)"""
        if freq is None:
            freq = self.tech_defaults[self.tech]['freq']
        if features is None:
            features = self.feature_modes

        print(f"🔧 Running feature sweep: {config} with {len(features)} feature sets @ {freq}MHz")

        results = []
        for feature_mode in features:
            result = self._run_synthesis(config, freq, feature_mode)
            results.append(result)

        successful = sum(1 for r in results if r['success'])
        print(f"✅ Feature sweep completed: {successful}/{len(results)} successful")

        return results

    def comprehensive_sweep(self, parallel=False):
        """Run complete synthesis characterization"""
        print(f"🔧 Running comprehensive synthesis suite for {self.tech}")

        all_results = []

        # Phase 1: Frequency sweeps for key configs
        key_configs = ['rv32e', 'rv64gc']
        for config in key_configs:
            print(f"\n📊 Frequency sweep: {config}")
            results = self.frequency_sweep(config)
            all_results.extend(results)

        # Phase 2: Config sweep at nominal frequency
        print("\n📊 Configuration sweep")
        results = self.config_sweep()
        all_results.extend(results)

        # Phase 3: Feature ablation
        print("\n📊 Feature ablation study")
        results = self.feature_sweep()
        all_results.extend(results)

        # Summary
        total_runs = len(all_results)
        successful = sum(1 for r in all_results if r['success'])
        total_time = sum(r['time'] for r in all_results)

        print("\n🎯 Comprehensive sweep completed:")
        print(f"   • Total runs: {total_runs}")
        print(f"   • Successful: {successful} ({successful/total_runs*100:.1f}%)")
        print(f"   • Total time: {total_time/3600:.1f} hours")

        return all_results


def main():
    parser = argparse.ArgumentParser(
        description='CVW Synthesis Tool - Intuitive synthesis automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single synthesis
  %(prog)s single rv64gc --freq 300 --tech sky130

  # Frequency sweep
  %(prog)s freq-sweep rv32e --base-freq 330 --range 20 --tech sky130

  # Test all RISC-V configs
  %(prog)s config-sweep --freq 330 --tech sky130

  # Feature ablation study
  %(prog)s feature-sweep rv64gc --freq 330 --tech sky130

  # Complete characterization
  %(prog)s comprehensive --tech sky130
        """)

    # Common arguments
    parser.add_argument('--tech', choices=['sky130', 'sky90', 'tsmc28', 'tsmc28psyn'],
                       default='sky130', help='Technology node (default: sky130)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Synthesis modes')

    # Single synthesis
    single_parser = subparsers.add_parser('single', help='Run single synthesis')
    single_parser.add_argument('config', nargs='?', default='rv64gc',
                              choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                              help='RISC-V configuration (default: rv64gc)')
    single_parser.add_argument('--freq', type=int, help='Frequency in MHz (default: technology default)')
    single_parser.add_argument('--feature-mode', choices=['baseline', 'no_atomic', 'no_fpu', 'no_muldiv', 'no_priv', 'pmp_off'],
                              default='baseline', help='Feature set to test (default: baseline)')
    single_parser.add_argument('--max-opt', action='store_true', help='Enable maximum optimization')

    # Frequency sweep
    freq_parser = subparsers.add_parser('freq-sweep', help='Run frequency sweep')
    freq_parser.add_argument('config', nargs='?', default='rv32e',
                            choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                            help='RISC-V configuration (default: rv32e)')
    freq_parser.add_argument('--base-freq', type=int, help='Base frequency in MHz (default: technology default)')
    freq_parser.add_argument('--range', type=int, default=20, help='Frequency range ±percentage (default: 20)')
    freq_parser.add_argument('--steps', type=int, default=13, help='Number of frequency points (default: 13)')

    # Config sweep
    config_parser = subparsers.add_parser('config-sweep', help='Test all RISC-V configurations')
    config_parser.add_argument('--freq', type=int, help='Frequency in MHz (default: technology default)')
    config_parser.add_argument('--configs', nargs='+',
                              choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                              help='Specific configs to test (default: all)')

    # Feature sweep
    feature_parser = subparsers.add_parser('feature-sweep', help='Feature ablation study')
    feature_parser.add_argument('config', nargs='?', default='rv64gc',
                               choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                               help='RISC-V configuration (default: rv64gc)')
    feature_parser.add_argument('--freq', type=int, help='Frequency in MHz (default: technology default)')
    feature_parser.add_argument('--features', nargs='+',
                               choices=['baseline', 'no_atomic', 'no_fpu', 'no_muldiv', 'no_priv', 'pmp_off'],
                               help='Specific features to test (default: all)')

    # Comprehensive
    comp_parser = subparsers.add_parser('comprehensive', help='Complete synthesis characterization')
    comp_parser.add_argument('--parallel', action='store_true', help='Run synthesis in parallel (experimental)')

    args = parser.parse_args()

    # Show help if no command given
    if args.command is None:
        parser.print_help()
        return

    # Create synthesizer
    synth = CVWSynthesizer(tech=args.tech, verbose=args.verbose)

    # Execute command
    try:
        if args.command == 'single':
            synth.synthesize_single(
                config=args.config,
                freq=args.freq,
                feature_mode=args.feature_mode,
                max_opt=args.max_opt
            )

        elif args.command == 'freq-sweep':
            synth.frequency_sweep(
                config=args.config,
                base_freq=args.base_freq,
                range_pct=args.range,
                steps=args.steps
            )

        elif args.command == 'config-sweep':
            synth.config_sweep(
                freq=args.freq,
                configs=args.configs
            )

        elif args.command == 'feature-sweep':
            synth.feature_sweep(
                config=args.config,
                freq=args.freq,
                features=args.features
            )

        elif args.command == 'comprehensive':
            synth.comprehensive_sweep(parallel=args.parallel)

    except KeyboardInterrupt:
        print("\n⚠️  Synthesis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
