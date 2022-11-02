#############################################################################
# Functions to compute degeneracy and syn/nonsyn subs for CDS sequences in degenotate
#############################################################################

import sys
import os
import csv
import re
import itertools
from collections import namedtuple
import lib.vcf as VCF
import lib.output as OUT
import lib.core as CORE

#############################################################################

def readDegen(globs):
# Read a codon table file into a degeneracy dict and a codon dict
# Assumes a plain text, comma-separated file with two columns
# The first column is the three lettter (DNA) codon sequence
# The second column is a three digit code for the degeneracy of the first, second, and third positions
# 0 = non-degenerate; any mutation will change the amino acid
# 2 = two nucleotides at the position code the same AA, so 1 of the three possible
#     mutations will be synonymous and 2 will be non-synonymous
# 3 = three nucleotides at the position code for the same AA, so 2 of the three possible
#     mutations will be synonymous and 1 will be non-synonymous
# 4 = four nucleotides at the position code for the same AA, so all 3 possible
#     mutations are synonymous
# The third column is the one letter AA code for that codon

    if "ns" in globs['codon-methods']:
        try:
            import networkx as nx
            # use networkx to turn codon table into a graph to allow easy computation of paths

            globs['shortest-paths'] = nx.all_shortest_paths;
        except:
            CORE.errorOut("DEGEN1", "Missing networkx dependency. Please install and try again: https://anaconda.org/conda-forge/networkx", globs);
    # Check for the networkx module

    DEGEN_DICT = {}
    CODON_DICT = {}
    with open(os.path.join(os.path.dirname(__file__), "codon-table.csv"), "r") as dd:
        reader = csv.reader(dd)
        for row in reader:
            DEGEN_DICT[row[0]] = row[2];
            CODON_DICT[row[0]] = row[1];

    if "ns" in globs['codon-methods']:
        # compute codon graph
        CODON_GRAPH = nx.Graph()

        # add a node for every codon
        CODON_GRAPH.add_nodes_from(list(CODON_DICT.keys()))
    else:
        CODON_GRAPH = False;

    # add an edge between all codons that are 1 mutation apart
    for codon1 in CODON_DICT.keys():
        for codon2 in CODON_DICT.keys():
            ed = codonHamming(codon1,codon2)
            if ed == 1 and "ns" in globs['codon-methods']:
                CODON_GRAPH.add_edge(codon1,codon2)
            else:
                continue

    return [ DEGEN_DICT, CODON_DICT, CODON_GRAPH, globs ]

#############################################################################

def getFrame(seq):
# A function that returns the frame of a coding sequence
    seq_mod = len(seq) % 3;
    if seq_mod == 0:
        return 0;
    elif seq_mod == 2:
        return 1;
    elif seq_mod == 1:
        return 2;

#############################################################################

def frameError(seq,frame):
# Check that the sequence is the correct multiple of three for the starting frame

    seq_mod = len(seq) % 3
    if frame == 0 and seq_mod == 0:
        return False
    elif frame == 1 and seq_mod == 2:
        return False
    elif frame == 2 and seq_mod == 1:
        return False
    else:
        return True

#############################################################################

#def getVariants(globs,transcript,transcript_position):

    #TO DO - function to return a list of variant codons based on vcf
    #should return two lists: one with all ingroup codons, the other with all outgroup codons
    #because outgroup is assumed to be only fixed differences, should only ever return a single
    #outgroup codon

#############################################################################

def codonPath(start_codon, end_codon, CODON_GRAPH, CODON_DICT, nx_shortest_paths):

    #function to calculate syn/nonsyn for multi-step paths
    #by default returns the average nonsyn and syn subs over all shortest paths b/w two codons
    dn=0.0
    ds=0.0

    #get all shortest paths using networkx functions
    paths = nx_shortest_paths(CODON_GRAPH, source=start_codon, target=end_codon)

    #number of possible shortest paths
    numpaths = 0

    #for each path, calculate the number of syn and nonsyn subs implied
    for path in paths:
        for pairs in itertools.pairwise(path):
            aa1 = CODON_DICT[pairs[0]]
            aa2 = CODON_DICT[pairs[1]]
            if aa1 == aa2:
                ds+=1
            if aa1 != aa2:
                dn+=1
        numpaths += 1

    #calculate average over all paths
    dn = dn/numpaths
    ds = ds/numpaths

    #return values
    return ds,dn

#############################################################################

def codonHamming(codon1,codon2):
    return sum(1 for a, b in zip(codon1, codon2) if a != b)

