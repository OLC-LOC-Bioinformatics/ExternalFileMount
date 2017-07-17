import os

from RedmineAPI.pyaccessories.SaveLoad import SaveLoad
from RedmineAPI.RedmineUtilities import DefaultValues, JsonKeys, FileExtension, create_timerlog
from RedmineAPI.Encryption import Encryption
from RedmineAPI.AccessRedmine import Redmine

from Utilities import CustomDefaultValues, CustomJsonKeys, UtilityMethods
from Extract_Files import MassExtractor
from Sequence_File import SequenceInfo


class MountFiles(object):

    def __init__(self):

        import sys
        script_dir = sys.path[0]  # copy current path
        self.config_json = os.path.join(script_dir, FileExtension.config_json)  # get the the json config file dir

        UtilityMethods.create_dir(script_dir, FileExtension.runner_log)
        self.timelog = create_timerlog(script_dir, FileExtension.runner_log)
        self.timelog.set_colour(30)

        # Load information from the config if possible
        # Otherwise they are entered by the user (with the keyboard or hitting enter for default)
        self.loader = SaveLoad(self.config_json, create=True)
        self.redmine_api_key = self.loader.get(JsonKeys.redmine_api_key_encrypted, default='none',
                                               ask=False)  # gives default as none, so must be entered

        self.first_run = self.loader.get(JsonKeys.first_run, default=DefaultValues.first_run, ask=False)
        self.nas_mnt = os.path.normpath(self.loader.get(JsonKeys.nas_mount, default=DefaultValues.nas_mount_path,
                                                        get_type=str))
        self.seconds_between_redmine_checks = self.loader.get(JsonKeys.secs_between_redmine_checks,
                                                              default=DefaultValues.check_time, get_type=int)
        self.drive_mnt = os.path.normpath(self.loader.get(CustomJsonKeys.drive_mount,
                                                          default=CustomDefaultValues.drive_mount_path, get_type=str))

        self.key = DefaultValues.encryption_key
        self.redmine_access = None

        self.botmsg = '\n\n_I am a bot. This action was performed automatically._'  # sets bot message
        self.issue_title = 'irida retrieve'
        self.issue_status = 'New'

    def set_api_key(self, force):

        if self.first_run == 'yes' and force:
            raise ValueError('Need redmine API key!')
        elif self.first_run == 'yes':
            input_api_key = 'y'
        elif not self.first_run == 'yes' and force:
            input_api_key = 'n'
        else:
            self.timelog.time_print("Would you like to set the redmine api key? (y/n)")
            input_api_key = input()

        if input_api_key == 'y':
            self.timelog.time_print("Enter your redmine api key (will be encrypted to file)")
            self.redmine_api_key = input()
            # Encode and send to json file
            self.loader.redmine_api_key_encrypted = Encryption.encode(self.key, self.redmine_api_key).decode('utf-8')
            self.loader.first_run = 'no'
            self.loader.dump(self.config_json)
        else:
            # Import and decode from file
            self.timelog.time_print("Used Redmine API key from the json file.")
            self.redmine_api_key = Encryption.decode(self.key, self.redmine_api_key)

        import re
        if not re.match(r'^[a-z0-9]{40}$', self.redmine_api_key):
            self.timelog.time_print("Invalid Redmine API key!")
            exit(1)

        self.redmine_access = Redmine(self.timelog, self.redmine_api_key)

    def timed_retrieve(self):
        import time
        while True:
            if os.path.exists(self.drive_mnt):
                self.run_retrieve()
                self.timelog.time_print("Waiting for the next check.")
                time.sleep(self.seconds_between_redmine_checks)
            else:
                self.timelog.time_print("Please connect the external drive. The process will not start until the drive "
                                        "is connected. If it is connect, ensure you have entered the correct path")
                time.sleep(self.seconds_between_redmine_checks)

    def run_retrieve(self):
        self.timelog.time_print("Checking for extraction requests...")

        found = self.redmine_access.retrieve_issues(self.issue_status, self.issue_title)
        self.timelog.time_print("Found %d new issue(s)..." % len(found))  # returns number of issues

        while len(found) > 0:  # While there are still issues to respond to
            self.respond_to_issue(found.pop(len(found)-1))

    def respond_to_issue(self, issue):

        self.timelog.time_print("Found a request to run. Subject: %s. ID: %s" % (issue.subject, issue.id))
        self.timelog.time_print("Adding to the list of responded to requests.")

        self.redmine_access.log_new_issue(issue)

        sequences_info = list()
        input_list = self.parse_redmine_attached_file(issue)
        output_folder = os.path.join(self.drive_mnt, str(issue.id))

        for input_line in input_list:
            if input_line is not '':
                sequences_info.append(SequenceInfo(input_line))

        try:
            sequences_info = self.add_validated_seqids(sequences_info)
            response = "Moving %d pairs of fastqs and the sample sheet to the drive..." % len(sequences_info)

            # Set the issue to in progress since the Extraction is running
            self.redmine_access.update_status_inprogress(issue, response + self.botmsg)
            self.run_request(issue, sequences_info, output_folder)

        except ValueError as e:
            response = "Sorry, there was a problem with your request:\n%s\n" \
                       "Please submit a new request and close this one." % e.args[0]

            # If something went wrong set the status to feedback and assign the author the issue
            self.redmine_access.update_issue_to_author(issue, response + self.botmsg)

    def run_request(self, issue, sequences_info, output_folder):
        # Parse input
        # noinspection PyBroadException
        try:
            # process the inputs from Redmine and move the corresponding files to the mounted drive
            missing_files = MassExtractor(nas_mnt=self.nas_mnt).move_files(sequences_info, output_folder)
            # Respond on redmine
            self.completed_response(issue, missing_files)

        except Exception as e:
            import traceback
            self.timelog.time_print("[Warning] run.py had a problem, continuing redmine api anyways.")
            self.timelog.time_print("[Irata Retrieve Error Dump]\n" + traceback.format_exc())
            # Send response
            message = "There was a problem with your request. Please create a new issue on" \
                      " Redmine to re-run it.\n%s" % traceback.format_exc() + self.botmsg
            # Set it to feedback and assign it back to the author
            self.redmine_access.update_issue_to_author(issue, message)

    def completed_response(self, issue, missing):
        notes = "Completed extracting files to the drive, it is available to pickup for this support request. \n" \
                "Results stored at ~/My Passport/%d" % issue.id
        missing_files = ""

        if len(missing) > 0:
            notes += '\nSome files are missing:\n'
            for file in missing:
                missing_files += file + '\n'

        # Assign the request back to the author
        self.redmine_access.update_issue_to_author(issue, notes + missing_files + self.botmsg)

        self.timelog.time_print("The request has been completed. " + missing_files +
                                "The next request will be processed once available.")

    def parse_redmine_attached_file(self, issue):
        # Turn the description from the Redmine Request into a list of lines
        try:
            attachment = self.redmine_access.get_attached_files(issue)

            if len(attachment) > 0:
                file_name = attachment[0]['filename']
                self.timelog.time_print("Found the attachment to the Redmine Request: %s" % file_name)
                self.timelog.time_print("Downloading file.....")

                txt_file = self.redmine_access.redmine_api.download_file(attachment[0]['content_url'])

                txt_lines = txt_file.split('\n')
                txt_lines = [x.strip() for x in txt_lines]
                return txt_lines

        except KeyError:
            response = "The file uploaded had invalid properites. Please upload a new request with another " \
                       "file to try again."
            self.timelog.time_print(response)
            self.redmine_access.update_issue_to_author(issue, response + self.botmsg)

    def add_validated_seqids(self, sequences_list):

        validated_sequence_list = list()
        regex = r'^(2\d{3}-\w{2,10}-\d{3,4})$'
        import re
        for sequence in sequences_list:
            if re.match(regex, sequence.sample_name):
                validated_sequence_list.append(sequence)
            else:
                raise ValueError("Invalid seq-id \"%s\"" % sequence.sample_name)

        if len(validated_sequence_list) < 1:
            raise ValueError("Invalid format for redmine request. Couldn't find any fastas or fastqs to extract")

        return validated_sequence_list
