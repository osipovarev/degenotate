#!/usr/bin/env python3
#############################################################################
# Degenotate is a script to calculate degeneracy of coding sites within a
# genome. This is the main interface.
#
# Gregg Thomas
# Fall 2021
#############################################################################

import sys
import os
import degenotate_lib.core as CORE
import degenotate_lib.params as params
import degenotate_lib.opt_parse as OP
import degenotate_lib.gxf as gxf
import degenotate_lib.vcf as vcf
import degenotate_lib.seq as SEQ
import degenotate_lib.degen as degen
import degenotate_lib.output as OUT

#############################################################################

if __name__ == '__main__':
# Main is necessary for multiprocessing to work on Windows.

    globs = params.init();
    # Get the global params as a dictionary.

    print("\n" + " ".join(sys.argv) + "\n");

    if any(v in sys.argv for v in ["--version", "-version", "--v"]):
        print("# degenotate version " + globs['version'] + " released on " + globs['releasedate'])
        sys.exit(0);
    # The version option to simply print the version and exit.
    # Need to get actual degenotate version for this, and not just the interface version.

    print("#");
    print("# " + "=" * 125);
    print(CORE.welcome());
    if "-h" not in sys.argv:
        print("            Degeneracy annotation of transcripts\n");
    # A welcome banner.

    globs = OP.optParse(globs);
    # Getting the input parameters from optParse.

    if globs['info']:
        print("# --info SET. EXITING AFTER PRINTING PROGRAM INFO...\n#")
        sys.exit(0);
    if globs['norun']:
        print("# --norun SET. EXITING AFTER PRINTING OPTIONS INFO...\n#")
        sys.exit(0);
    # Early exit options

    step_start_time = CORE.report_step(globs, "", "", "", start=True);
    # Initialize the step headers

    if globs['gxf-file']:
        globs = gxf.read(globs);
        # Read the features from the annotation file

        globs = SEQ.readGenome(globs);
        # Read the full sequence from the input genome

        SEQ.checkHeaders(globs);
        # Check to make sure the annotation and FASTA headers match

        globs = SEQ.extractCDS(globs);
        # Extract the coding sequences based on the annotation and the genome sequences

        if globs['write-cds'] or globs['write-longest']:
            CORE.endProg(globs);
        # If -c is specified, end the program here

        if globs['vcf-file']:
            step = "Reading VCF file";
            step_start_time = CORE.report_step(globs, step, False, "In progress...");
            globs = vcf.read(globs);
            step_start_time = CORE.report_step(globs, step, step_start_time, "Success");
        # Read the VCF file as a pysam VariantFile object

        step = "Removing genome sequence from memory";
        step_start_time = CORE.report_step(globs, step, False, "In progress...");
        del(globs['genome-seqs']);
        step_start_time = CORE.report_step(globs, step, step_start_time, "Success");
        # Free up the memory from the whole genome sequence since we don't need it anymore

    else:
        globs = SEQ.readCDS(globs);
        # Read the individual coding sequences from input

    #step = "Caclulating degeneracy per transcript";
    #step_start_time = CORE.report_step(globs, step, False, "In progress...");
    globs = degen.processCodons(globs)
    #step_start_time = CORE.report_step(globs, step, step_start_time, "Success");

    # if ("ns" in globs['codon-methods']):
    #     OUT.writeMK(globs);

    CORE.endProg(globs);

#############################################################################
