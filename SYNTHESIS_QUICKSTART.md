# CVW Synthesis Quick Start

This repository includes a simple script to run synthesis from a clean clone.

## Quick Synthesis

Run synthesis with default parameters (64-bit adder, rv32e config, 100 MHz, sky130 technology):

```bash
./run_synth.sh
```

## Custom Parameters

You can specify custom parameters:

```bash
./run_synth.sh [design] [config] [frequency] [technology] [width]
```

### Examples:

```bash
# 64-bit adder at 150 MHz
./run_synth.sh adder rv32e 150 sky130 64

# 32-bit adder at 200 MHz  
./run_synth.sh adder rv32e 200 sky130 32

# Different RISC-V configuration
./run_synth.sh adder rv64gc 100 sky130 64
```

### Parameters:
- **design**: Module to synthesize (default: `adder`)
- **config**: RISC-V configuration (default: `rv32e`)  
- **frequency**: Target frequency in MHz (default: `100`)
- **technology**: Technology library (default: `sky130`)
- **width**: Bit width for parameterized designs (default: `64`)

## Requirements

The script automatically checks for and sets up:
- ✅ CVW environment (sources `setup.sh`)
- ✅ Design Compiler tool availability
- ✅ Technology libraries (sky130)
- ✅ Environment variables (WALLY, RISCV)

## Output

After successful synthesis, you'll find results in:
```
synthDC/runs/[design]_[config]_[tech]_[freq]_MHz_[timestamp]/
├── reports/
│   ├── area.rep      # Area breakdown
│   ├── timing.rep    # Timing analysis
│   ├── qor.rep       # Quality of Results
│   └── power.rep     # Power estimation
├── mapped/
│   ├── [design].sv   # Synthesized netlist
│   ├── [design].sdc  # Timing constraints
│   └── [design].sdf  # Standard Delay Format
└── synth.out         # Full synthesis log
```

## Advanced Usage

For frequency sweeps and advanced analysis, see the comprehensive tools in `synthDC/`:
- `freq_sweep.py` - Automated frequency sweep with plotting
- `wallySynth.py` - Batch synthesis automation

## Troubleshooting

If you encounter issues:

1. **Permission errors**: Some warnings are normal and don't affect synthesis
2. **Tool not found**: Ensure Design Compiler is installed at `/opt/snps/syn/W-2024.09-SP4-1/`
3. **Library errors**: Verify sky130 libraries exist at `/opt/riscv/cad/lib/sky130_osu_sc_t12/`

The script provides detailed error messages to help diagnose issues.
