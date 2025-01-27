#############################################################################
# Functions to handle gtf and gff annotation files.
#############################################################################

import sys
import os
import gzip
import degenotate_lib.core as CORE

#############################################################################

def checkIDs(l, info, id_list, step, globs):
# Each time we read feature info and look for IDs, this checks to make sure only one
# ID is found. Probably unnecessary, but easy enough to check.

    if len(id_list) != 1:
        print("\n\n");
        print(len(id_list));
        print(id_list);
        print(info);
        print(l);
        print("\n\n");
        CORE.errorOut("GXF1", "Invalid number of IDs found during " + step, globs);

#############################################################################

def readFeatures(globs, file_reader, line_reader, feature_list, id_format, parent_id_format, info_field_splitter):

    num_features = 0;
    for line in file_reader(globs['gxf-file']):
            line = line_reader(line);
            # Read and parse the current line of the GXF file

            if "##FASTA" in line[0]:
                break;
            # Maker GFF files sometimes include the sequence of all transcripts at the end. We need to stop reading the file
            # at that point.

            if line[0][0] == "#":
                continue;
            # Header/comment lines should be skipped. Note that this must come after the check for "##FASTA" above, or else
            # the file will keep being read into the sequences and error out.

            feature_type, seq_header, start, end, strand, phase, feature_info = line[2], line[0], int(line[3]), int(line[4]), line[6], line[7], line[8].split(info_field_splitter);
            # Unpack the pertinent information from the current line into more readable variables.

            feature_info = list(filter(None, feature_info));
            # Remove empty strings from the feature list in case the gff field has a trailing semicolon

            if feature_info[-1][-1] == ";":
                feature_info[-1] = feature_info[-1][:-1];
            # For gtf files, the field splitter includes a space ("; "), meaning the last entry of feature_info will still contain a ; (since it ends ";\n")
            # Remove that trailing ; here.


            if feature_type in feature_list:
            # Skipping any 'unconfirmed_transcript'

                parent_id = [ info_field for info_field in feature_info if info_field.startswith(parent_id_format) ];
                # Get the gene ID associated with the transcript as a list of fields with the "Parent=" prefix

                checkIDs(line, feature_info, parent_id, feature_list[0] +" parent id parsing", globs);
                # A quick check to make sure we have read only one ID

                parent_id = parent_id[0].replace(parent_id_format, "").replace("\"", "");
                # Unpack and parse the gene ID

                feature_len = end - start;

                if feature_list[0] == "transcript":                  

                    feature_id = [ info_field for info_field in feature_info if info_field.startswith(id_format) ];
                    # Get the feature ID as a list of fields with the "ID=" prefix
                
                    checkIDs(line, feature_info, feature_id, feature_list[0] +" id parsing", globs);
                    # A quick check to make sure we have read only one ID

                    feature_id = feature_id[0].replace(id_format, "").replace("\"", "");
                    # Unpack and parse the ID

                    if feature_len < globs['min-len']:
                        CORE.printWrite(globs['logfilename'], 3, "# WARNING: transcript " + feature_id + " has a length shorter than the minimum specified and will be excluded from all calculations (" + str(feature_len) + " < " + str(globs['min-len']) + ")");
                        globs['short-transcripts'].append(feature_id);
                        globs['warnings'] += 1;                    
                        continue;
                    # If the transcript has 0 length for some reason, downstream stuff will be messed up and it should be excluded anyway, so we throw a warning about it
                    # and skip adding it to the annotation dict

                    globs['annotation'][feature_id] = { 'header' : seq_header, 'start' : start, 'end' : end, 'len' : feature_len, 'longest' : "no", 'cdslen': 0, 'strand' : strand, 
                                                        'exons' : {}, "gene-id" : parent_id, 'start-frame' : None, 'coding-start' : None, 'keep' : True,
                                                        0 : 0, 2 : 0, 3 : 0, 4 : 0 };
                    # Add the ID and related info to the annotation dict. This includes an empty dict for exons to be stored in a similar way
                    # The last 4 entries are counts for number of sites with each degeneracy to summarize transcripts

                    try: 
                        globs['genekey'][parent_id].append(feature_id);
                    except KeyError:
                        globs['genekey'][parent_id] = [feature_id];
                    # Make a dict of that includes all the transcript ids associated with a geneid

                elif feature_list[0] == "CDS":
                    
                    if parent_id in globs['short-transcripts']:
                        continue;
                    # Skip exons that have a 0 length transcript as a parent (and are likely 0 length themselves)

                    try: 
                        num_exons = len(globs['annotation'][parent_id]['exons']);
                    except KeyError:
                        continue;
                    #if we find a CDS without an associated transcript, skip it

                    exon_id = "exon-" + str(num_exons+1);
                    # Because exon IDs are not always included for CDS, or they only represent the CDS as a whole (e.g. protein ID from Ensembl), we 
                    # count the number of exons in the transcript as the ID

                    globs['annotation'][parent_id]['exons'][exon_id] = { 'header' : seq_header, 'start' : start, 'end' : end, 'len' : end-start, 'strand' : strand, 'phase' :  phase};
                    globs['annotation'][parent_id]['cdslen'] += end-start+1;
                # Add the ID and related info to the annotation dict.                   

                num_features += 1;
                # Add to the number of transcripts read

    return globs, num_features;

