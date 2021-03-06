#!/usr/bin/env python
'''Instantiate the ENCODE ChIP-seq workflow'''

import sys
import logging
import re
import dxpy

EPILOG = '''Notes:

Examples:
    # Build blank TF workflow from fastq to peaks
    %(prog)s --target tf --name "ENCODE TF ChIP-seq (no reference)" --outf "/ChIP-seq/"

    # Build blank histone workflow from fastq to peaks
    %(prog)s --target histone --name "ENCODE Histone ChIP-seq (no reference)" --outf "/ChIP-seq/"

    # Build a pre-configured GRCh38 histone workflow, requiring only data to run
    %(prog)s --target histone \\
    --name "ENCODE Histone ChIP-seq (GRCh38)" \\
    --chrom_sizes "ENCODE Reference Files:/GRCh38/GRCh38_EBV.chrom.sizes" \\
    --genomesize hs \\
    --reference "ENCODE Reference Files:/GRCh38/GRCh38_no_alt_analysis_set_GCA_000001405.15.fa.gz" \\
    --outf "/ChIP-seq/"

    # Build and run a complete hg19 TF workflow, specifying all inputs.
    %(prog)s --target tf \\
    --chrom_sizes "ENCODE Reference Files:/hg19/male.hg19.chrom.sizes" \\
    --genomesize hs \\
    --reference "ENCODE Reference Files:/hg19/male.hg19.tar.gz" \\
    --blacklist "ENCODE Reference Files:/hg19/blacklists/wgEncodeDacMapabilityConsensusExcludable.bed.gz" \\
    --outf "ENCSR464DKE-hCTCF-chr21" \\
    --title "ENCSR464DKE-hCTCF-chr21" \\
    --rep1 "/ChIP-seq/test_data/ENCSR464DKE-hCTCF/R1-ENCFF921SED.chr21.fq.gz" \\
    --rep2 "/ChIP-seq/test_data/ENCSR464DKE-hCTCF/R2-ENCFF812KOM.chr21.fq.gz" \\
    --ctl1 "/ChIP-seq/test_data/ENCSR464DKE-hCTCF/C1-ENCFF690VPV.chr21.fq.gz" \\
    --ctl2 "/ChIP-seq/test_data/ENCSR464DKE-hCTCF/C2-ENCFF357TLV.chr21.fq.gz" \\
    --yes

    # Build and run a complete hg19 TF workflow, with a unary control.
    %(prog)s --target tf \\
    --chrom_sizes "ENCODE Reference Files:/hg19/male.hg19.chrom.sizes" \\
    --genomesize hs \\
    --reference "ENCODE Reference Files:/hg19/male.hg19.tar.gz" \\
    --blacklist "ENCODE Reference Files:/hg19/blacklists/wgEncodeDacMapabilityConsensusExcludable.bed.gz" \\
    --outf "ENCSR000EEB-hMAFK-chr21" \\
    --title "ENCSR000EEB-hMAFK-chr21" \\
    --rep1 "/ChIP-seq/test_data/ENCSR000EEB-hMAFK/R1-ENCFF000XTT.chr21.fq.gz" \\
    --rep2 "/ChIP-seq/test_data/ENCSR000EEB-hMAFK/R2-ENCFF000XTU.chr21.fq.gz" \\
    --ctl1 "/ChIP-seq/test_data/ENCSR000EEB-hMAFK/C1-ENCFF000XSJ.chr21.fq.gz" \\
    --yes

    # Build and run a complete mm10 histone workflow, specifying all inputs.
    %(prog)s --target histone \\
    --chrom_sizes "ENCODE Reference Files:/mm10/male.mm10.chrom.sizes" \\
    --genomesize mm \\
    --reference "ENCODE Reference Files:/mm10/male.mm10.tar.gz" \\
    --outf "ENCSR087PLZ-mH3K9ac-chr19" \\
    --title "ENCSR087PLZ-mH3K9ac-chr19" \\
    --rep1 "/ChIP-seq/test_data/ENCSR087PLZ-mH3K9ac/R1-ENCFF560GLI.chr19.fq.gz" \\
    --rep2 "/ChIP-seq/test_data/ENCSR087PLZ-mH3K9ac/R2-ENCFF891NNX.chr19.fq.gz" \\
    --ctl1 "/ChIP-seq/test_data/ENCSR087PLZ-mH3K9ac/C1-ENCFF069WCH.chr19.fq.gz" \\
    --ctl2 "/ChIP-seq/test_data/ENCSR087PLZ-mH3K9ac/C2-ENCFF101KOM.chr19.fq.gz" \\
    --yes
 
'''

