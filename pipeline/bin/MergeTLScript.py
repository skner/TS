#!/usr/bin/python
# Copyright (C) 2012 Ion Torrent Systems, Inc. All Rights Reserved

__version__ = filter(str.isdigit, "$Revision$")

import os
import sys
import argparse
import traceback
import json
import subprocess

from ion.utils import blockprocessing
from ion.utils import explogparser
from ion.utils import sigproc
from ion.utils import basecaller
from ion.utils import alignment

from ion.utils.blockprocessing import printtime

from ion.utils.compress import make_zip

if __name__=="__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', dest='verbose', action='store_true')
    parser.add_argument('-s', '--do-sigproc', dest='do_sigproc', action='store_true', help='signal processing')
    parser.add_argument('-b', '--do-basecalling', dest='do_basecalling', action='store_true', help='base calling')
    parser.add_argument('-a', '--do-alignment', dest='do_alignment', action='store_true', help='alignment')
    parser.add_argument('-z', '--do-zipping', dest='do_zipping', action='store_true', help='zipping')

    args = parser.parse_args()

    if args.verbose:
        print "MergeTLScript:",args

    if not args.do_sigproc and not args.do_basecalling and not args.do_alignment and not args.do_zipping:
        parser.print_help()
        sys.exit(1)

    #ensure we permit read/write for owner and group output files.
    os.umask(0002)

    blockprocessing.printheader()
    env,warn = explogparser.getparameter()

    blockprocessing.write_version()
    sys.stdout.flush()
    sys.stderr.flush()

    blocks = explogparser.getBlocksFromExpLogJson(env['exp_json'], excludeThumbnail=True)
    dirs = ['block_%s' % block['id_str'] for block in blocks]


    if args.do_sigproc:

        merged_bead_mask_path = os.path.join(env['SIGPROC_RESULTS'], 'MaskBead.mask')

        sigproc.mergeSigProcResults(
            dirs,
            env['SIGPROC_RESULTS'],
            env['shortRunName'])


    if args.do_basecalling:
        # Only merge metrics and generate plots
        basecaller.merge_basecaller_stats(
            dirs,
            env['BASECALLER_RESULTS'],
            env['SIGPROC_RESULTS'],
            env['flows'],
            env['flowOrder'])
        ## Generate BaseCaller's composite "Big Data": unmapped.bam. Totally optional
        if env.get('libraryName','') == 'none':        
            actually_merge_unmapped_bams = True
        else:
            actually_merge_unmapped_bams = False
        if actually_merge_unmapped_bams:
            basecaller.merge_basecaller_bam(
                dirs,
                env['BASECALLER_RESULTS'])

    if args.do_alignment and env['libraryName'] and env['libraryName']!='none':
        # Only merge metrics and generate plots
        alignment.merge_alignment_stats(
            dirs,
            env['BASECALLER_RESULTS'],
            env['ALIGNMENT_RESULTS'],
            env['flows'])
        ## Generate Alignment's composite "Big Data": mapped bam. Totally optional
        actually_merge_mapped_bams = True
        if actually_merge_mapped_bams:
            alignment.merge_alignment_bigdata(
                dirs,
                env['BASECALLER_RESULTS'],
                env['ALIGNMENT_RESULTS'],
                env['mark_duplicates'])

    if args.do_zipping:
        
        datasets_basecaller_path = os.path.join(env['BASECALLER_RESULTS'],"datasets_basecaller.json")
        datasets_basecaller = {}
    
        if os.path.exists(datasets_basecaller_path):
            try:
                f = open(datasets_basecaller_path,'r')
                datasets_basecaller = json.load(f);
                f.close()
            except:
                printtime("ERROR: problem parsing %s" % datasets_basecaller_path)
                traceback.print_exc()
        else:
            printtime("ERROR: %s not found" % datasets_basecaller_path)


        # This is a special procedure to create links with official names to all downloadable data files
        
        physical_file_prefix = 'rawlib'
        official_file_prefix = "%s_%s" % (env['expName'], env['resultsName'])
        download_links = 'download_links'

        link_src = [
            os.path.join(env['BASECALLER_RESULTS'], 'rawtf.bam'),
            os.path.join(env['BASECALLER_RESULTS'], physical_file_prefix+'.basecaller.bam'),
            os.path.join(env['ALIGNMENT_RESULTS'], physical_file_prefix+'.bam'),
            os.path.join(env['ALIGNMENT_RESULTS'], physical_file_prefix+'.bam.bai')]
        link_dst = [
            os.path.join(download_links, official_file_prefix+'.rawtf.bam'),
            os.path.join(download_links, official_file_prefix+'.basecaller.bam'),
            os.path.join(download_links, official_file_prefix+'.bam'),
            os.path.join(download_links, official_file_prefix+'.bam.bai')]

        try:
            os.mkdir(download_links)
        except:
            printtime(traceback.format_exc())
        
        for (src,dst) in zip(link_src,link_dst):
            if not os.path.exists(dst) and os.path.exists(src):
                try:
                    os.symlink(os.path.relpath(src,os.path.dirname(dst)),dst)
                except:
                    printtime("ERROR: Unable to symlink '%s' to '%s'" % (src, dst))
                    printtime(traceback.format_exc())



        prefix_list = [dataset['file_prefix'] for dataset in datasets_basecaller.get("datasets",[])]
        
        if len(prefix_list) > 1:
            zip_task_list = [
                ('bam',             env['ALIGNMENT_RESULTS']),
                ('bam.bai',         env['ALIGNMENT_RESULTS']),
                ('basecaller.bam',  env['BASECALLER_RESULTS']),]

            for extension,base_dir in zip_task_list:
                zipname = "%s/%s_%s.barcode.%s.zip" % (download_links, env['expName'], env['resultsName'], extension)
                for prefix in prefix_list:
                    try:
                        filename = "%s/%s_%s_%s.%s" % (download_links, prefix.rstrip('_rawlib'), env['expName'], env['resultsName'], extension)
                        src = os.path.join(base_dir, prefix+'.'+extension)
                        if os.path.exists(src):
                            os.symlink(os.path.relpath(src,os.path.dirname(filename)),filename)
                            make_zip(zipname, filename, arcname=filename)
                    except:
                        printtime("ERROR: target: %s" % filename)
                        traceback.print_exc()

        else:
            printtime("MergeTLScript: No barcode run")

    printtime("MergeTLScript exit")
    sys.exit(0)