#############################################################################
# Functions to read sequences for degenotate
#############################################################################

import sys
import os
import gzip
import degenotate_lib.core as CORE
import degenotate_lib.output as OUT
from itertools import groupby

#############################################################################

def bioTranslator(seq, code):
# A function to translate a codon sequence to amino acids

    assert len(seq) % 3 == 0, "\nOUT OF FRAME NUCLEOTIDE SEQUENCE! " + str(len(seq));
    # Check that sequence is in frame.

    codon_seq = [(seq[i:i+3]) for i in range(0, len(seq), 3)];
    # Get chunks of 3 characters into a list.

    aa_seq = [ code[codon] for codon in codon_seq];
    # Build the aa sequence by looking up each codon in the provided code dict

    return "".join(aa_seq);
    # Return the amino acid sequence as a string

############################################################################# 

def readFasta(filename, seq_compression, seq_delim):
# Read a FASTA formatted sequence file
# Great iterator and groupby code from: https://www.biostars.org/p/710/ 

    if seq_compression == "gz":
        file_stream = gzip.open(filename);
        fa_iter = (x[1] for x in groupby(file_stream, lambda line: line.decode()[0] == ">"));
        readstr = lambda s : s.decode().strip();
    elif seq_compression == "none":
        file_stream = open(filename); 
        fa_iter = (x[1] for x in groupby(file_stream, lambda line: line[0] == ">"));
        readstr = lambda s : s.strip();
    # Read the lines of the file depending on the compression level
    # file_stream opens the file as an iterable
    # groupby takes an iterable (file_stream) and a function that indicates the key of the group. It iterates over
    # the iterable and when it encounters a key, it groups all following items to it (perfect for FASTA files).
    # fa_iter is a generator object holding all the grouped iterators.
    # readstr is a function that changes depending on compression level -- for compressed files we also need to decode
    # each string in the iterators below.

    seqdict = {};
    # A dictionary of sequences:
    # <sequence id/header> : <sequence>

    for header_obj in fa_iter:
        header = readstr(header_obj.__next__());
        # The header object is an iterator. This gets the string.

        curkey = header[1:];
        if seq_delim:
            curkey = curkey.split(seq_delim)[0];         
        # This removes the ">" character from the header string to act as the key in seqdict
        # and splits the header based on user input from the -d option

        seq = "".join(readstr(s) for s in fa_iter.__next__());
        # The current header should correspond to the current iterator in fa_iter. This gets all those
        # lines and combines them as a string.

        #print(header, len(seq));

        seqdict[curkey] = seq;
        # Save the sequence in the dictionary

    return seqdict;

#############################################################################

def readGenome(globs):
# A function that reads an entire genome fasta file into memory

    step = "Detecting compression of genome FASTA file";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    globs['seq-compression'] = CORE.detectCompression(globs['fa-file']);
    if globs['seq-compression'] == "none":
        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: No compression detected");
    else:
        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + globs['seq-compression'] + " detected");
    # Detect the compression of the input sequence file

    step = "Reading genome FASTA file";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    globs['genome-seqs'] = readFasta(globs['fa-file'], globs['seq-compression'], globs['seq-delim']);
    step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(len(globs['genome-seqs'])) + " seqs read");
    # Read the input sequence file

    #print(list(globs['genome-seqs'].keys()))
    ## NOTE: reading by index actually doesn't seem feasible because gzipped files must be decompressed each time seek() is called

    return globs;

#############################################################################

def checkHeaders(globs):
    step = "Checking headers";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    # Status update

    annotation_headers = set([ globs['annotation'][t]['header'] for t in globs['annotation'] ]);
    # Extract unique headers from annotation file

    for header in annotation_headers:
        if header not in globs['genome-seqs']:
            print();
            CORE.errorOut("SEQ1", "Region in annotation file not found in genome file: " + header + ". Reminder: you can use -d to trim FASTA headers at a given character.", globs);
    # Check each header in the annotation file against those in the FASTA file and print an error if one isn't found

    step_start_time = CORE.report_step(globs, step, step_start_time, "Success");
    # Status update

#############################################################################

