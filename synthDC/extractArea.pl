#!/usr/bin/env -S perl -w
use strict;
use warnings;

my %techResults;
my $dir = "runs";

my $macro = "Macro/Black Box area:";
my $seq = "Noncombinational area:";
my $buf = "Buf/Inv area:";
my $comb = "Combinational area:";
my $macroC = "Number of macros/black boxes:";
my $seqC = "Number of sequential cells:";
my $bufC = "Number of buf/inv:";
my $combC = "Number of combinational cells:";

my @keywords = (
    "ifu", "ieu", "lsu", "hzu", "ebu.ebu", "priv.priv", "mdu.mdu", "fpu.fpu",
    "wallypipelinedcore", $macro, $seq, $buf, $comb, $macroC, $seqC, $bufC, $combC
);

my @keywordsp = (
    "ifu", "ieu", "lsu", "hzu", "ebu.ebu", "priv.priv", "mdu.mdu", "fpu.fpu", "wallypipelinedcore", 
    "RAMs", "Flip-flops", "Inv/Buf", "Logic", 
    "RAMs Cnt", "Flip-flops Cnt", "Inv/Buf Cnt", "Logic Cnt", "Total Cnt"
);

my @configs = ("rv32e", "rv32i", "rv32imc", "rv32gc", "rv64i", "rv64gc");

opendir(my $dh, $dir) or die "Could not open $dir";
while (my $filename = readdir($dh)) {
    next unless $filename =~ /_orig_/;
    &processRun("$dir/$filename");
}
closedir($dh);

# -------- Print a table per tech --------
foreach my $tech (sort keys %techResults) {
    print "\n==== Area Summary for $tech ====\n";
    printf("%20s\t", "");
    foreach my $config (@configs) {
        printf("%s\t", $config);
    }
    print "\n";

    foreach my $kw (@keywordsp) {
        printf("%20s\t", $kw);
        foreach my $config (@configs) {
            my $r = $techResults{$tech}{$config};
            if ($r && exists $r->{$kw}) {
                my $area = $r->{$kw};
                $area =~ s/(\d)(?=(\d{3})+$)/$1,/g; # comma formatting
                print "$area\t";
            } else {
                print "\t";
            }
        }
        print "\n";
    }
}

# -------- Subroutine: process one run --------
sub processRun {
    my $fname = shift;
    my $ffname = "$fname/reports/area.rep";
    return unless -f $ffname;

    # Extract config and tech from filename
    my ($config) = $fname =~ /_([^_]*)_orig/;
    my ($tech)   = $fname =~ /orig_([^_]+)/;

    open(my $fh, "<", $ffname) or die "Could not read $ffname";

    my %results;
    while (my $line = <$fh>) {
        foreach my $kw (@keywords) {
            if ($line =~ /^${kw}\s+(\S*)/) {
                $results{$kw} = int($1);
            } elsif ($line =~ /^${kw}__\S*\s+(\S*)/) {
                $results{$kw} = int($1);
            }
        }
    }
    close($fh);

    # Post-process
    $results{"Logic"}         = $results{$comb} - $results{$buf};
    $results{"Inv/Buf"}       = $results{$buf};
    $results{"Flip-flops"}    = $results{$seq};
    $results{"RAMs"}          = $results{$macro};
    $results{"Logic Cnt"}     = $results{$combC} - $results{$bufC};
    $results{"Inv/Buf Cnt"}   = $results{$bufC};
    $results{"Flip-flops Cnt"}= $results{$seqC};
    $results{"RAMs Cnt"}      = $results{$macroC};
    $results{"Total Cnt"}     = $results{$macroC} + $results{$seqC} + $results{$combC};

    $techResults{$tech}{$config} = \%results;
}