WF = {
    'default': {
        'wf_name': 'chip_seq',
        'wf_title': 'ChIP-seq',
        'wf_description': 'ENCODE ChIP-seq Analysis Pipeline',
        'run_idr': True
    },
    'histone': {
        'wf_name': 'histone_chip_seq',
        'wf_title': 'Histone ChIP-seq',
        'wf_description': 'ENCODE histone ChIP-seq Analysis Pipeline',
        'run_idr': False
    },
    'tf': {
        'wf_name': 'tf_chip_seq',
        'wf_title': 'TF ChIP-seq',
        'wf_description': 'ENCODE TF ChIP-seq Analysis Pipeline',
        'run_idr': True
    }
}

DEFAULT_APPLET_PROJECT = dxpy.WORKSPACE_ID
DEFAULT_OUTPUT_PROJECT = dxpy.WORKSPACE_ID
DEFAULT_OUTPUT_FOLDER = '/analysis_run'

MAPPING_APPLET_NAME = 'encode_bwa'
FILTER_QC_APPLET_NAME = 'filter_qc'
XCOR_APPLET_NAME = 'xcor'
XCOR_ONLY_APPLET_NAME = 'xcor_only'
SPP_APPLET_NAME = 'spp'
POOL_APPLET_NAME = 'pool'
PSEUDOREPLICATOR_APPLET_NAME = 'pseudoreplicator'
ENCODE_SPP_APPLET_NAME = 'encode_spp'
ENCODE_MACS2_APPLET_NAME = 'encode_macs2'
# IDR_APPLET_NAME='idr'
IDR2_APPLET_NAME = 'idr2'
ENCODE_IDR_APPLET_NAME = 'encode_idr'
OVERLAP_PEAKS_APPLET_NAME = 'overlap_peaks'

APPLETS = {}


def get_args():
    import argparse
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--target', help="ChIP target type (histone or tf)", required=True)
    parser.add_argument('--debug',   help="Print debug messages and hold jobs for ssh",                 default=False, action='store_true')
    parser.add_argument('--reference', help="Reference tar to map to")
    parser.add_argument('--chrom_sizes', help="chrom.sizes file for bedToBigBed")
    parser.add_argument('--genomesize', help="Genome size string for MACS2, e.g. mm or hs")
    parser.add_argument('--narrowpeak_as', help=".as file for bed to bigbed", default='ENCODE Reference Files:narrowPeak.as')
    parser.add_argument('--gappedpeak_as', help=".as file for bed to bigbed", default='ENCODE Reference Files:gappedPeak.as')
    parser.add_argument('--broadpeak_as', help=".as file for bed to bigbed", default='ENCODE Reference Files:broadPeak.as')
    parser.add_argument('--rep1',    help="Replicate 1 fastq or tagAlign",              default=None, nargs='*')
    parser.add_argument('--rep2',    help="Replicate 2 fastq or tagAlign",              default=None, nargs='*')
    parser.add_argument('--ctl1',    help="Control for replicate 1 fastq or tagAlign",  default=None, nargs='*')
    parser.add_argument('--ctl2',    help="Control for replicate 2 fastq or tagAlign",  default=None, nargs='*')
    parser.add_argument('--unary_control', help="Force one control for both reps", default=False, action='store_true')
    parser.add_argument('--outp',    help="Output project name or ID",          default=DEFAULT_OUTPUT_PROJECT)
    parser.add_argument('--outf',    help="Output folder name or ID",           default=DEFAULT_OUTPUT_FOLDER)
    parser.add_argument('--name',    help="Name for new workflow")
    parser.add_argument('--title',   help="Title for new workflow")
    parser.add_argument('--description',   help="Description for new workflow")    
    parser.add_argument('--applets', help="Name of project containing applets", default=DEFAULT_APPLET_PROJECT)
    parser.add_argument('--nomap',   help='Given tagAligns, skip to peak calling', default=False, action='store_true')
    parser.add_argument('--rep1pe', help='Specify if rep1 is PE (required only if --nomap)', type=bool, default=None)
    parser.add_argument('--rep2pe', help='Specify if rep2 is PE (required only if --nomap)', type=bool, default=None)
    parser.add_argument('--blacklist', help="Blacklist to filter IDR peaks")
    # parser.add_argument('--idr',     help='Report peaks with and without IDR analysis',                 default=False, action='store_true')
    # parser.add_argument('--idronly',  help='Only report IDR peaks', default=None, action='store_true')
    # parser.add_argument('--idrversion', help='Version of IDR to use (1 or 2)', default="2")
    parser.add_argument('--yes',     help='Run the workflow',                   default=False, action='store_true')

    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug
    if DEBUG:
        logging.basicConfig(
            format='%(levelname)s:%(message)s',
            level=logging.DEBUG)
        logging.debug("Debug logging ON")
    else:  # use the defaulf logging level
        logging.basicConfig(format='%(levelname)s:%(message)s')

    logging.debug("rep1 is: %s" % (args.rep1))

    if args.nomap and (args.rep1pe is None or args.rep2pe is None):
        logging.error("With --nomap, endedness of replicates must be specified with --rep1pe and --rep2pe")
        raise ValueError

    return args


