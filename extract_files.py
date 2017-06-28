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

        # TODO fix this so it looks for seq_id of the file right away
        UtilityMethods.create_dir(self.script_dir, 'extractor_logs')
        self.extractor_timelog = UtilityMethods.create_timerlog(self.script_dir, 'extractor_logs')
        self.extractor_timelog.set_colour(32)

    def move_files(self, inputs):

        if inputs is None:
            raise ValueError('No input files were found.')

        outfolder = inputs['outputfolder']
        sequences = inputs['fastqs']
        completed_counter = 0
        path_to_check = ""

        self.extractor_timelog.time_print("Retrieving  fastqs and other relevant files...")

        self.extractor_timelog.time_print("Found information about %d SEQID pairs to "
                                          "move to the drive..." % (len(sequences)))

        for sequence in sequences:
            completed_counter += 1
            self.extractor_timelog.time_print("Currently moving %d of %d sets of files for - %s"
                                              % (completed_counter, len(sequences), sequence.seq_id))

            file = Sequence(sequence_info=sequence, output_folder=outfolder)
            run_date = None

            if 'SEQ' in sequence.seq_id:
                path_to_check = os.path.join(self.nas_mnt, 'MiSeq_Backup', '*', '*.fastq.gz')
            else:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*.fastq.gz')

            for path in glob.iglob(path_to_check):
                if sequence.seq_id in os.path.split(path)[1].split('_')[0]:

                    temp = path.split(sequence.seq_id)[0]
                    run_date = temp.split('/')[-2]

                    file.add_run_date(run_date)
                    file.add_nas_seqid_path(path=path)
                    file.add_mounted_folders_paths()

                    if file.nas_sample_sheet_path is None:
                        file.add_sample_sheet(path.split(sequence.seq_id)[0])

                    if file.both_exist:
                        break

            self.mount_seqid_files(file)

            # create the sample sheet if it does not already exist for that date
            if not os.path.exists(os.path.join(file.sample_sheet_mounted_folder, 'SampleSheet.csv')):
                self.create_csv(file, False)

            # append the sample sheet if it does exist for that date
            elif os.path.exists(os.path.join(file.sample_sheet_mounted_folder, 'SampleSheet.csv')):
                self.create_csv(file, True)

                # TODO throw an error

        return self.missing

    def create_csv(self, file, append):

        nas_csv_samplesheet = file.nas_sample_sheet_path
        mounted_csv_samplesheet = file.sample_sheet_mounted_path
        delimiter = ','
        found = False
        with open(nas_csv_samplesheet, 'r') as input_file:
            reader = csv.reader(input_file, delimiter=delimiter)

            if append is False:
                with open(mounted_csv_samplesheet, 'w') as output_file:
                    writer = csv.writer(output_file, delimiter=delimiter)
                    for row in reader:
                        if 'Sample_ID' in row[0] and found is False:
                            writer.writerow(row)
                            found = True
                        elif found is True:
                            if file.seqid_info.seq_id in row[0]:
                                row[1] = file.seqid_info.sample_name  # Change the Sample_name in the csv to the input
                                row[8] = file.seqid_info.project_num  # Change Sample_Project in the csv to the input
                                row[9] = file.seqid_info.description  # Change the description in the csv to the input
                                writer.writerow(row)
                                # self.seqid_rows.append(row)
                        else:
                            writer.writerow(row)
            else:
                with open(mounted_csv_samplesheet, 'a') as output_file:
                    append = csv.writer(output_file, delimiter=delimiter)
                    for row in reader:
                        if file.seqid_info.seq_id in row[0]:
                            row[1] = file.seqid_info.sample_name  # Change the Sample_name in the csv to the input
                            row[8] = file.seqid_info.project_num  # Change Sample_Project in the csv to the input
                            row[9] = file.seqid_info.description  # Change the description in the csv to the input
                            append.writerow(row)
                            # self.seqid_rows.append(row)

    def mount_seqid_files(self, file):
        if not os.path.exists(file.seqid_mounted_folder):
            # makes the output directory if it doesn't exist
            os.makedirs(file.seqid_mounted_folder)

        for path in file.seqid_paths:
            shutil.copy(path, file.seqid_mounted_folder)