def extractCDS(globs):
# This takes the coordiantes read from the input annotation file as well as the sequence read from the
# input genome fasta file and extracts coding sequences and coordinates for the CDS of all transcripts
# while accounting for strand

    step = "Extracting CDS";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    # Status update

    transcripts_no_exons, rm_transcripts = [], [];

    for transcript in globs['annotation']:

        if len(globs['annotation'][transcript]['exons']) == 0:
            transcripts_no_exons.append(transcript);
            continue;
        # No exons means this transcript does not have a CDS, so we skip it

        cur_seq = "";
        # Initialize the sequence string for the current transcript. This will be added to the 'seqs' dict later

        globs['coords'][transcript] = {};
        globs['coords-rev'][transcript] = {};
        cds_coord = 0;
        # Initialize the coord lookup dict for this transcript and start the coord count at 0

        header = globs['annotation'][transcript]['header'];
        strand = globs['annotation'][transcript]['strand'];
        # Unpack some info about the transcript

        exons = globs['annotation'][transcript]['exons'];
        # Get the exons for the current transcript

        if not all(exons[exon]['strand'] == strand for exon in exons):
            # print("\n\n");
            # print(transcript, strand);
            # print(exons);
            # print("\n\n");
            # CORE.errorOut("SEQ2", "Some exons have differing strands", globs);
            rm_transcripts.append(transcript);
            continue;
        # Add check to make sure exons all have same strand as transcript

        exon_coords = { exons[exon]['start'] : exons[exon]['end'] for exon in exons };
        exon_phase = { exons[exon]['start'] : exons[exon]['phase'] for exon in exons };
        # Get the coordinates of all the exons in this transcript

        if strand == "+":
            sorted_starts = sorted(list(exon_coords.keys()));
        elif strand == "-":
            sorted_starts = sorted(list(exon_coords.keys()), reverse=True);
        # Sort the start coordinates based on strand
         
        first_exon_genome_start = sorted_starts[0];
        first_exon_genome_end = exon_coords[sorted_starts[0]];
        
        if strand == "+":
            globs['annotation'][transcript]['coding-start'] = first_exon_genome_start
        elif strand == "-":
            globs['annotation'][transcript]['coding-start'] = first_exon_genome_end
        
        globs['annotation'][transcript]['start-frame'] = int(exon_phase[first_exon_genome_start])
        # Get the start and end coordinates of the first exon and the phase

        for genome_coord_start in sorted_starts:
            cur_exon_seq = globs['genome-seqs'][header][genome_coord_start-1:exon_coords[genome_coord_start]];
            # For each exon starting coordinate, extract the sequence that corresponds to the current header and
            # start and end coordinates
            # Subtract 1 here since GXF coordinates are 1-based and Python strings (like our genome) are 0-based

            cur_exon_len = len(cur_exon_seq);
            # Get the length of the current exon to count up coordinates

            cds_coord_list = list(range(cds_coord, cds_coord+cur_exon_len));
            # The list of coordinates in the current CDS relative to the first CDS

            genome_coord_list = list(range(genome_coord_start, genome_coord_start+cur_exon_len));
            # The list of genome coordinates in the current CDS

            if strand == "-": 
                cur_exon_seq = "".join(globs['complement'].get(base, base) for base in reversed(cur_exon_seq));
                # Reverse complement the sequence of the current CDS
                
                genome_coord_list.reverse(); 
                # Reverse the order of the genome coordinates             
            # If the strand is "-", get the reverse complement of the sequence and reverse the coordinates

            cur_seq += cur_exon_seq;
            # Concatenate the current exon sequence onto the overall transcript sequence

            for i in range(len(cds_coord_list)):
                globs['coords'][transcript][cds_coord_list[i]] = genome_coord_list[i];
                globs['coords-rev'][transcript][genome_coord_list[i]] = cds_coord_list[i];
            # Add the pairs of coordinates (CDS:genome) to the coords dict for this transcript

            cds_coord += cur_exon_len;
            # Increment the CDS coordinate by the length of the current CDS so the next CDS has the correct starting coord

        # End CDS loop
        ##########

        globs['cds-seqs'][transcript] = cur_seq.upper();
        # Save the current transcript sequence to the global seqs dict

        # End transcript loop
        ##########

    step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(len(globs['cds-seqs'])) + " CDS read");
    # Status update

    if transcripts_no_exons:
        for no_exon_transcript in transcripts_no_exons:
            CORE.printWrite(globs['logfilename'], 3, "# WARNING: transcript " + no_exon_transcript + " has no coding exons associated with it and will be REMOVED from subsequent analyses.");
            globs['warnings'] += 1;
            del globs['annotation'][no_exon_transcript];

    if rm_transcripts:
        for rm_transcript in rm_transcripts:
            CORE.printWrite(globs['logfilename'], 3, "# WARNING: transcript " + rm_transcript + " contains exons annotated on differing strands. This transcript will be REMOVED from subsequent analyses.");
            globs['warnings'] += 1;
            del globs['annotation'][rm_transcript];
    # Remove transcripts with problems, either no coding exons or mis-matched exon strands, from subsequent analyses

    ####################

    if globs['write-cds'] or globs['write-cds-aa'] or globs['write-longest'] or globs['write-longest-aa']:
        step = "Writing CDS sequences";
        step_start_time = CORE.report_step(globs, step, False, "In progress...");
        written = 0;

        if globs['write-cds-aa'] or globs['write-longest-aa']:
            from degenotate_lib.degen import readCodonTable
            degen_table, codon_table = readCodonTable(globs['genetic-code-file']);
        # Read the genetic code to translate sequences if -ca or -la is specified

        if globs['write-cds']:
            nt_stream = open(globs['write-cds'], "w");
        if globs['write-cds-aa']:
            aa_stream = open(globs['write-cds-aa'], "w");
        if globs['write-longest']:
            nt_long_stream = open(globs['write-longest'], "w");
        if globs['write-longest-aa']:
            aa_long_stream = open(globs['write-longest-aa'], "w");
        # Open the files to be written

        for transcript in globs['cds-seqs']:
            extra_leading_nt = globs['annotation'][transcript]['start-frame'];
            if extra_leading_nt is None:
                CORE.printWrite(globs['logfilename'], 3, "# WARNING: transcript " + transcript + " has an unknown frame....skipping");
                globs['warnings'] += 1;                    
                continue;
            # Get the frame of the current transcript and print a warning if it is unknown

            seq = globs['cds-seqs'][transcript][extra_leading_nt:];
            extra_trailing_nt = len(seq) % 3;
            if extra_trailing_nt > 0:
                seq = seq[:-extra_trailing_nt];
            # Adjust the sequence based on the frame and being divisible by 3

            if globs['write-cds-aa'] or globs['write-longest-aa']:
                aa_seq = bioTranslator(seq, codon_table);
            # If an amino acid output has been specified, translate the sequence here

            if globs['write-cds']:
                OUT.writeSeq(">" + transcript, seq, nt_stream);
            if globs['write-cds-aa']: 
                OUT.writeSeq(">" + transcript, aa_seq, aa_stream);
            # Write the nucleotide sequence

            if globs['annotation'][transcript]['longest'] == "yes":
                if globs['write-longest']:
                    OUT.writeSeq(">" + transcript, seq, nt_long_stream);
                if globs['write-longest-aa']:
                    OUT.writeSeq(">" + transcript, aa_seq, aa_long_stream);
            # Write the sequence if it is the longest isoform

            written += 1;
        ## End sequence writing loop

        if globs['write-cds']:
            nt_stream.close();
        if globs['write-cds-aa']:
            aa_stream.close();
        if globs['write-longest']:
            nt_long_stream.close();
        if globs['write-longest-aa']:
            aa_long_stream.close();
        # Close all open files

        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(written) + " sequences written");
    # Writes extracted CDS seqs to a provided file with options -c, -ca, -l, -la
    ####################

    return globs;

