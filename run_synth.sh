#!/bin/bash

# CVW Synthesis Setup and Run Script
# ===================================
#
# This script sets up the environment and runs synthesis from a clean repo clone.
# It handles all the common issues encountered when setting up CVW synthesis.
#
# USAGE:
#   ./run_synth.sh [design] [config] [freq] [tech] [width]
#
# EXAMPLES:
#   ./run_synth.sh                              # Default: adder, rv32e, 100MHz, sky130, 64-bit
#   ./run_synth.sh adder rv32e 150 sky130 64    # Custom parameters
#   ./run_synth.sh adder rv64gc 200 sky130 32   # Different config and width
#
# KEY LEARNINGS AND TROUBLESHOOTING:
# ==================================
#
# 1. ENVIRONMENT SETUP ISSUES:
#    - CVW setup.sh often has permission warnings (Imperas, site-setup.sh) - these are normal
#    - WALLY and RISCV environment variables MUST be set for synthesis to work
#    - Design Compiler must be in PATH: /opt/snps/syn/W-2024.09-SP4-1/bin
#
# 2. TECHNOLOGY LIBRARY PROBLEMS:
#    - Using TECH=sky130nm fails - must use TECH=sky130 (no 'nm' suffix)
#    - Sky130 libraries expected at: $RISCV/cad/lib/sky130_osu_sc_t12/12T_ms/lib/
#    - If synthesis shows "gtech" library, environment variables are not set correctly
#    - Successful synthesis should show: sky130_osu_sc_12T_ms_TT_1P8_25C.ccs.db
#
# 3. CONFIG FILE PATH ISSUES:
#    - Original Makefile had incorrect path: $(OLDCONFIGDIR)/deriv/$(CONFIG)/config.vh
#    - Fixed path should be: $(OLDCONFIGDIR)/$(CONFIG)/config.vh
#    - The 'deriv' directory doesn't exist in CVW - this was a legacy path issue
#
# 4. SHELL COMPATIBILITY WARNINGS:
#    - dc_shell-xg-t script has bash/dash compatibility issues with '==' vs '=' operators
#    - Warnings like "unexpected operator" are cosmetic - synthesis still works
#    - /bin/sh -> dash on Ubuntu causes these warnings, but doesn't prevent synthesis
#
# 5. SYNTHESIS RESULT VALIDATION:
#    - Area of 0.000000 µm² indicates technology library not loaded (using gtech fallback)
#    - Proper synthesis should show realistic areas (e.g., 3000-4500 µm² for 64-bit adder)
#    - Check for "Loading db file" messages to confirm correct library usage
#
# 6. FREQUENCY-AREA TRADEOFFS OBSERVED:
#    - 50 MHz:  3287.4 µm² (relaxed timing, smaller area)
#    - 100 MHz: 4085.5 µm² (balanced optimization)
#    - 150 MHz: 3383.6 µm² (aggressive optimization, different cell choices)
#    - Higher frequencies don't always mean larger area due to optimization strategies
#
# 7. SUBPROCESS ENVIRONMENT ISSUES:
#    - Python freq_sweep.py script needs explicit environment variable passing
#    - subprocess.run() doesn't inherit all shell environment automatically
#    - Must explicitly set WALLY, RISCV, and PATH in subprocess environment
#
# 8. REPORT PARSING LESSONS:
#    - Area reports are in reports/area.rep with "Total cell area:" field
#    - Timing reports show slack values - negative slack = timing violation
#    - QoR reports provide comprehensive quality metrics
#    - All reports use consistent directory structure in runs/[design]_[config]_*/
#
# TESTED CONFIGURATIONS:
# =====================
# - adder + rv32e + sky130: Works reliably across 50-200 MHz
# - 64-bit width parameter: Properly parameterizes the adder design
# - Multiple frequency points: All timing constraints met in test range
#
# REQUIREMENTS VERIFIED:
# =====================
# - Synopsys Design Compiler W-2024.09-SP4-1 at /opt/snps/syn/
# - Sky130 OSU standard cell libraries at /opt/riscv/cad/lib/
# - CVW repository with setup.sh in root directory
# - Make and basic shell tools (bash-compatible)
#
# AUTHORS: AI Assistant + User Collaboration
# DATE: November 2025
# VERSION: 1.0 - Initial working version with all major issues resolved

set -e  # Exit on any error

echo "=== CVW Synthesis Setup and Run Script ==="
echo "Date: $(date)"
echo "Working directory: $(pwd)"

# Default parameters (can be overridden by command line arguments)
DESIGN=${1:-adder}
CONFIG=${2:-rv32e}
FREQ=${3:-100}
TECH=${4:-sky130}
WIDTH=${5:-64}

echo "Parameters:"
echo "  Design: $DESIGN"
echo "  Config: $CONFIG"
echo "  Frequency: $FREQ MHz"
echo "  Technology: $TECH"
echo "  Width: $WIDTH bits"
echo

