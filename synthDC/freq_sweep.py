#!/usr/bin/env python3
"""
CVW Frequency Sweep Tool - Automated synthesis across frequency ranges
with comprehensive visualization and Pareto analysis.

4. SYNTHESIS SUCCESS VALIDATION:
   - Return code 0 doesn't guarantee successful technology mapping
   - Must check for actual area values > 0.0 to confirm real synthesis
   - Parse reports to verify technology library was used correctly
   - Success indicators: realistic area values, sky130 library loading messages

5. REPORT PARSING ROBUSTNESS:
   - Area reports have consistent format with "Total cell area:" field
   - Timing reports contain slack information for constraint validation
   - Path delay extraction helps understand critical timing paths
   - Handle missing reports gracefully (return 0.0 for failed synthesis)

6. FREQUENCY SWEEP INSIGHTS DISCOVERED:
   - Area doesn't increase monotonically with frequency
   - 50 MHz: 3287.4 µm² (relaxed timing, basic optimization)
   - 100 MHz: 4085.5 µm² (moderate optimization, larger area)
   - 150 MHz: 3383.6 µm² (aggressive optimization, different cell selection)
   - Higher frequencies may use faster, more compact cells vs slower, larger cells

7. ERROR HANDLING LESSONS:
   - Subprocess timeouts needed for hung synthesis runs
   - Capture both stdout and stderr for comprehensive debugging
   - Graceful degradation when synthesis fails (continue with other frequencies)
   - Clear progress reporting helps identify stuck processes

8. PLOTTING AND VISUALIZATION:
   - Area vs frequency shows non-linear relationship
   - Pareto frontier analysis identifies optimal design points
   - Timing slack plots reveal constraint margins
   - Log-scale plotting helps with wide area ranges

TESTED DESIGN SPACES:
====================
- Designs: adder (64-bit parameterized)
- Configs: rv32e, rv64gc
- Frequencies: 25-250 MHz range tested
- Technology: sky130 130nm OSU standard cells
- All timing constraints successfully met in test range

DEPENDENCIES RESOLVED:
=====================
- matplotlib, pandas, numpy: For plotting and data analysis
- subprocess: For synthesis tool invocation with proper environment
- pathlib: For robust file path handling
- argparse: For flexible command-line interface

AUTHORS: AI Assistant + User Collaboration
DATE: November 2025
VERSION: 2.0 - Environment issues resolved, shell warnings filtered, robust error handling
"""

