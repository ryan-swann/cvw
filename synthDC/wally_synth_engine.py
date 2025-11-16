#!/usr/bin/env python3
"""
Wally Synthesis Engine
======================

Complete rewrite of CVW synthesis using pure Python instead of Make/TCL.
Much more maintainable, debuggable, and intuitive than the old system.
"""

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config_manager import ConfigManager


@dataclass
class SynthesisConfig:
    """Configuration for a single synthesis run"""
    design: str = "wallypipelinedcore"
    config: str = "rv64gc"
    frequency_mhz: int = 330
    technology: str = "sky130"
    feature_mode: str = "baseline"
    max_optimization: bool = False
    use_sram: bool = False
    width: int = 32


@dataclass
class SynthesisResult:
    """Results from a synthesis run"""
    config: SynthesisConfig
    success: bool
    area_um2: Optional[float] = None
    slack_ns: Optional[float] = None
    power_mw: Optional[float] = None
    cell_count: Optional[int] = None
    synthesis_time_s: Optional[float] = None
    critical_path_ns: Optional[float] = None
    run_directory: Optional[Path] = None
    error_message: Optional[str] = None


class CVWSynthesisEngine:
    """Wally Synthesis Engine for CVW processor"""

    def __init__(self, base_dir: Optional[Path] = None, verbose: bool = False, machine_config: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.synth_dir = self.base_dir / "synthDC"
        self.verbose = verbose

        # Load machine configuration
        self.config_manager = ConfigManager(self.synth_dir / "configs")
        self.machine_config = self.config_manager.load_config(machine_config)

        if self.verbose:
            print(f"📋 Using configuration: {self.machine_config.name}")
            issues = self.config_manager.validate_config(self.machine_config, verbose=False)
            if issues:
                print(f"⚠️  Configuration issues found: {len(issues)}")
                for issue in issues:
                    print(f"   - {issue}")

        self._setup_environment()

    def _setup_environment(self):
        """Setup CVW and Synopsys environment from machine configuration"""
        # Set environment variables from config
        env_vars = self.machine_config.get_environment_vars()
        for key, value in env_vars.items():
            if key not in ['additional_env']:  # Skip metadata keys
                os.environ[key] = str(value)
                if self.verbose and key in ['WALLY', 'RISCV', 'SYNOPSYS_HOME']:
                    print(f"Set {key}={value}")

        # Add Synopsys tools to PATH
        synopsys_paths = self.machine_config.get_tool_paths('synopsys', 'dc_shell')
        current_path = os.environ.get('PATH', '')

        for syn_path in synopsys_paths:
            if os.path.exists(syn_path) and syn_path not in current_path:
                os.environ['PATH'] = f"{syn_path}:{current_path}"
                if self.verbose:
                    print(f"Added Synopsys tools: {syn_path}")
                break

    def _create_run_directory(self, config: SynthesisConfig) -> Path:
        """Create unique run directory for synthesis"""
        timestamp = time.strftime("%Y-%m-%d-%H-%M")
        git_hash = self._get_git_hash()

        # Create descriptive directory name
        feature_modes = self.machine_config.get_feature_modes()
        mod_name = feature_modes.get(config.feature_mode, 'orig')
        run_name = f"{config.design}_{config.config}_{mod_name}_{config.technology}nm_{config.frequency_mhz}_MHz_{timestamp}_{git_hash}"

        run_dir = self.synth_dir / "runs" / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        for subdir in ['hdl', 'reports', 'mapped', 'unmapped', 'config']:
            (run_dir / subdir).mkdir(exist_ok=True)

        return run_dir

    def _get_git_hash(self) -> str:
        """Get current git hash for run identification"""
        try:
            result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                  capture_output=True, text=True, cwd=self.base_dir)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"

    def _copy_source_files(self, config: SynthesisConfig, run_dir: Path):
        """Copy source files to run directory"""
        hdl_dir = run_dir / "hdl"
        config_dir = run_dir / "config"

        # Copy main CVW source files
        src_files = list((self.base_dir / "src").rglob("*.sv"))
        src_files.append(self.base_dir / "src" / "cvw.sv")

        # Add testbench wrapper
        wrapper_file = self.base_dir / "testbench" / "wallywrapper.sv"
        if wrapper_file.exists():
            src_files.append(wrapper_file)

        for src_file in src_files:
            if src_file.exists():
                shutil.copy2(src_file, hdl_dir)
                if self.verbose:
                    print(f"  Copied {src_file.name}")

        # Check if wrapper is needed and generate it
        design_file = hdl_dir / f"{config.design}.sv"
        if design_file.exists():
            with open(design_file) as f:
                content = f.read()
                if 'cvw_t' in content:
                    self._generate_wrapper(config, hdl_dir)
                    if self.verbose:
                        print(f"  Generated wrapper for {config.design}")

        # Copy configuration files
        config_src = self.base_dir / "config" / config.config
        shared_src = self.base_dir / "config" / "shared"

        if config_src.exists():
            shutil.copy2(config_src / "config.vh", config_dir)
            # Also copy to hdl directory for Design Compiler includes
            shutil.copy2(config_src / "config.vh", hdl_dir)
            if self.verbose:
                print(f"  Copied config for {config.config}")
        if shared_src.exists():
            for shared_file in shared_src.glob("*.vh"):
                shutil.copy2(shared_file, config_dir)
                # Also copy to hdl directory for Design Compiler includes
                shutil.copy2(shared_file, hdl_dir)
                if self.verbose:
                    print(f"  Copied {shared_file.name}")

    def _generate_wrapper(self, config: SynthesisConfig, hdl_dir: Path):
        """Generate wrapper for designs with cvw_t parameters"""
        design_file = hdl_dir / f"{config.design}.sv"

        # Parse the original module to extract interface
        with open(design_file) as f:
            lines = f.readlines()

        module_start = -1
        module_end = -1
        module_name = ""

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('module '):
                module_start = i
                module_name = stripped.split()[1].split('(')[0]
                break

        if module_start == -1:
            return  # No module found

        # Find end of module header
        for i in range(module_start, len(lines)):
            if lines[i].strip().endswith(');'):
                module_end = i
                break

        if module_end == -1:
            return  # No module end found

        # Generate wrapper content
        wrapper_content = [
            "import cvw::*;\n",
            '`include "config.vh"\n',
            '`include "parameter-defs.vh"\n',
            f"module {module_name}wrapper (\n"
        ]

        # Copy module interface (skip the module line with parameters)
        for i in range(module_start + 1, module_end + 1):
            line = lines[i]
            # Skip parameter section
            if '#(parameter' in line or 'cvw_t P)' in line:
                continue
            wrapper_content.append(line)

        # Add instantiation
        wrapper_content.append(f"\t{module_name} #(P) dut(.*);\n")
        wrapper_content.append("endmodule\n")

        # Write wrapper file
        wrapper_file = hdl_dir / f"{module_name}wrapper.sv"
        with open(wrapper_file, 'w') as f:
            f.writelines(wrapper_content)

    def _generate_synthesis_script(self, config: SynthesisConfig, run_dir: Path) -> Path:
        """Generate pure Python synthesis script (no TCL)"""
        script_content = self._build_dc_tcl_script(config, run_dir)
        script_path = run_dir / "synthesis.tcl"

        with open(script_path, 'w') as f:
            f.write(script_content)

        return script_path

    def _build_dc_tcl_script(self, config: SynthesisConfig, run_dir: Path) -> str:
        """Build comprehensive TCL script for Design Compiler"""
        tech = self.machine_config.get_technology_config(config.technology)
        if not tech:
            raise RuntimeError(f"Technology {config.technology} not configured for machine {self.machine_config.name}")

        period_ns = 1000 / config.frequency_mhz  # Convert MHz to ns period

        # Get compile options
        compile_mode = 'max_optimization' if config.max_optimization else 'standard'
        compile_opts = self.machine_config.get_compile_options(compile_mode)

        # Get constraints from config
        constraints = tech.get('constraints', {})
        operating_conditions = tech.get('operating_conditions', {})

        script = f'''
# Wally Synthesis Engine - Generated TCL Script
# Configuration: {config.config} @ {config.frequency_mhz}MHz on {config.technology}
# Machine: {self.machine_config.name}
# Run Directory: {run_dir}

# Setup basic variables
set my_design "{config.design}"
set my_toplevel "{config.design}wrapper"
set my_clock_pin "clk"
set my_period {period_ns:.3f}
set my_uncertainty {constraints.get('clock_uncertainty', 0.1)}
set outputDir "{run_dir}"
set hdl_src "{run_dir}/hdl"

# Library setup
set target_library "{tech['target_lib']}"
set link_library "{tech['link_lib']}"
set symbol_library {{}}

# Search paths
set search_path [list . $hdl_src {tech['lib_path']}]

# Set operating conditions
set_operating_conditions -library {operating_conditions.get('library', tech['lib_name'])}

# Read and elaborate design
# Read cvw.sv first (contains package definitions)
set cvw_pkg "$hdl_src/cvw.sv"
if {{[file exists $cvw_pkg]}} {{
    # Start with cvw.sv, then add other files (excluding cvw.sv)
    set verilog_files [list $cvw_pkg]
    set other_files [glob -nocomplain $hdl_src/*.sv]
    set filtered_files {{}}
    foreach file $other_files {{
        if {{$file != $cvw_pkg}} {{
            lappend filtered_files $file
        }}
    }}
    set verilog_files [concat $verilog_files [lsort $filtered_files]]
}} else {{
    set verilog_files [glob $hdl_src/*.sv]
}}
define_design_lib WORK -path $outputDir/WORK
analyze -f sverilog -lib WORK $verilog_files

# Elaborate with parameters
elaborate $my_toplevel -lib WORK
current_design $my_toplevel
link

# Create clock and constraints
create_clock -period $my_period -name $my_clock_pin [get_ports $my_clock_pin]
set_clock_uncertainty $my_uncertainty [get_clocks $my_clock_pin]
set_clock_transition {constraints.get('clock_transition', 0.1)} [get_clocks $my_clock_pin]

# Input/output constraints
set_input_delay -clock $my_clock_pin -max [expr $my_period * {constraints.get('input_delay_factor', 0.1)}] [remove_from_collection [all_inputs] [get_ports $my_clock_pin]]
set_output_delay -clock $my_clock_pin -max [expr $my_period * {constraints.get('output_delay_factor', 0.1)}] [all_outputs]
set_load {constraints.get('load', 0.01)} [all_outputs]
set_driving_cell -lib_cell {constraints.get('driving_cell', 'sky130_osu_sc_12T_ms__dff_1')} -pin Q [remove_from_collection [all_inputs] [get_ports $my_clock_pin]]

# Synthesis strategy
{' '.join(compile_opts)}

# Generate reports
file mkdir $outputDir/reports
report_qor > $outputDir/reports/qor.rep
report_area -hierarchy -nosplit -physical > $outputDir/reports/area.rep
report_timing -capacitance -transition_time -nets -nworst 1 > $outputDir/reports/timing.rep
report_power -hierarchy > $outputDir/reports/power.rep
report_constraint > $outputDir/reports/constraint.rep

# Write outputs
file mkdir $outputDir/mapped
write_file -f verilog -hierarchy -output $outputDir/mapped/$my_design.sv
write_sdc $outputDir/mapped/$my_design.sdc
write_file -format ddc -hierarchy -output $outputDir/mapped/$my_design.ddc

# Success message
puts "Wally synthesis completed successfully!"
quit
'''
        return script

    def _run_design_compiler(self, script_path: Path, run_dir: Path) -> tuple[bool, str]:
        """Execute Design Compiler with the generated script"""
        # Get DC command from configuration
        dc_executable = self.machine_config.get_tool_executable('synopsys', 'dc_shell')
        dc_args = self.machine_config.raw_config.get('tools', {}).get('synopsys', {}).get('dc_shell', {}).get('args', ['-64bit'])
        timeout = self.machine_config.raw_config.get('tools', {}).get('synopsys', {}).get('dc_shell', {}).get('timeout', 3600)

        cmd = [dc_executable] + dc_args + ["-f", str(script_path)]

        if self.verbose:
            print(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=run_dir,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Write synthesis log
            log_path = run_dir / "synthesis.log"
            with open(log_path, 'w') as f:
                f.write(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")

            if result.returncode == 0:
                return True, "Synthesis completed successfully"
            else:
                return False, f"Synthesis failed with return code {result.returncode}"

        except subprocess.TimeoutExpired:
            return False, f"Synthesis timed out after {timeout} seconds"
        except Exception as e:
            return False, f"Synthesis error: {e!s}"

    def _parse_results(self, run_dir: Path) -> dict:
        """Parse synthesis results from report files"""
        results = {}

        # Parse area report
        area_file = run_dir / "reports" / "area.rep"
        if area_file.exists():
            results['area_um2'] = self._parse_area_report(area_file)

        # Parse timing report
        timing_file = run_dir / "reports" / "timing.rep"
        if timing_file.exists():
            slack, path_delay = self._parse_timing_report(timing_file)
            results['slack_ns'] = slack
            results['critical_path_ns'] = path_delay

        # Parse QoR report
        qor_file = run_dir / "reports" / "qor.rep"
        if qor_file.exists():
            qor_data = self._parse_qor_report(qor_file)
            results.update(qor_data)

        return results

    def _parse_area_report(self, area_file: Path) -> Optional[float]:
        """Parse area from synthesis report"""
        try:
            with open(area_file) as f:
                content = f.read()

            # Look for "Total cell area:" line
            match = re.search(r'Total cell area:\s+([0-9.]+)', content)
            if match:
                return float(match.group(1))

        except Exception as e:
            if self.verbose:
                print(f"Error parsing area report: {e}")
        return None

    def _parse_timing_report(self, timing_file: Path) -> tuple[Optional[float], Optional[float]]:
        """Parse timing information from report"""
        try:
            with open(timing_file) as f:
                content = f.read()

            slack = None
            path_delay = None

            # Look for slack
            slack_match = re.search(r'slack \(MET\)\s+([0-9.-]+)', content)
            if slack_match:
                slack = float(slack_match.group(1))

            # Look for path delay
            delay_match = re.search(r'data arrival time\s+([0-9.]+)', content)
            if delay_match:
                path_delay = float(delay_match.group(1))

            return slack, path_delay

        except Exception as e:
            if self.verbose:
                print(f"Error parsing timing report: {e}")
        return None, None

    def _parse_qor_report(self, qor_file: Path) -> dict:
        """Parse Quality of Results report"""
        results = {}
        try:
            with open(qor_file) as f:
                content = f.read()

            # Parse cell count
            cell_match = re.search(r'Leaf Cell Count:\s+([0-9]+)', content)
            if cell_match:
                results['cell_count'] = int(cell_match.group(1))

        except Exception as e:
            if self.verbose:
                print(f"Error parsing QoR report: {e}")

        return results

    def synthesize(self, config: SynthesisConfig) -> SynthesisResult:
        """Run complete synthesis flow"""
        start_time = time.time()

        if self.verbose:
            print(f"🔧 Starting synthesis: {config.config} @ {config.frequency_mhz}MHz on {config.technology}")

        # Create run directory
        run_dir = self._create_run_directory(config)

        try:
            # Copy source files
            self._copy_source_files(config, run_dir)

            # Generate synthesis script
            script_path = self._generate_synthesis_script(config, run_dir)

            # Run synthesis
            success, message = self._run_design_compiler(script_path, run_dir)

            # Parse results
            synthesis_time = time.time() - start_time
            parsed_results = self._parse_results(run_dir) if success else {}

            # Create result object
            result = SynthesisResult(
                config=config,
                success=success,
                run_directory=run_dir,
                synthesis_time_s=synthesis_time,
                error_message=None if success else message,
                **parsed_results
            )

            if self.verbose:
                if success:
                    area_str = f"{result.area_um2:.1f} µm²" if result.area_um2 else "Unknown area"
                    print(f"✅ Synthesis completed: {area_str} in {synthesis_time:.1f}s")
                else:
                    print(f"❌ Synthesis failed: {message}")

            return result

        except Exception as e:
            synthesis_time = time.time() - start_time
            error_msg = f"Synthesis exception: {e!s}"

            if self.verbose:
                print(f"❌ {error_msg}")

            return SynthesisResult(
                config=config,
                success=False,
                run_directory=run_dir,
                synthesis_time_s=synthesis_time,
                error_message=error_msg
            )

    def batch_synthesize(self, configs: list[SynthesisConfig]) -> list[SynthesisResult]:
        """Run multiple synthesis configurations"""
        results = []

        print(f"🚀 Starting batch synthesis: {len(configs)} configurations")

        for i, config in enumerate(configs, 1):
            print(f"\n[{i}/{len(configs)}] Processing {config.config} @ {config.frequency_mhz}MHz")
            result = self.synthesize(config)
            results.append(result)

        # Summary
        successful = sum(1 for r in results if r.success)
        total_time = sum(r.synthesis_time_s for r in results if r.synthesis_time_s)

        print("\n📊 Batch synthesis complete:")
        print(f"   • Successful: {successful}/{len(configs)}")
        print(f"   • Total time: {total_time:.1f} seconds")

        return results

    def save_results(self, results: list[SynthesisResult], filename: str = "synthesis_results.json"):
        """Save synthesis results to JSON file"""
        results_data = []

        for result in results:
            data = {
                'config': {
                    'design': result.config.design,
                    'config': result.config.config,
                    'frequency_mhz': result.config.frequency_mhz,
                    'technology': result.config.technology,
                    'feature_mode': result.config.feature_mode,
                    'max_optimization': result.config.max_optimization
                },
                'success': result.success,
                'area_um2': result.area_um2,
                'slack_ns': result.slack_ns,
                'power_mw': result.power_mw,
                'cell_count': result.cell_count,
                'synthesis_time_s': result.synthesis_time_s,
                'critical_path_ns': result.critical_path_ns,
                'run_directory': str(result.run_directory) if result.run_directory else None,
                'error_message': result.error_message
            }
            results_data.append(data)

        output_file = self.synth_dir / filename
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)

        print(f"💾 Results saved to {output_file}")


if __name__ == '__main__':
    # Simple test
    engine = CVWSynthesisEngine(verbose=True)

    config = SynthesisConfig(
        config="rv32e",
        frequency_mhz=200,
        technology="sky130"
    )

    result = engine.synthesize(config)
    print(f"Test result: {result}")
