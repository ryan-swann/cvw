#!/usr/bin/env python3
"""
Create mock synthesis data for dashboard demonstration
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path


def create_mock_result_file(date_str, filename, run_type, configs, frequencies, technologies=None):
    """Create a mock result file with realistic synthesis data"""
    if technologies is None:
        technologies = ['sky130']

    results_dir = Path("results") / date_str
    results_dir.mkdir(parents=True, exist_ok=True)

    # Generate mock results
    results = []
    for config in configs:
        for freq in frequencies:
            for tech in technologies:
                # Generate realistic area based on configuration complexity
                base_areas = {
                    'rv32e': 8000,
                    'rv32i': 12000,
                    'rv32imc': 15000,
                    'rv32gc': 18000,
                    'rv64i': 22000,
                    'rv64gc': 28000
                }

                base_area = base_areas.get(config, 15000)
                # Area increases with frequency (more buffering needed)
                area_scaling = 1.0 + (freq - 200) * 0.0008
                area = base_area * area_scaling * random.uniform(0.95, 1.05)

                # Slack decreases with frequency (timing gets harder)
                target_period = 1000 / freq  # ns
                slack = (target_period * 0.1) * random.uniform(0.5, 2.0) - (freq - 200) * 0.002
                if freq > 400:  # High frequency runs start failing
                    slack *= random.uniform(-0.5, 1.2)

                # Synthesis time varies
                synth_time = random.uniform(15, 45)

                # Cell count roughly proportional to area
                cell_count = int(area / 4.2 * random.uniform(0.9, 1.1))

                success = slack > -0.1 and random.random() > 0.05  # 95% success rate for reasonable configs

                result = {
                    'config': {
                        'design': 'wallypipelinedcore',
                        'config': config,
                        'frequency_mhz': freq,
                        'technology': tech,
                        'feature_mode': 'baseline',
                        'max_optimization': False,
                        'use_sram': False,
                        'width': 32
                    },
                    'success': success,
                    'metrics': {
                        'area_um2': area if success else None,
                        'slack_ns': slack if success else None,
                        'power_mw': None,  # Not always available
                        'cell_count': cell_count if success else None,
                        'synthesis_time_s': synth_time,
                        'critical_path_ns': target_period - slack if success and slack > 0 else None
                    },
                    'run_directory': f"runs/mock_{config}_{tech}_{freq}MHz_{date_str.replace('-', '_')}",
                    'error_message': "Timing violation" if not success else None
                }
                results.append(result)

    # Calculate summary statistics
    successful = [r for r in results if r['success']]
    areas = [r['metrics']['area_um2'] for r in successful if r['metrics']['area_um2']]
    slacks = [r['metrics']['slack_ns'] for r in successful if r['metrics']['slack_ns']]
    times = [r['metrics']['synthesis_time_s'] for r in results if r['metrics']['synthesis_time_s']]

    summary = {
        'status': 'success' if len(successful) == len(results) else 'partial',
        'success_rate': len(successful) / len(results),
        'total_runs': len(results),
        'successful_runs': len(successful),
        'failed_runs': len(results) - len(successful)
    }

    if areas:
        summary['area_statistics'] = {
            'min_um2': min(areas),
            'max_um2': max(areas),
            'mean_um2': sum(areas) / len(areas),
            'range_um2': max(areas) - min(areas),
            'count': len(areas)
        }

    if slacks:
        summary['timing_statistics'] = {
            'min_slack_ns': min(slacks),
            'max_slack_ns': max(slacks),
            'mean_slack_ns': sum(slacks) / len(slacks),
            'violations': sum(1 for s in slacks if s < 0),
            'count': len(slacks)
        }

    if times:
        summary['performance_statistics'] = {
            'min_time_s': min(times),
            'max_time_s': max(times),
            'mean_time_s': sum(times) / len(times),
            'total_time_s': sum(times),
            'count': len(times)
        }

    # Create complete result file
    result_data = {
        'metadata': {
            'timestamp': f"{date_str} 14:30:22",
            'iso_timestamp': f"{date_str}T14:30:22",
            'run_type': run_type,
            'machine_config': {
                'name': 'avatar',
                'hostname': 'avatar.okstate.edu',
                'description': 'Oklahoma State University Research Server',
                'location': 'Stillwater, OK'
            },
            'git_info': {
                'hash': 'a1b2c3d',
                'branch': 'synth_fix',
                'status': 'clean'
            },
            'environment': {
                'wally_path': '/home/rswann/cvw',
                'synopsys_home': '/tools/synopsys/2024.09',
                'python_version': '3.11.5'
            },
            'run_statistics': {
                'total_runs': len(results),
                'successful_runs': len(successful),
                'failed_runs': len(results) - len(successful),
                'total_time_s': sum(times),
                'configurations': len(set(r['config']['config'] for r in results)),
                'technologies': len(set(r['config']['technology'] for r in results)),
                'frequency_points': len(set(r['config']['frequency_mhz'] for r in results))
            }
        },
        'summary': summary,
        'results': results
    }

    # Write file
    filepath = results_dir / filename
    with open(filepath, 'w') as f:
        json.dump(result_data, f, indent=2, sort_keys=True)

    print(f"Created mock data: {filepath}")
    return filepath

def main():
    """Generate a realistic set of mock synthesis data"""

    # Create data for the last few days
    today = datetime.now()

    # Day 1: Single runs
    date1 = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    create_mock_result_file(
        date1, "single_rv32e_sky130_250MHz_baseline_143022.json",
        "single", ["rv32e"], [250]
    )

    create_mock_result_file(
        date1, "single_rv64gc_sky130_300MHz_baseline_151234.json",
        "single", ["rv64gc"], [300]
    )

    # Day 2: Frequency sweep
    date2 = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    create_mock_result_file(
        date2, "freq-sweep_rv32e_sky130_sweep_200-400MHz_7pts_091234.json",
        "freq-sweep", ["rv32e"], [200, 233, 266, 300, 333, 366, 400]
    )

    create_mock_result_file(
        date2, "freq-sweep_rv64gc_sky130_sweep_250-450MHz_7pts_141234.json",
        "freq-sweep", ["rv64gc"], [250, 283, 316, 350, 383, 416, 450]
    )

    # Day 3 (today): Configuration sweep and comprehensive
    date3 = today.strftime("%Y-%m-%d")
    create_mock_result_file(
        date3, "config-sweep_3configs_sky130_300MHz_101234.json",
        "config-sweep", ["rv32e", "rv32gc", "rv64gc"], [300]
    )

    create_mock_result_file(
        date3, "comprehensive_rv32e_rv32gc_rv64gc_sky130_250-350MHz_baseline_141234.json",
        "comprehensive", ["rv32e", "rv32gc", "rv64gc"], [250, 275, 300, 325, 350]
    )

    print("\n📊 Mock synthesis data created successfully!")
    print("You can now run the dashboard to see the analysis.")

if __name__ == '__main__':
    main()
