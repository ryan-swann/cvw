#  
# Makefile for synthesis
# Shreya Sanghai (ssanghai@hmc.edu) 2/28/2022
# Madeleine Masser-Frye (mmasserfrye@hmc.edu) 1/27/2023
NAME := synth
# defaults
export DESIGN ?= wallypipelinedcore
export FREQ ?= 10000
export CONFIG ?= rv64gc
export MOD ?= orig
# title to add a note in the synth's directory name
TITLE = 
# tsmc28, sky130, and sky90 presently supported
export TECH ?= sky130
# MAXCORES allows parallel compilation, which is faster but less CPU-efficient
# Avoid when doing sweeps of many optimization points in parallel
export MAXCORES ?= 1
# MAXOPT turns on flattening, boundary optimization, and retiming
# The output netlist is hard to interpret, but significantly better PPA
export MAXOPT ?= 0
export DRIVE ?= FLOP
export USESRAM ?= 0
export WIDTH ?= 32

time := $(shell date +%F-%H-%M)
hash := $(shell git rev-parse --short HEAD)
export OUTPUTDIR := runs/$(DESIGN)_$(CONFIG)_$(MOD)_$(TECH)nm_$(FREQ)_MHz_$(time)_$(TITLE)_$(hash)
export SAIFPOWER ?= 0

OLDCONFIGDIR ?= ${WALLY}/config
export CONFIGDIR ?= $(OUTPUTDIR)/config

default:
	@echo "  Basic synthesis procedure for Wally:"
	@echo "        Invoke with make synth"
	@echo "Use wallySynth.py to run a concurrent sweep "


DIRS32 = rv32e rv32gc rv32imc rv32i
DIRS64 = rv64i rv64gc
DIRS = $(DIRS32) $(DIRS64)

configs: $(CONFIG)
$(CONFIG):
	@echo $(CONFIG)
	@echo "cp -r $(OLDCONFIGDIR)/shared/*.vh $(CONFIGDIR)"
	@echo "cp -r $(OLDCONFIGDIR)/$(CONFIG)/*.vh $(CONFIGDIR)"
	cp -r $(OLDCONFIGDIR)/$(CONFIG)/*.vh $(CONFIGDIR)
	cp -r $(OLDCONFIGDIR)/shared/*.vh $(CONFIGDIR)
	@echo "Case One"
ifeq ($(MOD), orig)
	cp -rf $(OLDCONFIGDIR)/$(CONFIG)/config.vh $(CONFIGDIR) | true
	@echo "Case Two"
else
	cp -rf $(OLDCONFIGDIR)/$(CONFIG)/config.vh $(CONFIGDIR) | true
	@echo "Case Three"
endif

ifeq ($(SAIFPOWER), 1)
	cp -f ../sim/power.saif .
endif

mkdirecs:
	@echo "DC Synthesis"
	@mkdir -p $(OUTPUTDIR)
	@mkdir -p $(OUTPUTDIR)/hdl
	@mkdir -p $(OUTPUTDIR)/config
	@mkdir -p $(OUTPUTDIR)/reports
	@mkdir -p $(OUTPUTDIR)/mapped
	@mkdir -p $(OUTPUTDIR)/unmapped

synth: mkdirecs configs rundc # clean

rundc:
ifeq ($(TECH), tsmc28psyn)
	dc_shell-xg-t -64bit -topographical_mode -f scripts/$(NAME).tcl | tee $(OUTPUTDIR)/$(NAME).out
else
	dc_shell-xg-t -64bit -f scripts/$(NAME).tcl | tee $(OUTPUTDIR)/$(NAME).out	
endif


clean:
	rm -rf $(OUTPUTDIR)/hdl
	rm -rf $(OUTPUTDIR)/WORK
	rm -rf $(OUTPUTDIR)/alib-52
	rm -f default.svf
	rm -f command.log
	rm -f filenames*.log
	rm -f power.saif
	rm -f Synopsys_stack_trace_*.txt
	rm -f crte_*.txt
	