def blank_workflow(args):
    return


def map_and_filter(infile, args):
    if not infile:
        return {None}
    stages = {None}
    return stages


def call_peaks(expvsctl, args):
    if not expvsctl:
        return {None}
    stages = {None}
    return stages


def resolve_project(identifier, privs='r'):
    project = dxpy.find_one_project(
        name=identifier,
        level='VIEW',
        name_mode='exact',
        return_handler=True,
        zero_ok=True)
    if project is None:
        try:
            project = dxpy.get_handler(identifier)
        except:
            logging.error(
                'Could not find a unique project with name or id %s'
                % (identifier))
            raise ValueError(identifier)
    logging.debug(
        'Project %s access level is %s'
        % (project.name, project.describe()['level']))
    if privs == 'w' and project.describe()['level'] == 'VIEW':
        logging.error('Output project %s is read-only' % (identifier))
        raise ValueError(identifier)
    return project


def resolve_folder(project, identifier):
    if not identifier.startswith('/'):
        identifier = '/' + identifier
    try:
        project_id = project.list_folder(identifier)
    except:
        try:
            project_id = project.new_folder(identifier, parents=True)
        except:
            logging.error(
                "Cannot create folder %s in project %s"
                % (identifier, project.name))
            raise ValueError('%s:%s' % (project.name, identifier))
        else:
            logging.info(
                "New folder %s created in project %s"
                % (identifier, project.name))
    return identifier


def resolve_file(identifier):
    logging.debug("resolve_file: %s" % (identifier))

    if not identifier:
        return None

    m = re.match(r'''^([\w\-\ \.]+):([\w\-\ /\.]+)''', identifier)
    if m:
        project_identifier = m.group(1)
        file_identifier = m.group(2)
    else:
        logging.debug("Defaulting to the current project")
        project_identifier = dxpy.WORKSPACE_ID
        file_identifier = identifier

    project = resolve_project(project_identifier)
    logging.debug("Got project %s" % (project.name))
    logging.debug("Now looking for file %s" % (file_identifier))

    m = re.match(r'''(^[\w\-\ /\.]+)/([\w\-\ \.]+)''', file_identifier)
    if m:
        folder_name = m.group(1)
        if not folder_name.startswith('/'):
            folder_name = '/' + folder_name
        recurse = False
        file_name = m.group(2)
    else:
        folder_name = '/'
        recurse = True
        file_name = file_identifier

    logging.debug(
        "Looking for file %s in folder %s" % (file_name, folder_name))

    try:
        file_handler = dxpy.find_one_data_object(
            name=file_name,
            folder=folder_name,
            project=project.get_id(),
            recurse=recurse,
            more_ok=False,
            zero_ok=False,
            return_handler=True)
    except dxpy.DXSearchError:
        logging.debug(
            '%s not found in project %s folder %s.  Trying as file ID'
            % (file_name, project.get_id(), folder_name))
        file_handler = None
    except:
        raise

    if not file_handler:
        try:
            file_handler = dxpy.DXFile(dxid=identifier, mode='r')
        except dxpy.DXError:
            logging.debug('%s not found as a dxid' % (identifier))
            logging.warning('Could not find file %s.' % (identifier))
            file_handler = None
        except:
            raise

    if file_handler:
        logging.info(
            "Resolved file identifier %s to %s"
            % (identifier, file_handler.get_id()))
        return file_handler
    else:
        logging.warning("Failed to resolve file identifier %s" % (identifier))
        return None


