import os


class Sequence:

    csv_sheet = 'SampleSheet.csv'
    bak_sheet = 'SampleSheet.bak2'

    def __init__(self, sequence_info):

        self.seqid_paths = list()  # list has a maximum size of 2 SEQ-IDs (R1 & R2 pair)
        self.seqid_info = sequence_info  # info given through the text document on Redmine
        self.nas_sample_sheet_path = None  # path to the sample sheet in the nas
        self.both_exist = False  # flag when a pair of SEQ-ID are found
        self.run_date = "01012000"
        self.csv_file = True

        # File paths for the files to be put on the drive
        self.seqid_mounted_folder = None
        self.sample_sheet_mounted_path = None

    def add_nas_seqid_path(self, path):

        if len(self.seqid_paths) is 1:
            self.both_exist = True  # both found, no need to continue searching
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


class SequenceInfo(object):
    def __init__(self, text_line):
        """
        :param text_line: this should have the format 'SampleName   SampleId    SampleProject' 
        with /t as delimeters
        """
        input_list = text_line.split('\t')
        self.sample_name = str(input_list[0]).rstrip()
        self.sample_id = str(input_list[1]).rstrip()
        self.sample_project = str(input_list[2]).rstrip()