#############################################################################

def readCDS(globs):
    
    step = "Reading CDS FASTA file(s)";
    step_start_time = CORE.report_step(globs, step, False, "In progress...", full_update=True);

    if globs['in-seq-type'] == "directory":
        seq_files = [ f for f in os.listdir(globs['in-seq']) if any(f.endswith(fasta_ext) for fasta_ext in [".fa", ".fa.gz", ".fasta", ".fasta.gz", ".fna", ".fna.gz"]) ];
        ## TODO: Make sure these are all the plausible extensions.
        ## TODO: Add extension lists to globs so they aren't all typed out here?
        ## NOTE: Do we even want to do this check?
    else:
        seq_files = [globs['in-seq']];
    # Get a list of files from the input
    # If the input is a directory, this will be all files in that directory
    # If the input is a file, this will just be a list with only that file in it

    if seq_files == []:
        CORE.errorOut("SEQ3", "No files in the input have extensions indicating they are FASTA files.", globs);
    # Makes sure some files have been read    

    for seq_file in seq_files:
        if globs['in-seq-type'] == "directory":
            seq_file_path = os.path.join(globs['in-seq'], seq_file);
        else:
            seq_file_path = seq_file;
        # For multiple input sequence files (directory), the path will be that directory and the current file

        cur_seqs = readFasta(seq_file_path, CORE.detectCompression(seq_file_path), False);
        # Read sequences in current file
        # Not sure if it is necessary to do the compression detections for each file... seems to take a while

        if len(cur_seqs) == 0:
            CORE.printWrite(globs['logfilename'], globs['log-v'], "# WARNING: file " + seq_file + " doesn't appear to be FASTA formatted... skipping");
            globs['warnings'] += 1;
            continue;
        # Check if we have actually read any sequence

        for seq in cur_seqs:
            # if len(cur_seqs[seq]) % 3 != 0:
            #     CORE.printWrite(globs['logfilename'], globs['log-v'], "# WARNING: sequence " + seq + " in file " + seq_file + " isn't in frame 1... skipping");
            #     globs['warnings'] += 1;
            #     continue;
            # Check that the current sequence is in frame 1

            globs['cds-seqs'][seq] = cur_seqs[seq].upper();
            # Add the current sequence to the global sequence dict

    if not globs['cds-seqs']:
       CORE.errorOut("SEQ3", "No FASTA sequences were read from input. Exiting.", globs); 
    # If no sequences were read from the input, error out

    step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(len(globs['cds-seqs'])) + " CDS read", full_update=True);
    # Status update

    return globs;

#############################################################################