import os
import shutil
import glob
import csv
from Sequence_File import SequencePair
from Utilities import UtilityMethods
from RedmineAPI import Utilities


class MassExtractor(object):

    def __init__(self, nas_mnt):
        self.missing = list()
        self.nas_mnt = nas_mnt
        self.seqid_rows = list()
        self.generic_sample_sheet_path = ""
        self.seqid_mounted_path = ""

        self.extractor_timelog = Utilities.create_time_log('extractor_logs')

    def move_files(self, sequences_info, outputfolder):
        """
        The main method that processes the inputs from Redmine and completes the task of moving the files to the mounted
        drive by running a series of tasks
        :param sequences_info: List of inputted Sequence_Info objects that will be used inplace of a text line
        :param outputfolder: The folder path on the drive where the folder from the nas must be moved to
        :return: Any files that could not be found on the nas 
        """

        if sequences_info is None:
            raise ValueError('No input files were found.')

        self.extractor_timelog.time_print("Retrieving  fastqs and other relevant files...")
        self.extractor_timelog.time_print("Found information about %d SEQID pairs to "
                                          "move to the drive..." % (len(sequences_info)))
        # The SEQ-IDs need to be places in a specific directory for the irida uploader to work
        self.seqid_mounted_path = os.path.join(outputfolder, "Data/Intensities/BaseCalls")
        # Create the directory if it does not exist
        UtilityMethods.create_dir(basepath=self.seqid_mounted_path)

        completed_counter = 0
        for sequence in sequences_info:
            completed_counter += 1
            self.extractor_timelog.time_print("Currently moving %d of %d sets of files for - %s"
                                              % (completed_counter, len(sequences_info), sequence.sample_name))
            # Create a SequencePair object that will store all relevant paths
            sequence_pair = SequencePair(sequence_info=sequence)
            # Set the path to check depending on the SEQ-ID abbreviation used to speed up the process
            if 'SEQ' in sequence.sample_name:
                path_to_check = os.path.join(self.nas_mnt, 'MiSeq_Backup', '*', '*.fastq.gz')
            elif 'OLF' in sequence.sample_name:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*', '*.fastq.gz')
            elif 'MER' in sequence.sample_name:
                path_to_check = os.path.join(self.nas_mnt, 'merge_Backup', '*.fastq.gz')
            else:
                path_to_check = os.path.join(self.nas_mnt, 'External_MiSeq_Backup', '*', '*', '*.fastq.gz')

            for path in glob.iglob(path_to_check):
                if sequence.sample_name in path:

                    # Add a the path of the sequence to the object
                    sequence_pair.add_nas_seqid_path(seqid_path=path)

                    # If no SampleSheet associated with the fastq pair then add one
                    if sequence_pair.nas_sample_sheet_path is None:
                        sequence_pair.add_sample_sheet(path.split(sequence.sample_name)[0])
                    # If both of the pair are found then exit the search
                    if sequence_pair.both_exist:
                        break
            # Move the files for the sequence pair to the drive and add their SampleSheet data to list
            self.mount_seqid_files(sequence_pair)
            self.add_seqid_csv_data(sequence_pair)
        # Mount the generic SampleSheet and then append it will the new information
        self.mount_generic_samplesheet(outputfolder)
        self.append_generic_csv(self.generic_sample_sheet_path)
        self.extractor_timelog.time_print("Completed moving the requested files to the drive.")

        return self.missing

    def add_seqid_csv_data(self, sequence_pair):
        """
        For each pair of sequence pair, add their data into the generic SampleSheet that will be moved to the drive 
        and used for the upload. For regular pairs, open their SampleSheet row that is logged on the nas and change it
        according to the inputted parameters. Next append it to the list that will be used to populate the 
        generic sheet.
        For MER sequence a custom row must be created from scratch since there are no SampleSheets for them on the nas
        :param sequence_pair: All information for a pair of SEQ-IDs
        """

        if "MER" in sequence_pair.seqid_info.sample_name:
            # Use custom parameters to be put in the SampleSheet for MER sequences
            self.seqid_rows.append(self.get_default_merge_sequence_row(sequence_pair))
        else:
            nas_csv_samplesheet = sequence_pair.nas_sample_sheet_path
            delimiter = ','
            # Open the SampleSheet for the sequence on the nas
            with open(nas_csv_samplesheet, 'r') as input_file:
                reader = csv.reader(input_file, delimiter=delimiter)
                for row in reader:
                    if len(row) > 8:  # incase of improper formatted row
                        # Search through the rows until the sample name is found in the first row of the SampleSheet
                        if sequence_pair.seqid_info.sample_name in row[0]:
                            row[0] = sequence_pair.seqid_info.sample_id   # Change the Sample_Name in the csv to the Sample ID
                            row[1] = sequence_pair.seqid_info.sample_id  # Change the Sample_ID in the csv to the input Sample ID
                            row[8] = sequence_pair.seqid_info.sample_project  # Change Sample_Project in the csv to the input
                            row[9] = sequence_pair.seqid_info.sample_name  # Change the description in the csv to the Sample Name

                            # If the length of the row is longer than the template, delete the extra columns
                            if len(row) > 10:
                                i = 10 - len(row)
                                del row[i:]
                            # Add the row to the list
                            self.seqid_rows.append(row)
                            break

    @ staticmethod
    def get_default_merge_sequence_row(sequence_pair):
        """
        Return the default row of data to be inputted into the data sheet for all merge type sequences 
        :param sequence_pair: All information for a pair of SEQ-IDs
        """
        return [sequence_pair.seqid_info.sample_id,  # Sample ID
                      sequence_pair.seqid_info.sample_id,  # Sample Name
                      "",  # Sample Plate
                      "",  # Sample Well
                      "na",  # I7 Index ID
                      "na",  # index
                      "na",  # I5 Index ID
                      "na",  # index2
                      sequence_pair.seqid_info.sample_project,  # Sample Project
                      sequence_pair.seqid_info.sample_name]  # Description

    def append_generic_csv(self, sample_sheet_path):
        """
        Add the rows from the different SampleSheets on the nas to the generic SampleSheet
        :param sample_sheet_path: Path of the default SampleSheet in the local folder
        """
        delimiter = ','
        with open(sample_sheet_path, 'a') as output_file:
            append = csv.writer(output_file, delimiter=delimiter)
            for row in self.seqid_rows:
                append.writerow(row)

    def mount_seqid_files(self, sequence_pair):
        """
        Put the sequence pair referenced in the sequence_files onto the drive - with specific path 
        "drivepath/Data/Intensities/BaseCalls"
        :param sequence_pair: All information for a pair of SEQ-IDs
        """
        for path in sequence_pair.seqid_paths:
            try:
                # Check if the file is R1 or R2
                sample_type = "_R1"
                if "R2" in path:
                    sample_type = "_R2"

                # Path the file will be copied to on the drive
                # Needs the extra string parameters to be recognized by the irida uploader
                mounted_path = os.path.join(self.seqid_mounted_path, sequence_pair.seqid_info.sample_id + "_S1_L001"
                                            + sample_type + "_001" + ".fastq.gz")

                self.extractor_timelog.time_print("Copying the file %s to %s" % (path, mounted_path))
                shutil.copy(path, mounted_path)
            except TypeError as e:
                # If one of the files cannot be copied over due to an error, add it to the missing files lsit
                self.extractor_timelog.time_print("One of the pairs of %s, was not copied from the path %s to %s"
                                                  % (sequence_pair.seqid_info.sample_name, path,
                                                     self.seqid_mounted_path))
                self.missing.append(sequence_pair.seqid_info.sample_name)

    def mount_generic_samplesheet(self, outputfolder):
        """
        Put the generic SampleSheet on the drive in the root folder
        :param outputfolder: Root folder on the drive where the Redmine request is to be placed
        """
        # Create the directory and the make path to place the SampleSample sheet on the drive
        UtilityMethods.create_dir(basepath=outputfolder)
        self.generic_sample_sheet_path = os.path.join(outputfolder, 'SampleSheet.csv')

        # Re-create the path for the local generic SampleSheet
        local_dir_path = os.path.dirname(os.path.realpath(__file__))
        local_generic_samplesheet_path = os.path.join(local_dir_path, 'SampleSheet.csv')

        self.extractor_timelog.time_print("Copying the generic SampleSheet from %s to %s"
                                          % (self.generic_sample_sheet_path, local_generic_samplesheet_path))
        # Copy the local SampleSheet onto the drive in the new location
        shutil.copy(local_generic_samplesheet_path, self.generic_sample_sheet_path)