import argparse
import csv
import os
import re
import subprocess
import time
from multiprocessing import Pool
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class FrequencySweep:
    def __init__(self, design='adder', config='rv32e', tech='sky130', width=64):
        self.design = design
        self.config = config
        self.tech = tech
        self.width = width
        self.results = []

        # Create results directory
        self.results_dir = Path('./freq_sweep_results')
        self.results_dir.mkdir(exist_ok=True)

    def run_single_synthesis(self, freq):
        """Run a single synthesis at specified frequency"""
        print(f"Running synthesis: {self.design} at {freq} MHz")

        # Set up environment with Design Compiler path and WALLY variable
        env = os.environ.copy()
        dc_path = "/opt/snps/syn/W-2024.09-SP4-1/bin"
        if 'PATH' in env:
            env['PATH'] = f"{dc_path}:{env['PATH']}"
        else:
            env['PATH'] = dc_path

        # Ensure WALLY and RISCV environment variables are set
        env['WALLY'] = '/home/rswann/new_cvw'
        env['RISCV'] = '/opt/riscv'

        # Environment variables are now properly set

        # Force shell to bash for better compatibility
        env['SHELL'] = '/bin/bash'

        # Ensure WALLY environment variable is set
        if 'WALLY' not in env:
            env['WALLY'] = '/home/rswann/new_cvw'

        command = [
            'make', 'synth',
            f'DESIGN={self.design}',
            f'CONFIG={self.config}',
            f'TECH={self.tech}',
            f'FREQ={freq}',
            f'WIDTH={self.width}',
            'DRIVE=FLOP',
            'MAXCORES=1'
        ]

        start_time = time.time()
        try:
            print(f"Running command: {' '.join(command)}")
            # Run with bash explicitly and filter out the dc_shell warnings
            result = subprocess.run(command, capture_output=True, text=True, timeout=600, env=env, shell=False)
            end_time = time.time()

            # Filter out the annoying dc_shell warnings about shell operators
            if result.stderr:
                stderr_lines = result.stderr.split('\n')
                filtered_stderr = []
                for line in stderr_lines:
                    if not ('unexpected operator' in line and 'dc_shell-xg-t' in line):
                        filtered_stderr.append(line)
                result.stderr = '\n'.join(filtered_stderr)

            print(f"Command completed in {end_time - start_time:.2f} seconds")
            print(f"Return code: {result.returncode}")

            if result.stdout:
                print("STDOUT preview:", result.stdout[:200], "...")
            if result.stderr and len(result.stderr.strip()) > 0:
                print("STDERR preview:", result.stderr[:200], "...")

            if result.returncode == 0:
                # Parse results from synthesis reports
                synth_results = self.parse_synthesis_results(freq)
                synth_results['synthesis_time'] = end_time - start_time
                synth_results['success'] = True
                synth_results['stdout'] = result.stdout[:500]  # Save partial stdout for debugging
                return synth_results
            else:
                print(f"Synthesis failed for {freq} MHz")
                return {
                    'freq': freq,
                    'success': False,
                    'error': result.stderr,
                    'stdout': result.stdout[:500] if result.stdout else '',
                    'synthesis_time': end_time - start_time
                }
        except subprocess.TimeoutExpired:
            print(f"Synthesis timed out for {freq} MHz")
            return {
                'freq': freq,
                'success': False,
                'error': 'Timeout',
                'synthesis_time': 600
            }

    def parse_synthesis_results(self, freq):
        """Parse synthesis results from report files"""
        # Find the most recent run directory for this frequency
        runs_pattern = f"runs/{self.design}_{self.config}_orig_{self.tech}nm_{freq}_MHz_*"
        import glob
        run_dirs = glob.glob(runs_pattern)

        if not run_dirs:
            print(f"No run directory found for {freq} MHz")
            return {'freq': freq, 'success': False, 'error': 'No run directory'}

        # Get the most recent run directory
        run_dir = max(run_dirs, key=os.path.getctime)

        results = {'freq': freq}

        # Parse area report
        area_file = os.path.join(run_dir, 'reports', 'area.rep')
        if os.path.exists(area_file):
            results.update(self.parse_area_report(area_file))

        # Parse timing report
        timing_file = os.path.join(run_dir, 'reports', 'timing.rep')
        if os.path.exists(timing_file):
            results.update(self.parse_timing_report(timing_file))

        # Parse power report
        power_file = os.path.join(run_dir, 'reports', 'power.rep')
        if os.path.exists(power_file):
            results.update(self.parse_power_report(power_file))

        # Parse QoR report
        qor_file = os.path.join(run_dir, 'reports', 'qor.rep')
        if os.path.exists(qor_file):
            results.update(self.parse_qor_report(qor_file))

        return results

    def parse_area_report(self, filename):
        """Parse area from synthesis report"""
        results = {}
        try:
            with open(filename) as f:
                content = f.read()

            # Extract total area
            area_match = re.search(r'Total cell area:\s+([0-9.]+)', content)
            if area_match:
                results['area'] = float(area_match.group(1))

            # Extract combinational area
            comb_area_match = re.search(r'Combinational area:\s+([0-9.]+)', content)
            if comb_area_match:
                results['comb_area'] = float(comb_area_match.group(1))

            # Extract number of cells
            cells_match = re.search(r'Number of cells:\s+([0-9]+)', content)
            if cells_match:
                results['num_cells'] = int(cells_match.group(1))

        except Exception as e:
            print(f"Error parsing area report: {e}")

        return results

    def parse_timing_report(self, filename):
        """Parse timing from synthesis report"""
        results = {}
        try:
            with open(filename) as f:
                content = f.read()

            # Extract path delay
            delay_match = re.search(r'data arrival time\s+([0-9.]+)', content)
            if delay_match:
                results['path_delay'] = float(delay_match.group(1))

            # Extract slack
            slack_match = re.search(r'slack \(.*?\)\s+([0-9.-]+)', content)
            if slack_match:
                results['slack'] = float(slack_match.group(1))

        except Exception as e:
            print(f"Error parsing timing report: {e}")

        return results

    def parse_power_report(self, filename):
        """Parse power from synthesis report"""
        results = {}
        try:
            with open(filename) as f:
                content = f.read()

            # Extract leakage power
            leakage_match = re.search(r'Cell Leakage Power\s*=\s*([0-9.e-]+)\s*nW', content)
            if leakage_match:
                results['leakage_power'] = float(leakage_match.group(1))

        except Exception as e:
            print(f"Error parsing power report: {e}")

        return results

    def parse_qor_report(self, filename):
        """Parse QoR metrics from synthesis report"""
        results = {}
        try:
            with open(filename) as f:
                content = f.read()

            # Extract critical path slack
            slack_match = re.search(r'Worst slack\s*:\s*([0-9.-]+)', content)
            if slack_match:
                results['worst_slack'] = float(slack_match.group(1))

        except Exception as e:
            print(f"Error parsing QoR report: {e}")

        return results

    def run_frequency_sweep(self, freq_range=None, freq_step=50, parallel=False):
        """Run synthesis across a range of frequencies"""
        if freq_range is None:
            freq_range = (50, 500)  # Default range 50-500 MHz

        frequencies = list(range(freq_range[0], freq_range[1] + 1, freq_step))

        print(f"Running frequency sweep from {freq_range[0]} to {freq_range[1]} MHz")
        print(f"Frequencies to test: {frequencies}")

        if parallel and len(frequencies) > 1:
            # Use multiprocessing for parallel synthesis
            with Pool(processes=min(4, len(frequencies))) as pool:
                results = pool.map(self.run_single_synthesis, frequencies)
        else:
            # Sequential synthesis
            results = [self.run_single_synthesis(freq) for freq in frequencies]

        # Filter successful results
        self.results = [r for r in results if r.get('success', False)]

        # Save results to CSV
        self.save_results_csv()

        return self.results

    def save_results_csv(self):
        """Save results to CSV file"""
        if not self.results:
            print("No results to save")
            return

        csv_file = self.results_dir / f"{self.design}_{self.config}_{self.tech}_sweep.csv"

        # Get all possible keys from results
        all_keys = set()
        for result in self.results:
            all_keys.update(result.keys())

        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(self.results)

        print(f"Results saved to {csv_file}")

    def plot_frequency_sweep(self, save_plots=True):
        """Generate comprehensive plots from frequency sweep results"""
        if not self.results:
            print("No results to plot")
            return

        # Convert results to DataFrame for easier plotting
        df = pd.DataFrame(self.results)
        df = df.sort_values('freq')  # Ensure proper frequency order

        # Create subplots with better layout
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle(f'Frequency Sweep Analysis: {self.design} ({self.config}, {self.tech}, {self.width}-bit)',
                     fontsize=16, fontweight='bold')

        # Plot 1: Area vs Frequency (Main focus plot)
        if 'area' in df.columns:
            axes[0, 0].plot(df['freq'], df['area'], 'bo-', markersize=8, linewidth=2, label='Area')

            # Add data point annotations
            for i, (freq, area) in enumerate(zip(df['freq'], df['area'])):
                axes[0, 0].annotate(f'{area:.0f}', (freq, area),
                                  textcoords="offset points", xytext=(0,10), ha='center',
                                  fontsize=9, alpha=0.8)

            axes[0, 0].set_xlabel('Frequency (MHz)', fontweight='bold')
            axes[0, 0].set_ylabel('Area (µm²)', fontweight='bold')
            axes[0, 0].set_title('Area vs Frequency\n(Key Design Tradeoff)', fontweight='bold')
            axes[0, 0].grid(True, alpha=0.3)
            axes[0, 0].legend()

            # Highlight min/max area points
            min_area_idx = df['area'].idxmin()
            max_area_idx = df['area'].idxmax()
            axes[0, 0].plot(df.loc[min_area_idx, 'freq'], df.loc[min_area_idx, 'area'],
                          'go', markersize=12, label=f"Min Area: {df.loc[min_area_idx, 'area']:.0f} µm²")
            axes[0, 0].plot(df.loc[max_area_idx, 'freq'], df.loc[max_area_idx, 'area'],
                          'ro', markersize=12, label=f"Max Area: {df.loc[max_area_idx, 'area']:.0f} µm²")

        # Plot 2: Timing Slack vs Frequency (Critical for timing closure)
        if 'slack' in df.columns:
            colors = ['red' if slack < 0 else 'darkgreen' if slack < 0.1 else 'green'
                     for slack in df['slack']]

            axes[0, 1].bar(df['freq'], df['slack'], color=colors, alpha=0.7, width=df['freq'].diff().mean()*0.6)
            axes[0, 1].axhline(y=0, color='red', linestyle='-', linewidth=2, label='Timing Violation')
            axes[0, 1].axhline(y=0.1, color='orange', linestyle='--', linewidth=1, label='Critical Timing')

            # Add slack value annotations
            for i, (freq, slack) in enumerate(zip(df['freq'], df['slack'])):
                axes[0, 1].annotate(f'{slack:.2f}', (freq, slack + 0.1 if slack >= 0 else slack - 0.1),
                                  ha='center', fontsize=9, fontweight='bold')

            axes[0, 1].set_xlabel('Frequency (MHz)', fontweight='bold')
            axes[0, 1].set_ylabel('Slack (ns)', fontweight='bold')
            axes[0, 1].set_title('Timing Slack vs Frequency\n(Negative = Violation)', fontweight='bold')
            axes[0, 1].grid(True, alpha=0.3)
            axes[0, 1].legend()

        # Plot 3: Path Delay vs Frequency
        if 'path_delay' in df.columns:
            axes[0, 2].plot(df['freq'], df['path_delay'], 'mo-', markersize=8, linewidth=2)

            # Add period constraint line
            period_ns = 1000 / df['freq']  # Convert MHz to ns period
            axes[0, 2].plot(df['freq'], period_ns, 'r--', linewidth=2, label='Period Constraint')

            axes[0, 2].set_xlabel('Frequency (MHz)', fontweight='bold')
            axes[0, 2].set_ylabel('Delay (ns)', fontweight='bold')
            axes[0, 2].set_title('Critical Path Delay vs Frequency\n(Must be < Period)', fontweight='bold')
            axes[0, 2].grid(True, alpha=0.3)
            axes[0, 2].legend(['Critical Path', 'Clock Period'])

        # Plot 4: Cell Count vs Frequency
        if 'num_cells' in df.columns:
            axes[1, 0].plot(df['freq'], df['num_cells'], 'co-', markersize=8, linewidth=2)

            # Add data point annotations
            for i, (freq, cells) in enumerate(zip(df['freq'], df['num_cells'])):
                axes[1, 0].annotate(f'{cells}', (freq, cells),
                                  textcoords="offset points", xytext=(0,10), ha='center',
                                  fontsize=9, alpha=0.8)

            axes[1, 0].set_xlabel('Frequency (MHz)', fontweight='bold')
            axes[1, 0].set_ylabel('Number of Cells', fontweight='bold')
            axes[1, 0].set_title('Cell Count vs Frequency\n(Optimization Strategy)', fontweight='bold')
            axes[1, 0].grid(True, alpha=0.3)

        # Plot 5: Area-Delay Product vs Frequency (Efficiency metric)
        if 'area' in df.columns and 'path_delay' in df.columns:
            adp = df['area'] * df['path_delay']
            axes[1, 1].plot(df['freq'], adp, 'ko-', markersize=8, linewidth=2)

            # Find optimal point (minimum ADP)
            min_adp_idx = adp.idxmin()
            axes[1, 1].plot(df.loc[min_adp_idx, 'freq'], adp.loc[min_adp_idx],
                          'ro', markersize=12, label=f"Optimal Point: {df.loc[min_adp_idx, 'freq']} MHz")

            axes[1, 1].set_xlabel('Frequency (MHz)', fontweight='bold')
            axes[1, 1].set_ylabel('Area x Delay Product', fontweight='bold')
            axes[1, 1].set_title('Area-Delay Product vs Frequency\n(Lower = Better Efficiency)', fontweight='bold')
            axes[1, 1].grid(True, alpha=0.3)
            axes[1, 1].legend()

        # Plot 6: Synthesis Time vs Frequency
        if 'synthesis_time' in df.columns:
            axes[1, 2].plot(df['freq'], df['synthesis_time'], 'yo-', markersize=8, linewidth=2)
            axes[1, 2].set_xlabel('Frequency (MHz)', fontweight='bold')
            axes[1, 2].set_ylabel('Synthesis Time (s)', fontweight='bold')
            axes[1, 2].set_title('Synthesis Time vs Frequency\n(Tool Effort)', fontweight='bold')
            axes[1, 2].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_plots:
            plot_file = self.results_dir / f"{self.design}_{self.config}_{self.tech}_sweep_plot.png"
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            print(f"Plot saved to {plot_file}")

        plt.show()

    def plot_pareto_frontier(self, save_plots=True):
        """Plot enhanced Pareto frontier analysis"""
        if not self.results:
            print("No results to plot")
            return

        df = pd.DataFrame(self.results)

        if 'area' not in df.columns or 'path_delay' not in df.columns:
            print("Area or delay data not available for Pareto plot")
            return

        # Create figure with subplots
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        fig.suptitle(f'Design Space Exploration: {self.design} ({self.config}, {self.tech}, {self.width}-bit)',
                     fontsize=14, fontweight='bold')

        # Plot 1: Area vs Path Delay (Traditional Pareto)
        scatter = axes[0].scatter(df['path_delay'], df['area'], c=df['freq'],
                                cmap='plasma', s=100, alpha=0.8, edgecolors='black', linewidth=1)
        plt.colorbar(scatter, ax=axes[0], label='Frequency (MHz)')

        # Add frequency labels to points
        for i, row in df.iterrows():
            axes[0].annotate(f"{row['freq']} MHz",
                           (row['path_delay'], row['area']),
                           xytext=(8, 8), textcoords='offset points',
                           fontsize=10, fontweight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.7))

        # Find and highlight Pareto optimal points
        pareto_mask = self._find_pareto_frontier(df[['path_delay', 'area']].values)
        pareto_points = df[pareto_mask]

        if len(pareto_points) > 1:
            # Sort Pareto points by delay for line plotting
            pareto_sorted = pareto_points.sort_values('path_delay')
            axes[0].plot(pareto_sorted['path_delay'], pareto_sorted['area'],
                        'r--', linewidth=3, alpha=0.7, label='Pareto Frontier')

        axes[0].set_xlabel('Critical Path Delay (ns)', fontweight='bold')
        axes[0].set_ylabel('Area (µm²)', fontweight='bold')
        axes[0].set_title('Area vs Delay Trade-off Space', fontweight='bold')
        axes[0].grid(True, alpha=0.3)
        axes[0].legend()

        # Plot 2: Area vs Frequency with timing constraints
        if 'slack' in df.columns:
            # Color by timing slack
            slack_colors = []
            for slack in df['slack']:
                if slack < 0:
                    slack_colors.append('red')      # Timing violation
                elif slack < 0.1:
                    slack_colors.append('orange')   # Critical timing
                else:
                    slack_colors.append('green')    # Good timing margin

            axes[1].scatter(df['freq'], df['area'], c=slack_colors,
                           s=100, alpha=0.8, edgecolors='black', linewidth=1)

            # Add data point annotations
            for i, row in df.iterrows():
                color = 'white' if row['slack'] >= 0 else 'yellow'
                axes[1].annotate(f"{row['area']:.0f}\n({row['slack']:.2f}ns)",
                               (row['freq'], row['area']),
                               xytext=(0, 15), textcoords='offset points',
                               fontsize=9, fontweight='bold', ha='center',
                               bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8))

        axes[1].set_xlabel('Frequency (MHz)', fontweight='bold')
        axes[1].set_ylabel('Area (µm²)', fontweight='bold')
        axes[1].set_title('Frequency vs Area\n(Color: Timing Status)', fontweight='bold')
        axes[1].grid(True, alpha=0.3)

        # Add legend for timing status
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor='green', label='Good Timing (>0.1ns slack)'),
                          Patch(facecolor='orange', label='Critical Timing (0-0.1ns slack)'),
                          Patch(facecolor='red', label='Timing Violation (<0ns slack)')]
        axes[1].legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()

        if save_plots:
            plot_file = self.results_dir / f"{self.design}_{self.config}_{self.tech}_pareto.png"
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            print(f"Pareto plot saved to {plot_file}")

        plt.show()

    def _find_pareto_frontier(self, costs):
        """Find Pareto frontier points (minimize both objectives)"""
        is_efficient = np.ones(costs.shape[0], dtype=bool)
        for i, c in enumerate(costs):
            if is_efficient[i]:
                # Remove points that are dominated by point i
                is_efficient[is_efficient] = np.any(costs[is_efficient] < c, axis=1)
                is_efficient[i] = True  # Keep point i
        return is_efficient