def find_applet_by_name(applet_name, applets_project_id):
    '''Looks up an applet by name in the project that holds tools.
      From Joe Dale's code.'''
    cached = '*'
    if (applet_name, applets_project_id) not in APPLETS:
        found = dxpy.find_one_data_object(
            classname="applet",
            name=applet_name,
            project=applets_project_id,
            zero_ok=False,
            more_ok=False,
            return_handler=True)
        APPLETS[(applet_name, applets_project_id)] = found
        cached = ''

    logging.info(
        cached + "Resolved applet %s to %s"
        % (applet_name, APPLETS[(applet_name, applets_project_id)].get_id()))
    return APPLETS[(applet_name, applets_project_id)]


def main():
    args = get_args()

    if not args.target:
        target_type = 'default'  # default
    else:
        target_type = args.target.lower()
    if target_type not in WF.keys():
        logging.error('Target type %s is not recognized')
        sys.exit(2)

    output_project = resolve_project(args.outp, 'w')
    logging.debug('Found output project %s' % (output_project.name))
    output_folder = resolve_folder(output_project, args.outf)
    logging.debug('Using output folder %s' % (output_folder))
    applet_project = resolve_project(args.applets, 'r')
    logging.debug('Found applet project %s' % (applet_project.name))

    workflow = dxpy.new_dxworkflow(
        name=args.name or WF[target_type]['wf_name'],
        title=args.title or WF[target_type]['wf_title'],
        description=args.description or WF[target_type]['wf_description'],
        project=output_project.get_id(),
        folder=output_folder)

    blank_workflow = not (args.rep1 or args.rep2 or args.ctl1 or args.ctl2)

    unary_control = args.unary_control or (args.rep1 and args.rep2 and args.ctl1 and not args.ctl2)

    if not args.genomesize:
        genomesize = None
    else:
        genomesize = args.genomesize
    if not args.chrom_sizes:
        chrom_sizes = None
    else:
        chrom_sizes = dxpy.dxlink(resolve_file(args.chrom_sizes))

    if not args.blacklist:
        blacklist = None
    else:
        blacklist = dxpy.dxlink(resolve_file(args.blacklist))

    run_idr = WF[target_type]['run_idr']

    if not args.nomap:
        # a "superstage" is just a dict with a name, name(s) of input files,
        # and then names and id's of stages that process that input
        # each superstage here could be implemented as a stage in a more
        # abstract workflow.  That stage would then call the various applets
        # that are separate
        # stages here.
        mapping_superstages = [  # the order of this list is important in that
            {'name': 'Rep1', 'input_args': args.rep1},
            {'name': 'Rep2', 'input_args': args.rep2},
            {'name': 'Ctl1', 'input_args': args.ctl1}
        ]
        if not unary_control:
            mapping_superstages.append(
                {'name': 'Ctl2', 'input_args': args.ctl2})

        mapping_applet = find_applet_by_name(
            MAPPING_APPLET_NAME, applet_project.get_id())
        # mapping_output_folder = resolve_folder(
        #     output_project, output_folder + '/' + mapping_applet.name)
        mapping_output_folder = mapping_applet.name
        reference_tar = resolve_file(args.reference)
        filter_qc_applet = find_applet_by_name(
            FILTER_QC_APPLET_NAME, applet_project.get_id())
        filter_qc_output_folder = mapping_output_folder
        xcor_applet = find_applet_by_name(
            XCOR_APPLET_NAME, applet_project.get_id())
        xcor_output_folder = mapping_output_folder

        # in the first pass create the mapping stage id's so we can use JBOR's
        # to link inputs
        for mapping_superstage in mapping_superstages:
            superstage_name = mapping_superstage.get('name')
            mapped_stage_id = workflow.add_stage(
                mapping_applet,
                name='Map %s' % (superstage_name),
                folder=mapping_output_folder
            )
            mapping_superstage.update({'map_stage_id': mapped_stage_id})

        # in the second pass populate the stage inputs and build other stages
        rep1_stage_id = next(ss.get('map_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep1')
        for mapping_superstage in mapping_superstages:
            superstage_name = mapping_superstage.get('name')
            superstage_id = mapping_superstage.get('map_stage_id')

            if mapping_superstage.get('input_args') or blank_workflow:
                mapping_stage_input = {}
                if superstage_name != "Rep1":
                    mapping_stage_input.update(
                        {'reference_tar': dxpy.dxlink(
                            {'stage': rep1_stage_id,
                             'inputField': 'reference_tar'})})
                else:
                    if args.reference:
                        mapping_stage_input.update(
                            {'reference_tar': dxpy.dxlink(
                                reference_tar.get_id())})
                if not blank_workflow:
                    for arg_index, input_arg in enumerate(mapping_superstage['input_args']): #read pairs assumed be in order read1,read2
                        reads = dxpy.dxlink(resolve_file(input_arg).get_id())
                        mapping_stage_input.update({'reads%d' %(arg_index+1): reads})
                # this is now done in the first pass loop above
                # mapped_stage_id = workflow.add_stage(
                #     mapping_applet,
                #     name='Map %s' %(superstage_name),
                #     folder=mapping_output_folder,
                #     stage_input=mapping_stage_input
                # )
                # mapping_superstage.update({'map_stage_id': mapped_stage_id})
                workflow.update_stage(superstage_id, stage_input=mapping_stage_input)

                filter_qc_stage_id = workflow.add_stage(
                    filter_qc_applet,
                    name='Filter_QC %s' %(superstage_name),
                    folder=filter_qc_output_folder,
                    stage_input={
                        'input_bam': dxpy.dxlink({'stage': superstage_id, 'outputField': 'mapped_reads'}),
                        'paired_end': dxpy.dxlink({'stage': superstage_id, 'outputField': 'paired_end'})
                    }
                )
                mapping_superstage.update({'filter_qc_stage_id': filter_qc_stage_id})

                xcor_stage_id = workflow.add_stage(
                    xcor_applet,
                    name='Xcor %s' %(superstage_name),
                    folder=xcor_output_folder,
                    stage_input={
                        'input_bam': dxpy.dxlink({'stage': filter_qc_stage_id, 'outputField': 'filtered_bam'}),
                        'paired_end': dxpy.dxlink({'stage': filter_qc_stage_id, 'outputField': 'paired_end'})
                    }
                )
                mapping_superstage.update({'xcor_stage_id': xcor_stage_id})

        exp_rep1_ta = dxpy.dxlink(
                    {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep1'),
                     'outputField': 'tagAlign_file'})
        exp_rep1_cc = dxpy.dxlink(
                    {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep1'),
                     'outputField': 'CC_scores_file'})
        exp_rep2_ta = dxpy.dxlink(
                    {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep2'),
                     'outputField': 'tagAlign_file'})
        exp_rep2_cc = dxpy.dxlink(
                    {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep2'),
                     'outputField': 'CC_scores_file'})
        ctl_rep1_ta = dxpy.dxlink(
                    {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Ctl1'),
                     'outputField': 'tagAlign_file'})
        if unary_control:
            ctl_rep2_ta = ctl_rep1_ta
        else:
            ctl_rep2_ta = dxpy.dxlink(
                        {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Ctl2'),
                         'outputField': 'tagAlign_file'})
        rep1_paired_end = dxpy.dxlink(
                        {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep1'),
                         'outputField': 'paired_end'})
        rep2_paired_end = dxpy.dxlink(
                        {'stage': next(ss.get('xcor_stage_id') for ss in mapping_superstages if ss['name'] == 'Rep2'),
                         'outputField': 'paired_end'})
    else: #skipped the mapping, so just bring in the inputs from arguments
        exp_rep1_ta = dxpy.dxlink(resolve_file(args.rep1[0]).get_id())
        exp_rep2_ta = dxpy.dxlink(resolve_file(args.rep2[0]).get_id())
        ctl_rep1_ta = dxpy.dxlink(resolve_file(args.ctl1[0]).get_id())
        ctl_rep2_ta = dxpy.dxlink(resolve_file(args.ctl2[0]).get_id())
        rep1_paired_end = args.rep1pe
        rep2_paired_end = args.rep2pe

        #here we need to calculate the cc scores files, because we're only being supplied tagAligns
        #if we had mapped everything above we'd already have a handle to the cc file
        xcor_only_applet = find_applet_by_name(XCOR_ONLY_APPLET_NAME, applet_project.get_id())
        # xcor_output_folder = resolve_folder(output_project, output_folder + '/' + xcor_only_applet.name)
        xcor_output_folder = xcor_only_applet.name
        xcor_only_stages = []

        exp_rep1_cc_stage_id = workflow.add_stage(
            xcor_only_applet,
            name="Rep1 cross-correlation",
            folder=xcor_output_folder,
            stage_input={
                'input_tagAlign': exp_rep1_ta,
                'paired_end': rep1_paired_end
            }
        )
        xcor_only_stages.append({'xcor_only_rep1_id': exp_rep1_cc_stage_id})
        exp_rep1_cc = dxpy.dxlink(
                    {'stage': exp_rep1_cc_stage_id,
                     'outputField': 'CC_scores_file'})

        exp_rep2_cc_stage_id = workflow.add_stage(
            xcor_only_applet,
            name="Rep2 cross-correlation",
            folder=xcor_output_folder,
            stage_input={
                'input_tagAlign': exp_rep2_ta,
                'paired_end': rep2_paired_end
            }
        )
        xcor_only_stages.append({'xcor_only_rep2_id': exp_rep2_cc_stage_id})
        exp_rep2_cc = dxpy.dxlink(
                    {'stage': exp_rep2_cc_stage_id,
                     'outputField': 'CC_scores_file'})

    encode_macs2_applet = find_applet_by_name(ENCODE_MACS2_APPLET_NAME, applet_project.get_id())
    encode_macs2_stages = []
    # peaks_output_folder = resolve_folder(output_project, output_folder + '/' + encode_macs2_applet.name)
    peaks_output_folder = encode_macs2_applet.name

    macs2_stage_input = {
            'rep1_ta' : exp_rep1_ta,
            'rep2_ta' : exp_rep2_ta,
            'ctl1_ta': ctl_rep1_ta,
            'ctl2_ta' : ctl_rep2_ta,
            'rep1_xcor' : exp_rep1_cc,
            'rep2_xcor' : exp_rep2_cc,
            'rep1_paired_end': rep1_paired_end,
            'rep2_paired_end': rep2_paired_end,
            'narrowpeak_as': dxpy.dxlink(resolve_file(args.narrowpeak_as)),
            'gappedpeak_as': dxpy.dxlink(resolve_file(args.gappedpeak_as)),
            'broadpeak_as':  dxpy.dxlink(resolve_file(args.broadpeak_as))
        }
    if genomesize:
        macs2_stage_input.update({'genomesize': genomesize})
    if chrom_sizes:
        macs2_stage_input.update({'chrom_sizes': chrom_sizes})
    encode_macs2_stage_id = workflow.add_stage(
        encode_macs2_applet,
        name='ENCODE Peaks',
        folder=peaks_output_folder,
        stage_input=macs2_stage_input
        )
    encode_macs2_stages.append({'name': 'ENCODE Peaks', 'stage_id': encode_macs2_stage_id})

    if run_idr:
        encode_spp_applet = find_applet_by_name(ENCODE_SPP_APPLET_NAME, applet_project.get_id())
        encode_spp_stages = []
        # idr_peaks_output_folder = resolve_folder(output_project, output_folder + '/' + encode_spp_applet.name)
        idr_peaks_output_folder = encode_spp_applet.name
        PEAKS_STAGE_NAME = 'SPP Peaks'
        peaks_stage_input = {
                    'rep1_ta' : exp_rep1_ta,
                    'rep2_ta' : exp_rep2_ta,
                    'ctl1_ta': ctl_rep1_ta,
                    'ctl2_ta' : ctl_rep2_ta,
                    'rep1_xcor' : exp_rep1_cc,
                    'rep2_xcor' : exp_rep2_cc,
                    'rep1_paired_end': rep1_paired_end,
                    'rep2_paired_end': rep2_paired_end,
                    'as_file': dxpy.dxlink(resolve_file(args.narrowpeak_as)),
                    'idr_peaks': True
                    }
        if chrom_sizes:
            peaks_stage_input.update({'chrom_sizes': chrom_sizes})
        else:
            peaks_stage_input.update({'chrom_sizes': dxpy.dxlink({'stage': encode_macs2_stage_id, 'inputField': 'chrom_sizes'})})

        encode_spp_stage_id = workflow.add_stage(
            encode_spp_applet,
            name=PEAKS_STAGE_NAME,
            folder=idr_peaks_output_folder,
            stage_input=peaks_stage_input
            )
        encode_spp_stages.append({'name': PEAKS_STAGE_NAME, 'stage_id': encode_spp_stage_id})

        idr_applet = find_applet_by_name(IDR2_APPLET_NAME, applet_project.get_id())
        encode_idr_applet = find_applet_by_name(ENCODE_IDR_APPLET_NAME, applet_project.get_id())
        idr_stages = []
        # idr_output_folder = resolve_folder(output_project, output_folder + '/' + idr_applet.name)
        idr_output_folder = idr_applet.name
        if (args.rep1 and args.ctl1 and args.rep2) or blank_workflow:
            idr_stage_id = workflow.add_stage(
                idr_applet,
                name='IDR True Replicates',
                folder=idr_output_folder,
                stage_input={
                    'rep1_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep1_peaks'}),
                    'rep2_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep2_peaks'}),
                    'pooled_peaks': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'pooled_peaks'})
                }
            )
            idr_stages.append({'name': 'IDR True Replicates', 'stage_id': idr_stage_id})

            idr_stage_id = workflow.add_stage(
                idr_applet,
                name='IDR Rep 1 Self-pseudoreplicates',
                folder=idr_output_folder,
                stage_input={
                    'rep1_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep1pr1_peaks'}),
                    'rep2_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep1pr2_peaks'}),
                    'pooled_peaks': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep1_peaks'})
                }
            )
            idr_stages.append({'name': 'IDR Rep 1 Self-pseudoreplicates', 'stage_id': idr_stage_id})

            idr_stage_id = workflow.add_stage(
                idr_applet,
                name='IDR Rep 2 Self-pseudoreplicates',
                folder=idr_output_folder,
                stage_input={
                    'rep1_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep2pr1_peaks'}),
                    'rep2_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep2pr2_peaks'}),
                    'pooled_peaks': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'rep2_peaks'})
                }
            )
            idr_stages.append({'name': 'IDR Rep 2 Self-pseudoreplicates', 'stage_id': idr_stage_id})

            idr_stage_id = workflow.add_stage(
                idr_applet,
                name='IDR Pooled Pseudoreplicates',
                folder=idr_output_folder,
                stage_input={
                    'rep1_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'pooledpr1_peaks'}),
                    'rep2_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'pooledpr2_peaks'}),
                    'pooled_peaks': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_spp_stages if ss['name'] == PEAKS_STAGE_NAME),
                         'outputField': 'pooled_peaks'})
                }
            )
            idr_stages.append({'name': 'IDR Pooled Pseudoreplicates', 'stage_id': idr_stage_id})

            final_idr_stage_input = {
                    'reps_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in idr_stages if ss['name'] == 'IDR True Replicates'),
                         'outputField': 'IDR_peaks'}),
                    'r1pr_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in idr_stages if ss['name'] == 'IDR Rep 1 Self-pseudoreplicates'),
                         'outputField': 'IDR_peaks'}),
                    'r2pr_peaks' : dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in idr_stages if ss['name'] == 'IDR Rep 2 Self-pseudoreplicates'),
                         'outputField': 'IDR_peaks'}),
                    'pooledpr_peaks': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in idr_stages if ss['name'] == 'IDR Pooled Pseudoreplicates'),
                         'outputField': 'IDR_peaks'}),
                    'as_file': dxpy.dxlink(resolve_file(args.narrowpeak_as)),
                    'rep1_signal': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                         'outputField': 'rep1_fc_signal'}),
                    'rep2_signal': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                         'outputField': 'rep2_fc_signal'}),
                    'pooled_signal': dxpy.dxlink(
                        {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                         'outputField': 'pooled_fc_signal'})
                }
            if blacklist:
                final_idr_stage_input.update({'blacklist': blacklist})
            if chrom_sizes:
                final_idr_stage_input.update({'chrom_sizes': chrom_sizes})
            else:
                final_idr_stage_input.update({'chrom_sizes': dxpy.dxlink({'stage': encode_spp_stage_id, 'inputField': 'chrom_sizes'})})

            idr_stage_id = workflow.add_stage(
                encode_idr_applet,
                name='Final IDR peak calls',
                folder=idr_output_folder,
                stage_input=final_idr_stage_input,

            )
            idr_stages.append({'name': 'Final IDR peak calls', 'stage_id': idr_stage_id})

    if target_type == 'histone':
        overlap_peaks_applet = find_applet_by_name(OVERLAP_PEAKS_APPLET_NAME, applet_project.get_id())
        overlap_peaks_stages = []
        for peaktype in ['narrowpeaks', 'gappedpeaks', 'broadpeaks']:

            if peaktype == 'narrowpeaks':
                as_file = dxpy.dxlink(resolve_file(args.narrowpeak_as))
                peak_type_extension = 'narrowPeak'

            elif peaktype == 'gappedpeaks':
                as_file = dxpy.dxlink(resolve_file(args.gappedpeak_as))
                peak_type_extension = 'gappedPeak'

            elif peaktype == 'broadpeaks':
                as_file = dxpy.dxlink(resolve_file(args.broadpeak_as))
                peak_type_extension = 'broadPeak'

            overlap_peaks_stage_input = {
                'rep1_peaks': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'rep1_%s' %(peaktype)}),
                'rep2_peaks': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'rep2_%s' %(peaktype)}),
                'pooled_peaks': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'pooled_%s' %(peaktype)}),
                'pooledpr1_peaks': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'pooledpr1_%s' %(peaktype)}),
                'pooledpr2_peaks': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'pooledpr2_%s' %(peaktype)}),
                'as_file': as_file,
                'peak_type': peak_type_extension,
                'prefix': 'final',
                'rep1_signal': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'rep1_fc_signal'}),
                'rep2_signal': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'rep2_fc_signal'}),
                'pooled_signal': dxpy.dxlink(
                    {'stage': next(ss.get('stage_id') for ss in encode_macs2_stages if ss['name'] == 'ENCODE Peaks'),
                     'outputField': 'pooled_fc_signal'})
            }
            if chrom_sizes:
                overlap_peaks_stage_input.update({'chrom_sizes': chrom_sizes})
            else:
                overlap_peaks_stage_input.update({'chrom_sizes': dxpy.dxlink({'stage': encode_macs2_stage_id, 'inputField': 'chrom_sizes'})})

            overlap_peaks_stage_id = workflow.add_stage(
                overlap_peaks_applet,
                name='Final %s' %(peaktype),
                folder=peaks_output_folder,
                stage_input=overlap_peaks_stage_input
            )
            overlap_peaks_stages.append({'name': 'Final %s' %(peaktype), 'stage_id': overlap_peaks_stage_id})

    if args.yes:
        if args.debug:
            job_id = workflow.run({}, folder=output_folder, priority='high', debug={'debugOn': ['AppInternalError', 'AppError']}, delay_workspace_destruction=True, allow_ssh=['255.255.255.255'])
        else:
            job_id = workflow.run({}, folder=output_folder, priority='high')
        logging.info("Running as job %s" %(job_id))

if __name__ == '__main__':
    main()
