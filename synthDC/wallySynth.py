#!/usr/bin/env python3
"""CVW Wally Synthesis Tool - Automated synthesis with multiple configurations"""

import argparse
import os
import subprocess
import sys
import time
from multiprocessing import Pool


def runSynth(config, mod, tech, freq, maxopt, usesram, design='wallypipelinedcore', width=None):
    """Run synthesis with proper environment setup and error handling"""
    global pool
    # Use config directly - no prefix needed for standard configs
    cfg = config

    # Build command based on design type
    if design == 'wallypipelinedcore':
        command = f"make synth DESIGN={design} CONFIG={cfg} MOD={mod} TECH={tech} DRIVE=FLOP FREQ={freq} MAXOPT={maxopt} USESRAM={usesram} MAXCORES=1"
    else:
        # For simpler designs like adder, mul, etc.
        width_param = f" WIDTH={width}" if width else ""
        command = f"make synth DESIGN={design} CONFIG={config} TECH={tech} DRIVE=FLOP FREQ={freq} MAXOPT={maxopt} MAXCORES=1{width_param}"

    print(f"Running: {command}")

    # Setup environment for subprocess
    env = os.environ.copy()
    if 'WALLY' not in env:
        env['WALLY'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Add Synopsys tools to PATH
    synopsys_path = "/opt/snps/syn/V-2023.12-SP5-3/bin"
    if synopsys_path not in env.get('PATH', ''):
        env['PATH'] = f"{synopsys_path}:{env.get('PATH', '')}"

    # Run synthesis with proper error handling
    try:
        result = subprocess.run(command, shell=True, env=env, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            print(f"ERROR in synthesis: {command}")
            print(f"STDERR: {result.stderr}")
            return False
        else:
            print(f"SUCCESS: {command}")
            return True
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {command}")
        return False
    except Exception as e:
        print(f"EXCEPTION in {command}: {e}")
        return False


def mask(command):
    """Legacy function - replaced with better error handling in runSynth"""
    subprocess.Popen(command, shell=True)


if __name__ == '__main__':
    techs = ['sky130', 'sky90', 'tsmc28', 'tsmc28psyn']
    allConfigs = ['rv32gc', 'rv32imc', 'rv64gc', 'rv64imc', 'rv32e', 'rv32i', 'rv64i']
    freqVaryPct = [-20, -12, -8, -6, -4, -2, 0, 2, 4, 6, 8, 12, 20]

    pool = Pool()

    parser = argparse.ArgumentParser(description='CVW Wally Synthesis Tool')

    parser.add_argument("-s", "--freqsweep", type=int,
                       help="Synthesize wally with target frequencies at given MHz and +/- percentages")
    parser.add_argument("-c", "--configsweep", action='store_true',
                       help="Synthesize wally with all RISC-V configurations")
    parser.add_argument("-f", "--featuresweep", action='store_true',
                       help="Synthesize wally with features turned off progressively")

    parser.add_argument("-v", "--version", choices=allConfigs,
                       help="Configuration of wally")
    parser.add_argument("-t", "--targetfreq", type=int,
                       help="Target frequency in MHz")
    parser.add_argument("-e", "--tech", choices=techs,
                       help="Technology node")
    parser.add_argument("-o", "--maxopt", action='store_true',
                       help="Turn on maximum optimization")
    parser.add_argument("-r", "--usesram", action='store_true',
                       help="Use SRAM modules")

    args = parser.parse_args()

    # Validate environment
    if 'WALLY' not in os.environ:
        print("WARNING: WALLY environment variable not set")
        os.environ['WALLY'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Set WALLY={os.environ['WALLY']}")

    tech = args.tech if args.tech else 'sky130'  # Changed default to sky130
    maxopt = int(args.maxopt)
    usesram = int(args.usesram)
    mod = 'orig'

    # Better default frequencies per technology
    default_freqs = {
        'sky130': 330,
        'sky90': 870,
        'tsmc28': 2800,
        'tsmc28psyn': 2800
    }

    print(f"Starting synthesis with technology: {tech}")
    start_time = time.time()
    success_count = 0
    total_count = 0

    if args.freqsweep:
        sc = args.freqsweep
        config = args.version if args.version else 'rv32e'
        print(f"Running frequency sweep for {config} around {sc} MHz")

        for freq in [round(sc+sc*x/100) for x in freqVaryPct]:
            total_count += 1
            if runSynth(config, mod, tech, freq, maxopt, usesram):
                success_count += 1

    elif args.configsweep:
        freq = args.targetfreq if args.targetfreq else default_freqs.get(tech, 500)
        print(f"Running configuration sweep at {freq} MHz")

        for config in ['rv32i', 'rv64gc', 'rv64i', 'rv32gc', 'rv32imc', 'rv32e']:
            total_count += 1
            if runSynth(config, mod, tech, freq, maxopt, usesram):
                success_count += 1

    elif args.featuresweep:
        freq = args.targetfreq if args.targetfreq else default_freqs.get(tech, 500)
        config = args.version if args.version else 'rv64gc'
        print(f"Running feature sweep for {config} at {freq} MHz")

        for mod in ['orig', 'noAtomic', 'noFPU', 'noMulDiv', 'noPriv', 'pmp0']:
            total_count += 1
            if runSynth(config, mod, tech, freq, maxopt, usesram):
                success_count += 1
    else:
        # Single synthesis
        freq = args.targetfreq if args.targetfreq else default_freqs.get(tech, 500)
        config = args.version if args.version else 'rv64gc'
        print(f"Running single synthesis: {config} at {freq} MHz")

        total_count = 1
        if runSynth(config, mod, tech, freq, maxopt, usesram):
            success_count = 1

    # Summary
    elapsed = time.time() - start_time
    print("\n=== Synthesis Summary ===")
    print(f"Successful: {success_count}/{total_count}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print(f"Technology: {tech}")

    if success_count < total_count:
        print(f"WARNING: {total_count - success_count} synthesis runs failed")
        sys.exit(1)
    else:
        print("All synthesis runs completed successfully!")
        sys.exit(0)