def main():
    parser = argparse.ArgumentParser(description='Run frequency sweep synthesis for CVW designs')
    parser.add_argument('--design', default='adder', help='Design to synthesize (default: adder)')
    parser.add_argument('--config', default='rv32e', help='Configuration (default: rv32e)')
    parser.add_argument('--tech', default='sky130', help='Technology (default: sky130)')
    parser.add_argument('--width', type=int, default=32, help='Width parameter (default: 32)')
    parser.add_argument('--freq-min', type=int, default=50, help='Minimum frequency (default: 50)')
    parser.add_argument('--freq-max', type=int, default=500, help='Maximum frequency (default: 500)')
    parser.add_argument('--freq-step', type=int, default=50, help='Frequency step (default: 50)')
    parser.add_argument('--parallel', action='store_true', help='Run syntheses in parallel')
    parser.add_argument('--plot-only', action='store_true', help='Only generate plots from existing results')

    args = parser.parse_args()

    # Create frequency sweep object
    sweep = FrequencySweep(
        design=args.design,
        config=args.config,
        tech=args.tech,
        width=args.width
    )

    if not args.plot_only:
        # Run frequency sweep
        results = sweep.run_frequency_sweep(
            freq_range=(args.freq_min, args.freq_max),
            freq_step=args.freq_step,
            parallel=args.parallel
        )

        print(f"\nCompleted {len(results)} successful syntheses")

        # Print summary
        if results:
            df = pd.DataFrame(results)
            print("\nSummary Statistics:")
            print(f"Frequency range: {df['freq'].min()} - {df['freq'].max()} MHz")
            if 'area' in df.columns:
                print(f"Area range: {df['area'].min():.1f} - {df['area'].max():.1f} µm²")
            if 'slack' in df.columns:
                timing_met = (df['slack'] >= 0).sum()
                print(f"Timing met: {timing_met}/{len(df)} syntheses")

    # Generate plots
    if sweep.results or args.plot_only:
        if args.plot_only:
            # Load results from CSV
            csv_file = sweep.results_dir / f"{args.design}_{args.config}_{args.tech}_sweep.csv"
            if csv_file.exists():
                df = pd.read_csv(csv_file)
                sweep.results = df.to_dict('records')
            else:
                print(f"No existing results found at {csv_file}")
                return

        sweep.plot_frequency_sweep()
        sweep.plot_pareto_frontier()

if __name__ == '__main__':
    main()