#############################################################################

def getLongest(globs):
# Get the longest transcript for each gene. 
# First look at CDS length; if there are multiple transcript with same CDS length look at mRNA length;
# If there are multiple transcripts with the same CDS and mRNA length take the first alphabetically

    for gene_feature in globs['genekey']:
        longest_transcript = globs['genekey'][gene_feature][0];
        longest_cds = 0;
        longest_mrna = 0;
        for transcript_feature in sorted(globs['genekey'][gene_feature]):
            cds_len = globs['annotation'][transcript_feature]['cdslen']
            mrna_len = globs['annotation'][transcript_feature]['len']
            if cds_len > longest_cds:
                longest_cds = cds_len;
                longest_mrna = mrna_len;
                longest_transcript = transcript_feature;
            elif cds_len == longest_cds and mrna_len > longest_mrna:
                longest_cds = cds_len;
                longest_mrna = mrna_len;
                longest_transcript = transcript_feature;
            else:
                continue;

        globs['annotation'][longest_transcript]['longest'] = "yes";
    
    return globs

#############################################################################

def read(globs):

    step = "Detecting compression of annotation file";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    globs['gxf-compression'] = CORE.detectCompression(globs['gxf-file']);
    if globs['gxf-compression'] == "none":
        reader = open;
        readline = lambda l : l.strip().split("\t");
        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: No compression detected");
    else:
        reader = gzip.open;
        readline = lambda l : l.decode().strip().split("\t");
        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + globs['gxf-compression'] + " detected");
    # Detect the compression of the input annotation file

    if globs['gxf-type'] == "gff":
        field_splitter = ";";
        gene_id_format = "ID=";
        transcript_id_format = "ID=";
        exon_id_format = "ID=";
        transcript_parent_format = "Parent=";
        exon_parent_format = "Parent=";

    elif globs['gxf-type'] == "gtf":
        field_splitter = "; ";
        gene_id_format = "gene_id ";
        transcript_id_format = "transcript_id ";
        exon_id_format = "exon_id ";
        transcript_parent_format = "gene_id ";
        exon_parent_format = "transcript_id ";
    # These outline the differences between GFF and GTF

    globs['annotation'] = {};
    # The main annotation storage dict. A nested structure for genes, transcripts, and coding exons.
    # <transcript id> : { <header>, <start coord>, <end coord>, <strand>, 
    #                       { <exon id> : <exon header>, <exon start coord>, <exon end coord>, <exon strand> } } }

    ####################

    step = "Reading transcripts";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    globs, num_transcripts = readFeatures(globs, reader, readline, ["transcript", "mRNA", "V_gene_segment", "C_gene_segment"], transcript_id_format, transcript_parent_format, field_splitter);
    step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(num_transcripts) + " transcripts read");

    # Read transcripts
    ####################

    step = "Reading coding exons";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    globs, num_cds_exons = readFeatures(globs, reader, readline, ["CDS"], exon_id_format, exon_parent_format, field_splitter);
    globs = getLongest(globs);
    step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(num_cds_exons) + " coding exons read");

    # Read coding exons
    ####################

    if num_cds_exons == 0:
        CORE.errorOut("GXF2", "No CDS exons found in input annotation file! Cannot calculate degeneracy without coding sequences.", globs);
    # Check to make sure at least one CDS sequence is found, otherwise error out

    return globs;

    #############################################################################
    





    #############################################################################
    
    # step = "Reading genes";
    # step_start_time = CORE.report_step(globs, step, False, "In progress...");

    # for line in reader(globs['gxf-file']):
    #     line = readline(line);
    #     # Read and parse the current line of the GXF file

    #     if "##FASTA" in line[0]:
    #         break;
    #     # Maker GFF files sometimes include the sequence of all transcripts at the end. We need to stop reading the file
    #     # at that point

    #     if line[0][0] == "#":
    #         continue;
    #     # Header/comment lines should be skipped. Note that this must come after the check for "##FASTA" above, or else
    #     # the file will keep being read into the sequences and error out

    #     feature_type, seq_header, start, end, strand, feature_info = line[2], line[0], int(line[3]), int(line[4]), line[6], line[8].split(field_splitter);
    #     # Unpack the pertinent information from the current line into more readable variables

    #     if feature_type == "gene":
    #         feature_id = [ info_field for info_field in feature_info if info_field.startswith(gene_id_format) ];
    #         # Get the feature ID as a list of fields with the "ID=" prefix

    #         checkIDs(line, feature_info, feature_id, "gene id parsing", globs);
    #         # A quick check to make sure we have read only one ID

    #         feature_id = feature_id[0].replace(gene_id_format, "").replace("\"", "");
    #         # Unpack and parse the ID

    #         globs['annotation'][feature_id] = { 'header' : seq_header, 'start' : start, 'end' : end, 'strand' : strand, 'transcripts' : {} };
    #         # Add the ID and related info to the annotation dict. This includes an empty dict for transcripts to be stored in a similar way

    # step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(len(globs['annotation'])) + " genes read");
    # # Status update

    # # Old code to read genes
    # ####################