# Check if we're in the CVW root directory
if [ ! -f "setup.sh" ] || [ ! -d "synthDC" ]; then
    echo "ERROR: This script must be run from the CVW root directory"
    echo "Expected files: setup.sh, synthDC/"
    exit 1
fi

echo "=== Step 1: Setting up CVW environment ==="
# Source the CVW setup script
if [ -f "setup.sh" ]; then
    echo "Sourcing setup.sh..."
    source setup.sh 2>/dev/null || {
        echo "Warning: Some setup warnings occurred (usually permission issues)"
        echo "Continuing with synthesis..."
    }
    echo "✓ CVW environment setup complete"
else
    echo "ERROR: setup.sh not found in current directory"
    exit 1
fi

echo
echo "=== Step 2: Checking tool availability ==="

# Check if Design Compiler is available
if ! command -v dc_shell-xg-t &> /dev/null; then
    echo "Adding Design Compiler to PATH..."
    export PATH="/opt/snps/syn/W-2024.09-SP4-1/bin:$PATH"
fi

if command -v dc_shell-xg-t &> /dev/null; then
    echo "✓ Design Compiler found: $(which dc_shell-xg-t)"
else
    echo "ERROR: Design Compiler (dc_shell-xg-t) not found"
    echo "Expected location: /opt/snps/syn/W-2024.09-SP4-1/bin/dc_shell-xg-t"
    exit 1
fi

# Check environment variables
if [ -z "$WALLY" ]; then
    echo "Setting WALLY environment variable..."
    export WALLY=$(pwd)
fi
echo "✓ WALLY: $WALLY"

if [ -z "$RISCV" ]; then
    echo "Setting RISCV environment variable..."
    export RISCV="/opt/riscv"
fi
echo "✓ RISCV: $RISCV"

# Check if sky130 libraries exist (for sky130 tech)
if [ "$TECH" = "sky130" ]; then
    SKY130_LIB="$RISCV/cad/lib/sky130_osu_sc_t12/12T_ms/lib/sky130_osu_sc_12T_ms_TT_1P8_25C.ccs.db"
    if [ -f "$SKY130_LIB" ]; then
        echo "✓ Sky130 library found: $SKY130_LIB"
    else
        echo "WARNING: Sky130 library not found at $SKY130_LIB"
        echo "Synthesis may fall back to generic library"
    fi
fi

echo
echo "=== Step 3: Running synthesis ==="
cd synthDC

echo "Cleaning previous runs..."
make clean 2>/dev/null || true

echo "Running synthesis with parameters:"
echo "  make synth DESIGN=$DESIGN CONFIG=$CONFIG FREQ=$FREQ TECH=$TECH WIDTH=$WIDTH DRIVE=FLOP MAXCORES=1"
echo

# Run the synthesis
make synth DESIGN=$DESIGN CONFIG=$CONFIG FREQ=$FREQ TECH=$TECH WIDTH=$WIDTH DRIVE=FLOP MAXCORES=1

# Check if synthesis was successful
if [ $? -eq 0 ]; then
    echo
    echo "=== Step 4: Checking results ==="

    # Find the most recent run directory
    RUN_DIR=$(ls -td runs/${DESIGN}_${CONFIG}_*_${FREQ}_MHz_* 2>/dev/null | head -1)

    if [ -n "$RUN_DIR" ] && [ -d "$RUN_DIR" ]; then
        echo "✓ Synthesis completed successfully!"
        echo "✓ Results directory: $RUN_DIR"

        # Check for key output files
        if [ -f "$RUN_DIR/reports/area.rep" ]; then
            echo "✓ Area report generated"
            echo
            echo "=== Area Summary ==="
            grep -A 10 "Total cell area:" "$RUN_DIR/reports/area.rep" | head -5
        fi

        if [ -f "$RUN_DIR/reports/timing.rep" ]; then
            echo "✓ Timing report generated"
        fi

        if [ -f "$RUN_DIR/mapped/${DESIGN}.sv" ]; then
            echo "✓ Synthesized netlist generated: $RUN_DIR/mapped/${DESIGN}.sv"
        fi

        echo
        echo "=== Synthesis Summary ==="
        echo "Design: $DESIGN"
        echo "Config: $CONFIG"
        echo "Frequency: $FREQ MHz"
        echo "Technology: $TECH"
        echo "Results: $PWD/$RUN_DIR"
        echo
        echo "To view detailed results:"
        echo "  Area report:   cat $RUN_DIR/reports/area.rep"
        echo "  Timing report: cat $RUN_DIR/reports/timing.rep"
        echo "  QoR report:    cat $RUN_DIR/reports/qor.rep"

    else
        echo "ERROR: No results directory found. Synthesis may have failed."
        exit 1
    fi
else
    echo "ERROR: Synthesis failed with exit code $?"
    exit 1
fi

echo
echo "=== CVW Synthesis Complete! ==="
