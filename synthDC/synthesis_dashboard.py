#!/usr/bin/env python3
"""
Wally Synthesis Dashboard
========================

Elegant analysis and visualization of synthesis results for publications.
Automatically discovers and analyzes self-documenting result files.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass
class ResultFile:
    """Metadata about a results file"""
    path: Path
    timestamp: datetime
    run_type: str
    configurations: list[str]
    technologies: list[str]
    frequency_range: tuple[int, int]
    success_rate: float
    total_runs: int


@dataclass
class SynthesisMetrics:
    """Synthesis metrics for analysis"""
    config: str
    technology: str
    frequency_mhz: int
    feature_mode: str
    area_um2: Optional[float]
    slack_ns: Optional[float]
    power_mw: Optional[float]
    cell_count: Optional[int]
    synthesis_time_s: Optional[float]
    success: bool
    timestamp: datetime
    run_type: str


class WallySynthesisDashboard:
    """Analysis and visualization dashboard for Wally synthesis results"""

    def __init__(self, results_dir: Optional[Path] = None):
        self.results_dir = results_dir or Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)

        # Setup publication-quality plotting style
        self._setup_plot_style()

        # Cache for loaded data
        self._results_cache: dict[Path, dict] = {}

        # Cache for sweep folders
        self._sweep_cache: dict[str, dict] = {}

    def _setup_plot_style(self):
        """Configure matplotlib for publication-quality plots"""
        # Use a clean, professional style
        plt.style.use('default')

        # Set font sizes for papers
        plt.rcParams.update({
            'font.size': 12,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 16,
            'font.family': 'serif',
            'font.serif': ['Times New Roman', 'DejaVu Serif'],
            'mathtext.fontset': 'stix',
            'figure.dpi': 300,
            'savefig.dpi': 300,
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.1,
            'axes.grid': True,
            'grid.alpha': 0.3,
            'axes.axisbelow': True
        })

        # Set color palette for different configurations
        self.config_colors = {
            'rv32e': '#1f77b4',    # Blue
            'rv32i': '#ff7f0e',    # Orange
            'rv32imc': '#2ca02c',  # Green
            'rv32gc': '#d62728',   # Red
            'rv64i': '#9467bd',    # Purple
            'rv64gc': '#8c564b'    # Brown
        }

        self.tech_markers = {
            'sky130': 'o',
            'sky90': 's',
            'tsmc28': '^',
            'tsmc28psyn': 'D'
        }

    def discover_result_files(self, days_back: int = 30) -> list[ResultFile]:
        """Discover all result files in the specified time window"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        result_files = []

        for json_file in self.results_dir.rglob("*.json"):
            try:
                # Parse filename to extract metadata
                file_info = self._parse_result_filename(json_file)
                if file_info and file_info.timestamp >= cutoff_date:
                    result_files.append(file_info)
            except Exception as e:
                print(f"Warning: Could not parse {json_file.name}: {e}")

        # Sort by timestamp (newest first)
        result_files.sort(key=lambda x: x.timestamp, reverse=True)
        return result_files

    def _parse_result_filename(self, file_path: Path) -> Optional[ResultFile]:
        """Parse metadata from self-documenting filename"""
        try:
            # Load the file to get accurate metadata
            with open(file_path) as f:
                data = json.load(f)

            metadata = data.get('metadata', {})
            summary = data.get('summary', {})

            # Parse timestamp from metadata or file
            if 'iso_timestamp' in metadata:
                timestamp = datetime.fromisoformat(metadata['iso_timestamp'])
            else:
                # Fallback to file modification time
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)

            # Extract configurations and technologies
            results = data.get('results', [])
            configurations = list(set(r['config']['config'] for r in results))
            technologies = list(set(r['config']['technology'] for r in results))

            # Get frequency range
            frequencies = [r['config']['frequency_mhz'] for r in results]
            freq_range = (min(frequencies), max(frequencies)) if frequencies else (0, 0)

            return ResultFile(
                path=file_path,
                timestamp=timestamp,
                run_type=metadata.get('run_type', 'unknown'),
                configurations=configurations,
                technologies=technologies,
                frequency_range=freq_range,
                success_rate=summary.get('success_rate', 0.0),
                total_runs=summary.get('total_runs', 0)
            )

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def discover_sweep_folders(self, days_back: int = 30) -> list[dict]:
        """Discover sweep folders for dropdown selection"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        sweep_folders = []

        for date_dir in self.results_dir.glob("*"):
            if not date_dir.is_dir():
                continue

            # Check if it's a date directory
            try:
                date_obj = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if date_obj < cutoff_date:
                    continue
            except ValueError:
                continue

            sweeps_dir = date_dir / "sweeps"
            if not sweeps_dir.exists():
                continue

            for sweep_dir in sweeps_dir.iterdir():
                if not sweep_dir.is_dir():
                    continue

                sweep_info_file = sweep_dir / "sweep_info.json"
                if not sweep_info_file.exists():
                    continue

                try:
                    with open(sweep_info_file) as f:
                        sweep_info = json.load(f)

                    # Find the main results file
                    results_file = None
                    for json_file in sweep_dir.glob("*.json"):
                        if json_file.name != "sweep_info.json":
                            results_file = json_file
                            break

                    if results_file:
                        sweep_folders.append({
                            'path': str(sweep_dir),
                            'name': sweep_dir.name,
                            'display_name': f"{date_dir.name} - {sweep_info['sweep_type']} ({sweep_info['total_runs']} runs)",
                            'sweep_type': sweep_info['sweep_type'],
                            'date': date_dir.name,
                            'total_runs': sweep_info['total_runs'],
                            'successful_runs': sweep_info['successful_runs'],
                            'configurations': sweep_info['configurations'],
                            'results_file': str(results_file),
                            'timestamp': sweep_info.get('timestamp', ''),
                            'machine': sweep_info.get('machine', 'unknown')
                        })

                except Exception as e:
                    print(f"Error reading sweep info from {sweep_dir}: {e}")

        # Sort by date and time (newest first)
        sweep_folders.sort(key=lambda x: (x['date'], x['timestamp']), reverse=True)
        return sweep_folders

    def load_sweep_data(self, sweep_folder_path: str) -> tuple[list[SynthesisMetrics], dict]:
        """Load data from a specific sweep folder"""
        sweep_dir = Path(sweep_folder_path)

        # Load sweep metadata
        sweep_info_file = sweep_dir / "sweep_info.json"
        if not sweep_info_file.exists():
            raise ValueError(f"No sweep_info.json found in {sweep_folder_path}")

        with open(sweep_info_file) as f:
            sweep_metadata = json.load(f)

        # Find and load the main results file
        results_file = None
        for json_file in sweep_dir.glob("*.json"):
            if json_file.name != "sweep_info.json":
                results_file = json_file
                break

        if not results_file:
            raise ValueError(f"No results file found in {sweep_folder_path}")

        # Load the results using existing method
        result_file_info = ResultFile(
            path=results_file,
            timestamp=datetime.now(),  # Will be overridden from file
            run_type=sweep_metadata['sweep_type'],
            configurations=sweep_metadata['configurations'],
            technologies=['sky130'],  # Will be overridden from file
            frequency_range=(sweep_metadata['frequency_range']['min'],
                           sweep_metadata['frequency_range']['max']),
            success_rate=sweep_metadata['successful_runs'] / sweep_metadata['total_runs'],
            total_runs=sweep_metadata['total_runs']
        )

        metrics = self.load_metrics([result_file_info])
        return metrics, sweep_metadata

    def load_metrics(self, result_files: Optional[list[ResultFile]] = None) -> list[SynthesisMetrics]:
        """Load synthesis metrics from result files"""
        if result_files is None:
            result_files = self.discover_result_files()

        all_metrics = []

        for file_info in result_files:
            try:
                # Use cache if available
                if file_info.path in self._results_cache:
                    data = self._results_cache[file_info.path]
                else:
                    with open(file_info.path) as f:
                        data = json.load(f)
                    self._results_cache[file_info.path] = data

                # Extract metrics from each result
                for result in data.get('results', []):
                    config = result['config']
                    metrics = result['metrics']

                    metric = SynthesisMetrics(
                        config=config['config'],
                        technology=config['technology'],
                        frequency_mhz=config['frequency_mhz'],
                        feature_mode=config['feature_mode'],
                        area_um2=metrics.get('area_um2'),
                        slack_ns=metrics.get('slack_ns'),
                        power_mw=metrics.get('power_mw'),
                        cell_count=metrics.get('cell_count'),
                        synthesis_time_s=metrics.get('synthesis_time_s'),
                        success=result['success'],
                        timestamp=file_info.timestamp,
                        run_type=file_info.run_type
                    )
                    all_metrics.append(metric)

            except Exception as e:
                print(f"Error loading metrics from {file_info.path}: {e}")

        return all_metrics

    def generate_summary_report(self, days_back: int = 7) -> str:
        """Generate a text summary of recent synthesis activity"""
        result_files = self.discover_result_files(days_back)
        metrics = self.load_metrics(result_files)

        # Filter to successful runs only for statistics
        successful_metrics = [m for m in metrics if m.success]

        report = []
        report.append("=" * 60)
        report.append("WALLY SYNTHESIS DASHBOARD - SUMMARY REPORT")
        report.append("=" * 60)
        report.append(f"Analysis Period: Last {days_back} days")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Overall statistics
        report.append("📊 OVERALL STATISTICS")
        report.append("-" * 25)
        report.append(f"Total synthesis runs: {len(metrics)}")
        report.append(f"Successful runs: {len(successful_metrics)} ({len(successful_metrics)/len(metrics)*100:.1f}%)")
        report.append(f"Result files analyzed: {len(result_files)}")
        report.append("")

        if successful_metrics:
            # Configuration breakdown
            config_counts = {}
            for m in successful_metrics:
                config_counts[m.config] = config_counts.get(m.config, 0) + 1

            report.append("🏗️ CONFIGURATION BREAKDOWN")
            report.append("-" * 27)
            for config, count in sorted(config_counts.items()):
                report.append(f"{config:8}: {count:4d} runs")
            report.append("")

            # Technology breakdown
            tech_counts = {}
            for m in successful_metrics:
                tech_counts[m.technology] = tech_counts.get(m.technology, 0) + 1

            report.append("🔬 TECHNOLOGY BREAKDOWN")
            report.append("-" * 24)
            for tech, count in sorted(tech_counts.items()):
                report.append(f"{tech:12}: {count:4d} runs")
            report.append("")

            # Area statistics
            areas = [m.area_um2 for m in successful_metrics if m.area_um2 is not None]
            if areas:
                report.append("📐 AREA STATISTICS (µm²)")
                report.append("-" * 23)
                report.append(f"Minimum: {min(areas):>12,.1f}")
                report.append(f"Maximum: {max(areas):>12,.1f}")
                report.append(f"Average: {sum(areas)/len(areas):>12,.1f}")
                report.append(f"Range:   {max(areas)-min(areas):>12,.1f}")
                report.append("")

            # Timing statistics
            slacks = [m.slack_ns for m in successful_metrics if m.slack_ns is not None]
            if slacks:
                violations = sum(1 for s in slacks if s < 0)
                report.append("⏱️ TIMING STATISTICS (ns)")
                report.append("-" * 24)
                report.append(f"Best slack:    {max(slacks):>8.3f}")
                report.append(f"Worst slack:   {min(slacks):>8.3f}")
                report.append(f"Average slack: {sum(slacks)/len(slacks):>8.3f}")
                report.append(f"Violations:    {violations:>8d} ({violations/len(slacks)*100:.1f}%)")
                report.append("")

        # Recent activity
        if result_files:
            report.append("📅 RECENT ACTIVITY")
            report.append("-" * 17)
            for file_info in result_files[:10]:  # Show last 10 files
                date_str = file_info.timestamp.strftime("%m/%d %H:%M")
                configs_str = "+".join(file_info.configurations[:3])
                if len(file_info.configurations) > 3:
                    configs_str += f"+{len(file_info.configurations)-3}more"
                report.append(f"{date_str} | {file_info.run_type:12} | {configs_str:15} | {file_info.success_rate:.1%}")
            report.append("")

        report.append("=" * 60)
        return "\n".join(report)

    def plot_area_vs_frequency(self, config_filter: Optional[list[str]] = None,
                              tech_filter: Optional[list[str]] = None,
                              save_path: Optional[Path] = None) -> plt.Figure:
        """Create publication-quality area vs frequency plot"""
        metrics = self.load_metrics()

        # Filter data
        if config_filter:
            metrics = [m for m in metrics if m.config in config_filter]
        if tech_filter:
            metrics = [m for m in metrics if m.technology in tech_filter]

        # Filter to successful runs with area data
        metrics = [m for m in metrics if m.success and m.area_um2 is not None]

        if not metrics:
            print("No valid data for area vs frequency plot")
            return None

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Group by configuration
        for config in set(m.config for m in metrics):
            config_metrics = [m for m in metrics if m.config == config]

            frequencies = [m.frequency_mhz for m in config_metrics]
            areas = [m.area_um2 for m in config_metrics]

            # Plot with configuration-specific color
            color = self.config_colors.get(config, 'gray')
            ax.scatter(frequencies, areas, label=config, color=color, alpha=0.7, s=50)

        ax.set_xlabel('Frequency (MHz)')
        ax.set_ylabel('Area (µm²)')
        ax.set_title('Area vs. Operating Frequency')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)

        # Format y-axis with comma separators
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Area vs Frequency plot saved to {save_path}")

        return fig

    def plot_timing_analysis(self, config_filter: Optional[list[str]] = None,
                           save_path: Optional[Path] = None) -> plt.Figure:
        """Create timing slack analysis plot"""
        metrics = self.load_metrics()

        if config_filter:
            metrics = [m for m in metrics if m.config in config_filter]

        # Filter to successful runs with timing data
        metrics = [m for m in metrics if m.success and m.slack_ns is not None]

        if not metrics:
            print("No valid timing data for analysis")
            return None

        # Create subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Slack histogram
        slacks = [m.slack_ns for m in metrics]
        ax1.hist(slacks, bins=30, alpha=0.7, edgecolor='black', linewidth=0.5)
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Timing Failure')
        ax1.set_xlabel('Slack (ns)')
        ax1.set_ylabel('Count')
        ax1.set_title('Timing Slack Distribution')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Slack vs frequency by configuration
        for config in set(m.config for m in metrics):
            config_metrics = [m for m in metrics if m.config == config]
            frequencies = [m.frequency_mhz for m in config_metrics]
            config_slacks = [m.slack_ns for m in config_metrics]

            color = self.config_colors.get(config, 'gray')
            ax2.scatter(frequencies, config_slacks, label=config, color=color, alpha=0.7, s=50)

        ax2.axhline(y=0, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax2.set_xlabel('Frequency (MHz)')
        ax2.set_ylabel('Slack (ns)')
        ax2.set_title('Timing Slack vs. Frequency')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Timing analysis plot saved to {save_path}")

        return fig

    def plot_config_comparison(self, metric: str = 'area_um2', technology: str = 'sky130',
                              save_path: Optional[Path] = None) -> plt.Figure:
        """Create configuration comparison bar chart"""
        metrics = self.load_metrics()

        # Filter to specific technology and successful runs
        metrics = [m for m in metrics if m.technology == technology and m.success]

        if not metrics:
            print(f"No valid data for {technology} technology")
            return None

        # Group by configuration and calculate statistics
        config_data = {}
        for m in metrics:
            if m.config not in config_data:
                config_data[m.config] = []

            value = getattr(m, metric)
            if value is not None:
                config_data[m.config].append(value)

        # Calculate means and error bars (std dev)
        configs = []
        means = []
        stds = []

        for config, values in config_data.items():
            if values:  # Only include configs with data
                configs.append(config)
                means.append(np.mean(values))
                stds.append(np.std(values) if len(values) > 1 else 0)

        if not configs:
            print(f"No valid {metric} data for comparison")
            return None

        # Create bar chart
        fig, ax = plt.subplots(figsize=(10, 6))

        colors = [self.config_colors.get(config, 'gray') for config in configs]
        bars = ax.bar(configs, means, yerr=stds, color=colors, alpha=0.8,
                     capsize=5, error_kw={'linewidth': 2})

        # Formatting
        metric_labels = {
            'area_um2': 'Area (µm²)',
            'slack_ns': 'Slack (ns)',
            'power_mw': 'Power (mW)',
            'synthesis_time_s': 'Synthesis Time (s)',
            'cell_count': 'Cell Count'
        }

        ax.set_ylabel(metric_labels.get(metric, metric))
        ax.set_title(f'Configuration Comparison - {metric_labels.get(metric, metric)} ({technology})')
        ax.grid(True, alpha=0.3)

        # Add value labels on bars
        for bar, mean, std in zip(bars, means, stds):
            height = bar.get_height()
            if metric == 'area_um2':
                label = f'{mean:,.0f}'
            elif metric in ['slack_ns', 'synthesis_time_s']:
                label = f'{mean:.2f}'
            else:
                label = f'{mean:.0f}'

            ax.text(bar.get_x() + bar.get_width()/2., height + std,
                   label, ha='center', va='bottom', fontweight='bold')

        # Format y-axis
        if metric == 'area_um2':
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Configuration comparison plot saved to {save_path}")

        return fig

    def generate_publication_suite(self, output_dir: Optional[Path] = None,
                                 config_filter: Optional[list[str]] = None) -> list[Path]:
        """Generate complete suite of publication-ready plots"""
        if output_dir is None:
            output_dir = self.results_dir / "plots" / datetime.now().strftime("%Y-%m-%d_%H%M%S")

        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files = []

        print(f"🎨 Generating publication suite in {output_dir}")

        # Area vs Frequency
        fig = self.plot_area_vs_frequency(config_filter=config_filter,
                                        save_path=output_dir / "area_vs_frequency.pdf")
        if fig:
            generated_files.append(output_dir / "area_vs_frequency.pdf")
            plt.close(fig)

        # Timing Analysis
        fig = self.plot_timing_analysis(config_filter=config_filter,
                                      save_path=output_dir / "timing_analysis.pdf")
        if fig:
            generated_files.append(output_dir / "timing_analysis.pdf")
            plt.close(fig)

        # Configuration comparisons for each technology
        metrics = self.load_metrics()
        technologies = set(m.technology for m in metrics if m.success)

        for tech in technologies:
            for metric in ['area_um2', 'slack_ns', 'synthesis_time_s']:
                fig = self.plot_config_comparison(metric=metric, technology=tech,
                                                save_path=output_dir / f"config_comparison_{tech}_{metric}.pdf")
                if fig:
                    generated_files.append(output_dir / f"config_comparison_{tech}_{metric}.pdf")
                    plt.close(fig)

        # Generate summary report
        report_path = output_dir / "summary_report.txt"
        with open(report_path, 'w') as f:
            f.write(self.generate_summary_report(days_back=30))
        generated_files.append(report_path)

        print(f"✅ Generated {len(generated_files)} files for publication")
        return generated_files

    def export_data_table(self, output_path: Optional[Path] = None,
                         file_format: str = 'csv') -> Path:
        """Export synthesis data as table for external analysis"""
        metrics = self.load_metrics()

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.results_dir / f"synthesis_data_{timestamp}.{file_format}"

        # Convert to pandas DataFrame
        data = []
        for m in metrics:
            data.append({
                'timestamp': m.timestamp.isoformat(),
                'config': m.config,
                'technology': m.technology,
                'frequency_mhz': m.frequency_mhz,
                'feature_mode': m.feature_mode,
                'area_um2': m.area_um2,
                'slack_ns': m.slack_ns,
                'power_mw': m.power_mw,
                'cell_count': m.cell_count,
                'synthesis_time_s': m.synthesis_time_s,
                'success': m.success,
                'run_type': m.run_type
            })

        df = pd.DataFrame(data)

        if format.lower() == 'csv':
            df.to_csv(output_path, index=False)
        elif format.lower() == 'xlsx':
            df.to_excel(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        print(f"📊 Data exported to {output_path}")
        return output_path


if __name__ == '__main__':
    # Quick test
    dashboard = WallySynthesisDashboard()
    print(dashboard.generate_summary_report(days_back=7))
