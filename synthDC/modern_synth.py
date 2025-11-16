#!/usr/bin/env python3
"""
Wally Modern Synthesis CLI
==========================

Clean, intuitive interface for CVW synthesis using the Wally synthesis engine.
No more Makefile/TCL mess - everything is maintainable Python code.
"""

import argparse
import sys
from pathlib import Path

# Import our Wally synthesis engine
from wally_synth_engine import CVWSynthesisEngine, SynthesisConfig, SynthesisResult


def create_frequency_sweep_configs(base_config: SynthesisConfig, base_freq: int,
                                 range_pct: int, steps: int) -> list[SynthesisConfig]:
    """Create configurations for frequency sweep"""
    min_freq = base_freq * (100 - range_pct) // 100
    max_freq = base_freq * (100 + range_pct) // 100

    configs = []
    for i in range(steps):
        freq = int(min_freq + (max_freq - min_freq) * i / (steps - 1))
        config = SynthesisConfig(
            design=base_config.design,
            config=base_config.config,
            frequency_mhz=freq,
            technology=base_config.technology,
            feature_mode=base_config.feature_mode,
            max_optimization=base_config.max_optimization,
            use_sram=base_config.use_sram,
            width=base_config.width
        )
        configs.append(config)

    return configs


def create_config_sweep_configs(base_config: SynthesisConfig,
                               configs: list[str]) -> list[SynthesisConfig]:
    """Create configurations for RISC-V config sweep"""
    sweep_configs = []
    for config_name in configs:
        config = SynthesisConfig(
            design=base_config.design,
            config=config_name,
            frequency_mhz=base_config.frequency_mhz,
            technology=base_config.technology,
            feature_mode=base_config.feature_mode,
            max_optimization=base_config.max_optimization,
            use_sram=base_config.use_sram,
            width=base_config.width
        )
        sweep_configs.append(config)

    return sweep_configs


def create_feature_sweep_configs(base_config: SynthesisConfig,
                                features: list[str]) -> list[SynthesisConfig]:
    """Create configurations for feature ablation study"""
    sweep_configs = []
    for feature in features:
        config = SynthesisConfig(
            design=base_config.design,
            config=base_config.config,
            frequency_mhz=base_config.frequency_mhz,
            technology=base_config.technology,
            feature_mode=feature,
            max_optimization=base_config.max_optimization,
            use_sram=base_config.use_sram,
            width=base_config.width
        )
        sweep_configs.append(config)

    return sweep_configs


def print_results_summary(results: list[SynthesisResult]):
    """Print a nice summary of synthesis results"""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print("\n📊 Synthesis Results Summary")
    print(f"{'='*50}")
    print(f"Total runs: {len(results)}")
    print(f"Successful: {len(successful)} ✅")
    print(f"Failed: {len(failed)} ❌")

    if successful:
        total_time = sum(r.synthesis_time_s for r in successful if r.synthesis_time_s)
        avg_time = total_time / len(successful)

        areas = [r.area_um2 for r in successful if r.area_um2]
        if areas:
            min_area = min(areas)
            max_area = max(areas)
            avg_area = sum(areas) / len(areas)

            print("\nArea Statistics:")
            print(f"  Min: {min_area:,.1f} µm²")
            print(f"  Max: {max_area:,.1f} µm²")
            print(f"  Avg: {avg_area:,.1f} µm²")

        print("\nTiming Statistics:")
        print(f"  Average synthesis time: {avg_time:.1f}s")

        # Show best results
        print("\n🏆 Best Results:")
        if areas:
            best_area = min(successful, key=lambda r: r.area_um2 if r.area_um2 else float('inf'))
            print(f"  Smallest area: {best_area.config.config} @ {best_area.config.frequency_mhz}MHz = {best_area.area_um2:,.1f} µm²")

        fastest_synth = min(successful, key=lambda r: r.synthesis_time_s if r.synthesis_time_s else float('inf'))
        print(f"  Fastest synthesis: {fastest_synth.config.config} @ {fastest_synth.config.frequency_mhz}MHz = {fastest_synth.synthesis_time_s:.1f}s")

    if failed:
        print("\n❌ Failed Runs:")
        for result in failed:
            print(f"  {result.config.config} @ {result.config.frequency_mhz}MHz: {result.error_message}")


