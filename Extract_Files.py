import sys
import os
import shutil
import glob
import csv

from RedmineAPI.RedmineUtilities import create_timerlog

from Sequence_File import Sequence
from Utilities import UtilityMethods


class MassExtractor(object):

    def __init__(self, nas_mnt):
        self.missing = list()
        self.script_dir = sys.path[0]
        self.nas_mnt = nas_mnt
        self.seqid_rows = list()
        self.generic_sample_sheet_path = ""
        self.seqid_mounted_path = ""

        UtilityMethods.create_dir(self.script_dir, 'extractor_logs')
        self.extractor_timelog = create_timerlog(self.script_dir, 'extractor_logs')
        self.extractor_timelog.set_colour(32)

    def move_files(self, sequences, outputfolder):

        if sequences is None:
            raise ValueError('No input files were found.')

        self.extractor_timelog.time_print("Retrieving  fastqs and other relevant files...")
        self.extractor_timelog.time_print("Found information about %d SEQID pairs to "
                                          "move to the drive..." % (len(sequences)))
        self.seqid_mounted_path = os.path.join(outputfolder, "Data/Intensities/BaseCalls")

        path_to_check = ""
        completed_counter = 0
        for sequence in sequences:
            completed_counter += 1
            self.extractor_timelog.time_print("Currently moving %d of %d sets of files for - %s"
                                              % (completed_counter, len(sequences), sequence.sample_name))

            file = Sequence(sequence_info=sequence)
            run_date = None

            if 'SEQ' in sequence.sample_name:
                path_to_check = os.path.join(self.nas_mnt, 'MiSeq_Backup', '*', '*.fastq.gz')
            elif 'OLF' in sequence.sample_name:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*', '*.fastq.gz')
            else:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*.fastq.gz')

            for path in glob.iglob(path_to_check):
                if sequence.sample_name in path:

                    file.add_nas_seqid_path(path=path)

                    # if no samplesheet associated with the fastq pair then add one
                    if file.nas_sample_sheet_path is None:
                        file.add_sample_sheet(path.split(sequence.sample_name)[0])

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
                if len(row) > 8:  # incase of improper formatted row
                    if file.seqid_info.sample_name in row[0]:
                        row[0] = file.seqid_info.sample_id  # Change the Sample_ID in the csv to the input
                        row[1] = file.seqid_info.sample_name   # Change the Sample_Name in the csv to the input
                        row[8] = file.seqid_info.sample_project  # Change Sample_Project in the csv to the input
                        row[9] = ""  # Change the description in the csv to nothing

                        # if the length of the row is longer than the template, delete the extra columns
                        if len(row) > 10:
                            i = 10 - len(row)
                            del row[i:]

                        self.seqid_rows.append(row)
                        break

    def append_generic_csv(self, sample_sheet_p):
        delimiter = ','
        with open(sample_sheet_p, 'a') as output_file:
            append = csv.writer(output_file, delimiter=delimiter)
            for row in self.seqid_rows:
                append.writerow(row)

    def mount_seqid_files(self, file):
        UtilityMethods.create_dir(basepath=self.seqid_mounted_path)

        for path in file.seqid_paths:
            try:
                self.extractor_timelog.time_print("Copying the file %s to %s" % (path, self.seqid_mounted_path))
                shutil.copy(path, self.seqid_mounted_path)
            except TypeError as e:
                self.extractor_timelog.time_print("One of that pairs of %s, was not copied from the path %s to %s"
                                                  % (file.seqid_info.sample_name, path, self.seqid_mounted_path))
                self.missing.append(file.seqid_info.sample_name)

    def mount_generic_samplesheet(self, outputfolder):

        UtilityMethods.create_dir(basepath=outputfolder)
        self.generic_sample_sheet_path = os.path.join(outputfolder, 'SampleSheet.csv')
        local_dir_path = os.path.dirname(os.path.realpath(__file__))
        local_generic_samplesheet_path = os.path.join(local_dir_path, 'SampleSheet.csv')

        self.extractor_timelog.time_print("Copying the generic SampleSheet from %s to %s"
                                          % (self.generic_sample_sheet_path, local_generic_samplesheet_path))
        shutil.copy(local_generic_samplesheet_path, self.generic_sample_sheet_path)