#############################################################################

def processCodons(globs):
# take CDS sequence and split into list of codons, computing degeneracy, ns, or both
# might need a clearer name?

    DEGEN_DICT, CODON_DICT, CODON_GRAPH, globs = readDegen(globs)
    MKTable = namedtuple("MKTable", "pn ps dn ds")

    ####################

    num_transcripts = len(globs['cds-seqs']);

    step = "Caclulating degeneracy per transcript";
    step_start_time = CORE.report_step(globs, step, False, "Processed 0 / " + str(num_transcripts) + " alns...", full_update=True);
    # Status update

    ####################

    with open(globs['outbed'], "w") as bedfile, open(globs['out-transcript'], "a") as transcriptfile:
        counter = 0;
        for transcript in globs['cds-seqs']:

            if globs['gxf-file']:
                transcript_region = globs['annotation'][transcript]['header'];
            else:
                transcript_region = transcript;
            # Get the genome region if the input was a gxf file+genome

            if globs['gxf-file']:
                frame = globs['annotation'][transcript].get('start-frame', 0);
                # use dict.get() to return value or a default option if key doesn't exist
                # assumes that globs['annotation'][transcript]['start-frame'] won't exist
                # unless start frame was parsed from GFF

            # Get the frame when input is a when input is a gxf+genome
            else:
                frame = getFrame(globs['cds-seqs'][transcript]);
                if frame != 0:
                    CORE.printWrite(globs['logfilename'], 3, "# WARNING: transcript " + transcript + " is partial with unknown frame....skipping");
                    globs['warnings'] += 1;                    
                    continue;
                    ## TODO: Add warning that transcript is skipped 
            # Get the frame when input is a dir/file of individual CDS seqs
            # In this case we just check to make sure the sequence is a multiple of 3

            extra_leading_nt = globs['leading-bases'][int(frame)]
            # Look up the number of leading bases given the current frame

            #if frame is not 1, need to skip the first frame-1 bases
            fasta = globs['cds-seqs'][transcript][extra_leading_nt:]

            #now check to see if there are still trailing bases
            extra_trailing_nt = len(fasta) % 3

            if extra_trailing_nt > 0:
                fasta = fasta[:-extra_trailing_nt]
 
            #make list of codons
            codons = re.findall('...', fasta)

            if ("degen" in globs['codon-methods']):
                degen = [ DEGEN_DICT[x] if "N" not in x else "..." for x in codons ];
                # Get the string of degeneracy integers for every codon in the current sequence (e.g. 002)

                degen = "." * extra_leading_nt + "".join(degen);
                # Convert the degeneracy string to a list, and add on dots for any leading bases that
                # were removed if the frame is not 1

                cds_coord = 0;
                # Start the CDS coord counter

                if frame != 1:
                    for out_of_frame_pos in range(extra_leading_nt):
                        outline = OUT.compileBedLine(globs, transcript, transcript_region, cds_coord, globs['cds-seqs'][transcript][cds_coord], "", "", ".", ".", "");
                        bedfile.write("\t".join(outline) + "\n");
                        # Call the output function with blank values since there is no degeneracy at this position
                        # and write the output to the bed file 

                        cds_coord += 1;
                        # Increment the position in the CDS
                # If the CDS is not in frame 1, the bed output needs to be filled in for the leading bases that were removed
                ##########

                for codon in codons:
                    try:
                        aa = CODON_DICT[codon];
                    except KeyError:
                        aa = "."
                    # Look up the AA of the current codon

                    for codon_pos in [0,1,2]:
                        base = codon[codon_pos];
                        # Extract the current base from the codon string
                    
                        outline = OUT.compileBedLine(globs, transcript, transcript_region, cds_coord, base, codon, codon_pos, aa, degen[cds_coord], CODON_DICT);
                        bedfile.write("\t".join(outline) + "\n");
                        # Write the output from the current position to the bed file

                        if degen[cds_coord] != ".":
                            globs['annotation'][transcript][int(degen[cds_coord])] += 1;
                        # Increment the count for the current degeneracy for the transcript summary
                        # Skip positions with unknown degeneracy ('.')

                        cds_coord += 1;
                        # Increment the position in the CDS
                    # End base loop
                    ##########
                # End codon loop
                ##########

                if extra_trailing_nt != 0:
                    for out_of_frame_pos in range(extra_trailing_nt):
                        outline = OUT.compileBedLine(globs, transcript, transcript_region, cds_coord, globs['cds-seqs'][transcript][cds_coord], "", "", ".", ".", "");
                        bedfile.write("\t".join(outline) + "\n");
                        # Call the output function with blank values since there is no degeneracy at this position
                        # and write the output to the bed file 

                        cds_coord += 1;
                        # Increment the position in the CDS
                # If the CDS has extra trailing bases, the bed output needs to be filled in for the leading bases that were removed
                ##########

                #globs['degeneracy'][transcript] = degen;
                # Add the degen string to the global dict (not sure we need this anymore?)

                # print();
                # print(transcript);
                # print(globs['degeneracy'][transcript]);
                # print();
                # For debugging

            ## Runtime for test chromosome without output:              6 sec
            ## Runtime for test chromosome with output without subs:    20 sec
            ## Runtime for test chromosome with output with subs:       33 sec

            ## Out of frame test seq when using -s test-data/mm10/ensembl/cds/ as input: transcript:ENSMUST00000237320

            t_outline = [transcript, globs['annotation'][transcript]['gene-id'], str(globs['annotation'][transcript]['cdslen']),  str(globs['annotation'][transcript]['len']), str(globs['annotation'][transcript]['longest']),
                            str(globs['annotation'][transcript][0]), str(globs['annotation'][transcript][2]), 
                            str(globs['annotation'][transcript][3]), str(globs['annotation'][transcript][4]) ]
            transcriptfile.write("\t".join(t_outline) + "\n");
            # Compile and write the transcript summary line to the transcript outfile

            # End degen method block
            ####################

            if ("ns" in globs['codon-methods']):

                #define coordinate shift based on frame
                transcript_position = extra_leading_nt;

                #process each codon
                # NOTE GT: I think this will work since I now define the number of extra leading NTs above and in
                # globs['leading-bases'][frame]. We can just start the transcript at that position and
                # increment by 3 each time. Probably needs debuging.
                for codon in codons:
                    try: 
                        ref_aa = CODON_DICT[codon]
                    except KeyError:
                        continue;

                    ps = 0.0
                    pn = 0.0
                    ds = 0.0
                    dn = 0.0

                    #assume getVariants returns a data structure of variant codons
                    #this should be a list (empty, 1, or more) for in group codons
                    #but for outgroup codons, it should be a single string with fixed differences
                    poly_codons,div_codon = VCF.getVariants(globs, transcript, transcript_position, list(codon));
                    #print(transcript,transcript_position,codon,poly_codons,div_codon, sep=":")

                    if poly_codons:
                        #there are variants
                        for poly_codon in poly_codons:

                            #for in group variants, we treat each as independent

                            try:
                                poly_aa = CODON_DICT[poly_codon]
                            except KeyError:
                                continue;
                            
                            if poly_aa == ref_aa:
                                ps += 1;
                            if poly_aa != ref_aa:
                                pn += 1;

                    if div_codon:
                        #there are fixed differences

                        #get number of differences between the codons
                        diffs = codonHamming(div_codon,codon)

                        if diffs == 1:
                            try:
                                div_aa = CODON_DICT[div_codon]
                            except KeyError:
                                continue;
                                
                            if div_aa == ref_aa:
                                ds += 1;
                            if div_aa != ref_aa:
                                dn += 1;

                        if diffs >= 2:
                            ds,dn = codonPath(codon, div_codon, CODON_GRAPH, CODON_DICT, globs['shortest-paths'])

                    try:
                        globs['nonsyn'][transcript][transcript_position] = MKTable(pn,ps,dn,ds)
                    except KeyError:
                        globs['nonsyn'].update({transcript: {transcript_position : MKTable(pn,ps,dn,ds)}})
                    # NOTE GT: do we need to add placeholders for the extra leading bases to the nonsyn dict?
                    # e.g. globs['nonsyn'][transcript] could be a list with the index being the position... not
                    # sure what is easiest here.
                    transcript_position += 3
                # End codon loop
                ##########

            # End ns method block
            ##########

            counter += 1;
            if counter % 100 == 0:
                cur_step_time = CORE.report_step(globs, step, step_start_time, "Processed " + str(counter) + " / " + str(num_transcripts) + " transcripts...", full_update=True);
            # A counter and a status update every 100 loci

        # End transcript loop
        ##########

    # Close bed file
    ##########

    step_start_time = CORE.report_step(globs, step, step_start_time, "Success", full_update=True);
    # Status update

    return globs

#############################################################################