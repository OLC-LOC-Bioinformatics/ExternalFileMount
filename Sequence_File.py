import os

class Sequence:

    csv_sheet = 'SampleSheet.csv'
    bak_sheet = 'SampleSheet.bak2'
    seq_folder_structure = "Data/Intensities/BaseCalls"

    def __init__(self, sequence_info, output_folder):

        self.seqid_paths = list()  # list has a maximum size of 2 SEQ-IDs (R1 & R2 pair)
        self.seqid_info = sequence_info  # info given through the text document on Redmine
        self.mounted_base_path = output_folder  # path of the mounted dirve
        self.nas_sample_sheet_path = None  # path to the sample sheet in the nas
        self.both_exist = False  # flag when a pair of SEQ-ID are found
        self.run_date = "01012000"
        self.csv_file = True

        # File paths for the files to be put on the drive
        self.sample_sheet_mounted_folder = None
        self.seqid_mounted_folder = None
        self.sample_sheet_mounted_path = None

    def add_nas_seqid_path(self, path):

        if len(self.seqid_paths) is 1:
            self.both_exist = True  # both found, not need to continue searching
            self.seqid_paths.append(path)

        elif len(self.seqid_paths) is 0:
            self.seqid_paths.append(path)

        else:
             raise ImportWarning("More than 2 files found that have the SEQ-ID: %s", self.seqid_info.seq_id)

    def add_sample_sheet(self, nas_sheet_dir):
        """
        :param nas_sheet_dir: the directory of the sheet in the nas
        """
        csv_sheet_path = os.path.join(nas_sheet_dir, Sequence.csv_sheet)
        bak_sheet_path = os.path.join(nas_sheet_dir, Sequence.bak_sheet)

        if os.path.exists(csv_sheet_path):
            self.nas_sample_sheet_path = csv_sheet_path
        elif os.path.exists(bak_sheet_path):
            self.nas_sample_sheet_path = bak_sheet_path
            self.csv_file = False

    def add_mounted_folders_paths(self):

        self.seqid_mounted_folder = os.path.join(self.mounted_base_path, self.run_date, Sequence.seq_folder_structure)
        self.sample_sheet_mounted_folder = os.path.join(self.mounted_base_path, self.run_date)
        self.sample_sheet_mounted_path = os.path.join(self.sample_sheet_mounted_folder, Sequence.csv_sheet)


    def add_run_date(self, run_date):
        self.run_date = run_date


class SequenceInfo(object):
    def __init__(self, text_line):
        """
        :param text_line: this should have the format 'SEQ-ID   SampleName  Project#' - with /t as delimeters
        """
        input_list = text_line.split('\t')
        self.seq_id = str(input_list[0]).rstrip()
        self.sample_name = str(input_list[1]).rstrip()
        self.project_num = str(input_list[2]).rstrip()
        self.description = str(input_list[3]).rstrip()
