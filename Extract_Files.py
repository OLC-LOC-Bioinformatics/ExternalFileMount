import sys
import os
import shutil
import glob
import csv
from Sequence_File import Sequence
from Utilities import UtilityMethods


class MassExtractor(object):

    def __init__(self, nas_mnt):
        self.missing = list()
        self.script_dir = sys.path[0]
        self.nas_mnt = nas_mnt
        self.seqid_rows = list()
        self.generic_sample_sheet_path = ""

        UtilityMethods.create_dir(self.script_dir, 'extractor_logs')
        self.extractor_timelog = UtilityMethods.create_timerlog(self.script_dir, 'extractor_logs')
        self.extractor_timelog.set_colour(32)

    def move_files(self, sequences, outputfolder):

        if sequences is None:
            raise ValueError('No input files were found.')

        self.extractor_timelog.time_print("Retrieving  fastqs and other relevant files...")
        self.extractor_timelog.time_print("Found information about %d SEQID pairs to "
                                          "move to the drive..." % (len(sequences)))

        path_to_check = ""
        completed_counter = 0
        for sequence in sequences:
            completed_counter += 1
            self.extractor_timelog.time_print("Currently moving %d of %d sets of files for - %s"
                                              % (completed_counter, len(sequences), sequence.seq_id))

            file = Sequence(sequence_info=sequence, output_folder=outputfolder)
            run_date = None

            if 'SEQ' in sequence.seq_id:
                path_to_check = os.path.join(self.nas_mnt, 'MiSeq_Backup', '*', '*.fastq.gz')
            elif 'OLF' in sequence.seq_id:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*', '*.fastq.gz')
            else:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*.fastq.gz')

            for path in glob.iglob(path_to_check):
                if sequence.seq_id in path:

                    temp = path.split(sequence.seq_id)[0]
                    run_date = temp.split('/')[-2]

                    file.add_run_date(run_date)
                    file.add_nas_seqid_path(path=path)
                    file.add_mounted_folders_paths()

                    # if no samplesheet associated with the fastq pair then add one
                    if file.nas_sample_sheet_path is None:
                        file.add_sample_sheet(path.split(sequence.seq_id)[0])

                    if file.both_exist:
                        break

            self.mount_seqid_files(file)
            self.add_seqid_csv_data(file)

        self.mount_generic_samplesheet(outputfolder)
        self.append_generic_csv(self.generic_sample_sheet_path)
        self.extractor_timelog.time_print("Completed moving the requested files to the drive.")

        return self.missing

    def add_seqid_csv_data(self, file):
        nas_csv_samplesheet = file.nas_sample_sheet_path
        delimiter = ','
        with open(nas_csv_samplesheet, 'r') as input_file:
            reader = csv.reader(input_file, delimiter=delimiter)
            for row in reader:
                if len(row) > 8:  # incase of a non existent row
                    if file.seqid_info.seq_id in row[0]:
                        row[1] = file.seqid_info.sample_name  # Change the Sample_name in the csv to the input
                        row[8] = file.seqid_info.project_num  # Change Sample_Project in the csv to the input
                        row[9] = file.seqid_info.description  # Change the description in the csv to the input
                        self.seqid_rows.append(row)
                        break

    def append_generic_csv(self, sample_sheet_p):
        delimiter = ','
        with open(sample_sheet_p, 'a') as output_file:
            append = csv.writer(output_file, delimiter=delimiter)
            for row in self.seqid_rows:
                append.writerow(row)

    def mount_seqid_files(self, file):
        UtilityMethods.create_dir(basepath=file.seqid_mounted_folder)

        for path in file.seqid_paths:
            try:
                self.extractor_timelog.time_print("Copying the file %s to %s" % (path, file.seqid_mounted_folder))
                shutil.copy(path, file.seqid_mounted_folder)
            except TypeError as e:
                self.extractor_timelog.time_print("One of that pairs of %s, was not copied from the path %s to %s"
                                                  % (file.seqid_info.seq_id, path, file.seqid_mounted_folder))
                self.missing.append(file.seqid_info.seq_id)

    def mount_generic_samplesheet(self, outputfolder):

        UtilityMethods.create_dir(basepath=outputfolder)
        self.generic_sample_sheet_path = os.path.join(outputfolder, 'SampleSheet.csv')
        local_dir_path = os.path.dirname(os.path.realpath(__file__))
        local_generic_samplesheet_path = os.path.join(local_dir_path, 'SampleSheet.csv')

        self.extractor_timelog.time_print("Copying the generic SampleSheet from %s to %s"
                                          % (self.generic_sample_sheet_path, local_generic_samplesheet_path))
        shutil.copy(local_generic_samplesheet_path, self.generic_sample_sheet_path)