def main():
    parser = argparse.ArgumentParser(
        description='CVW Modern Synthesis - Pure Python Implementation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single synthesis
  %(prog)s single rv64gc --freq 300

  # Frequency sweep
  %(prog)s freq-sweep rv32e --base-freq 300 --range 20 --steps 5

  # Configuration comparison
  %(prog)s config-sweep --freq 300 --configs rv32e rv32gc rv64gc

  # Feature ablation study
  %(prog)s feature-sweep rv64gc --freq 300 --features baseline no_fpu no_muldiv

  # Complete characterization
  %(prog)s comprehensive
        """)

    # Global options
    parser.add_argument('--tech', choices=['sky130', 'sky90', 'tsmc28', 'tsmc28psyn'],
                       default='sky130', help='Technology node (default: sky130)')
    parser.add_argument('--machine-config', help='Machine configuration name (auto-detected if not specified)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--max-opt', action='store_true', help='Enable maximum optimization')
    parser.add_argument('--save-results', help='Save results to JSON file')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Synthesis modes')

    # Single synthesis
    single_parser = subparsers.add_parser('single', help='Run single synthesis')
    single_parser.add_argument('config', nargs='?', default='rv64gc',
                              choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                              help='RISC-V configuration')
    single_parser.add_argument('--freq', type=int, help='Frequency in MHz')
    single_parser.add_argument('--feature', choices=['baseline', 'no_atomic', 'no_fpu', 'no_muldiv', 'no_priv', 'pmp_off'],
                              default='baseline', help='Feature mode')

    # Frequency sweep
    freq_parser = subparsers.add_parser('freq-sweep', help='Frequency sweep analysis')
    freq_parser.add_argument('config', nargs='?', default='rv32e',
                            choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                            help='RISC-V configuration')
    freq_parser.add_argument('--base-freq', type=int, help='Base frequency in MHz')
    freq_parser.add_argument('--range', type=int, default=20, help='Frequency range ±percentage')
    freq_parser.add_argument('--steps', type=int, default=7, help='Number of frequency points')

    # Config sweep
    config_parser = subparsers.add_parser('config-sweep', help='RISC-V configuration comparison')
    config_parser.add_argument('--freq', type=int, help='Frequency in MHz')
    config_parser.add_argument('--configs', nargs='+',
                              choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                              default=['rv32e', 'rv32gc', 'rv64gc'],
                              help='Configurations to test')

    # Feature sweep
    feature_parser = subparsers.add_parser('feature-sweep', help='Feature ablation study')
    feature_parser.add_argument('config', nargs='?', default='rv64gc',
                               choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                               help='RISC-V configuration')
    feature_parser.add_argument('--freq', type=int, help='Frequency in MHz')
    feature_parser.add_argument('--features', nargs='+',
                               choices=['baseline', 'no_atomic', 'no_fpu', 'no_muldiv', 'no_priv', 'pmp_off'],
                               default=['baseline', 'no_atomic', 'no_fpu', 'no_muldiv', 'no_priv'],
                               help='Features to test')

    # Comprehensive
    subparsers.add_parser('comprehensive', help='Complete synthesis characterization')

    # Dashboard
    dashboard_parser = subparsers.add_parser('dashboard', help='Analysis dashboard for synthesis results')
    dashboard_parser.add_argument('--days', type=int, default=7, help='Days of history to analyze')
    dashboard_parser.add_argument('--report', action='store_true', help='Generate text summary report')
    dashboard_parser.add_argument('--plots', action='store_true', help='Generate publication plots')
    dashboard_parser.add_argument('--export', choices=['csv', 'xlsx'], help='Export data table')
    dashboard_parser.add_argument('--config-filter', nargs='+',
                                 choices=['rv32e', 'rv32i', 'rv32imc', 'rv32gc', 'rv64i', 'rv64gc'],
                                 help='Filter to specific configurations')
    dashboard_parser.add_argument('--output-dir', type=str, help='Output directory for plots/exports')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # Create synthesis engine with machine config
    engine = CVWSynthesisEngine(verbose=args.verbose, machine_config=args.machine_config)

    # Get technology defaults from machine configuration
    def get_tech_default_freq(tech_name: str) -> int:
        tech_config = engine.machine_config.get_technology_config(tech_name)
        return tech_config.get('default_freq_mhz', 330) if tech_config else 330

    try:
        results = []

        if args.command == 'single':
            # Single synthesis
            freq = args.freq if args.freq else get_tech_default_freq(args.tech)
            config = SynthesisConfig(
                config=args.config,
                frequency_mhz=freq,
                technology=args.tech,
                feature_mode=args.feature,
                max_optimization=args.max_opt
            )

            result = engine.synthesize(config)
            results = [result]

        elif args.command == 'freq-sweep':
            # Frequency sweep
            base_freq = args.base_freq if args.base_freq else get_tech_default_freq(args.tech)
            base_config = SynthesisConfig(
                config=args.config,
                frequency_mhz=base_freq,
                technology=args.tech,
                max_optimization=args.max_opt
            )

            configs = create_frequency_sweep_configs(base_config, base_freq, args.range, args.steps)
            print(f"🔧 Frequency sweep: {args.config} from {configs[0].frequency_mhz}-{configs[-1].frequency_mhz}MHz ({len(configs)} points)")
            results = engine.batch_synthesize(configs)

        elif args.command == 'config-sweep':
            # Configuration sweep
            freq = args.freq if args.freq else get_tech_default_freq(args.tech)
            base_config = SynthesisConfig(
                frequency_mhz=freq,
                technology=args.tech,
                max_optimization=args.max_opt
            )

            configs = create_config_sweep_configs(base_config, args.configs)
            print(f"🔧 Configuration sweep: {len(args.configs)} configs @ {freq}MHz")
            results = engine.batch_synthesize(configs)

        elif args.command == 'feature-sweep':
            # Feature ablation
            freq = args.freq if args.freq else get_tech_default_freq(args.tech)
            base_config = SynthesisConfig(
                config=args.config,
                frequency_mhz=freq,
                technology=args.tech,
                max_optimization=args.max_opt
            )

            configs = create_feature_sweep_configs(base_config, args.features)
            print(f"🔧 Feature ablation: {args.config} with {len(args.features)} feature sets @ {freq}MHz")
            results = engine.batch_synthesize(configs)

        elif args.command == 'comprehensive':
            # Complete characterization
            print(f"🔧 Comprehensive synthesis suite for {args.tech}")
            all_results = []

            # Frequency sweeps for key configs
            for config_name in ['rv32e', 'rv64gc']:
                base_freq = get_tech_default_freq(args.tech)
                base_config = SynthesisConfig(
                    config=config_name,
                    frequency_mhz=base_freq,
                    technology=args.tech,
                    max_optimization=args.max_opt
                )
                configs = create_frequency_sweep_configs(base_config, base_freq, 20, 7)
                print(f"\n📊 Frequency sweep: {config_name}")
                sweep_results = engine.batch_synthesize(configs)
                all_results.extend(sweep_results)

            # Config sweep
            print("\n📊 Configuration sweep")
            base_config = SynthesisConfig(
                frequency_mhz=get_tech_default_freq(args.tech),
                technology=args.tech,
                max_optimization=args.max_opt
            )
            configs = create_config_sweep_configs(base_config, ['rv32e', 'rv32gc', 'rv64gc'])
            config_results = engine.batch_synthesize(configs)
            all_results.extend(config_results)

            # Feature ablation
            print("\n📊 Feature ablation study")
            base_config = SynthesisConfig(
                config='rv64gc',
                frequency_mhz=get_tech_default_freq(args.tech),
                technology=args.tech,
                max_optimization=args.max_opt
            )
            configs = create_feature_sweep_configs(base_config, ['baseline', 'no_atomic', 'no_fpu', 'no_muldiv'])
            feature_results = engine.batch_synthesize(configs)
            all_results.extend(feature_results)

            results = all_results

        elif args.command == 'dashboard':
            # Dashboard analysis
            from synthesis_dashboard import WallySynthesisDashboard
            dashboard = WallySynthesisDashboard()

            output_dir = None
            if args.output_dir:
                output_dir = Path(args.output_dir)

            if args.report or not any([args.plots, args.export]):
                # Generate and show summary report (default)
                print(dashboard.generate_summary_report(days_back=args.days))

            if args.plots:
                # Generate publication plots
                files = dashboard.generate_publication_suite(
                    output_dir=output_dir,
                    config_filter=args.config_filter
                )
                print(f"\n📊 Generated {len(files)} publication files")

            if args.export:
                # Export data table
                export_path = dashboard.export_data_table(
                    output_path=output_dir / f"synthesis_data.{args.export}" if output_dir else None,
                    format=args.export
                )
                print(f"\n📋 Data exported to {export_path}")

            return  # Exit early for dashboard commands

        # Print summary for synthesis commands
        print_results_summary(results)

        # Save results if requested
        if args.save_results:
            engine.save_results(results, args.save_results, run_type=args.command)
        else:
            # Always save results with auto-generated name
            engine.save_results(results, run_type=args.command)

        # Exit with error if any synthesis failed
        failed_count = sum(1 for r in results if not r.success)
        if failed_count > 0:
            print(f"\n⚠️  {failed_count} synthesis run(s) failed")
            sys.exit(1)
        else:
            print("\n🎉 All synthesis runs completed successfully!")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
