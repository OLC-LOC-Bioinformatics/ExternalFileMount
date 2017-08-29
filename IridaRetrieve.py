import os

from RedmineAPI.Utilities import FileExtension, create_time_log, get_validated_seqids
from RedmineAPI.Access import RedmineAccess
from RedmineAPI.Configuration import Setup

from Utilities import CustomValues, CustomKeys
from Extract_Files import MassExtractor
from Sequence_File import SequenceInfo


class Automate(object):

    def __init__(self, force):

        # create a log, can be written to as the process continues
        self.timelog = create_time_log(FileExtension.runner_log)

        # Key: used to index the value to the config file for setup
        # Value: 3 Item Tuple ("default value", ask user" - i.e. True/False, "type of value" - i.e. str, int....)
        # A value of None is the default for all parts except for "Ask" which is True
        custom_terms = {CustomKeys.drive_mount: (CustomValues.drive_mount_path, True, str)}

        # Create a RedmineAPI setup object to create/read/write to the config file and get default arguments
        setup = Setup(time_log=self.timelog, custom_terms=custom_terms)
        setup.set_api_key(force)

        # Custom terms saved to the config after getting user input
        self.custom_values = setup.get_custom_term_values()
        self.drive_mnt = self.custom_values[CustomKeys.drive_mount]

        # Default terms saved to the config after getting user input
        self.seconds_between_checks = setup.seconds_between_check
        self.nas_mnt = setup.nas_mnt
        self.redmine_api_key = setup.api_key

        # Initialize Redmine wrapper
        self.access_redmine = RedmineAccess(self.timelog, self.redmine_api_key)

        self.botmsg = '\n\n_I am a bot. This action was performed automatically._'  # sets bot message
        # Subject name and Status to be searched on Redmine
        self.issue_title = 'irida retrieve'
        self.issue_status = 'New'

    def timed_retrieve(self):
        """
            If the drive location selected from the user can be found, then continuously search Redmine in time 
            intervals for the inputted period. Otherwise log the drive does not exist and do not continue.
            Log errors to the log file as they occur.
        """
        import time
        while True:
            if os.path.exists(self.drive_mnt):  # If the drive exists continue, otherwise wait

                # Get issues matching the issue status and title
                found_issues = self.access_redmine.retrieve_issues(self.issue_status, self.issue_title)
                # Respond to the issues in the list 1 at a time
                while len(found_issues) > 0:
                    self.respond_to_issue(found_issues.pop(len(found_issues) - 1))

                self.timelog.time_print("Waiting for the next check.")
                time.sleep(self.seconds_between_checks)
            else:
                self.timelog.time_print("Please connect the external drive. The process will not start until the drive "
                                        "is connected. If it is connect, ensure you have entered the correct path")
                time.sleep(self.seconds_between_checks)

    def respond_to_issue(self, issue):
        """
            Run the desired automation process on the inputted issue, if there is an error update the author
            :param issue: Specified Redmine issue information
        """

        self.timelog.time_print("Found a request to run. Subject: %s. ID: %s" % (issue.subject, issue.id))
        self.timelog.time_print("Adding to the list of responded to requests.")
        self.access_redmine.log_new_issue(issue)

        try:
            # Parse the attached file into lines, ensuring to strip any extra characters
            input_list = self.parse_redmine_attached_file(issue)
            # If there were no lines found in the file, exit the process for this issue
            if input_list is None:
                return

            # Parse each tab delimited line creating a SequenceInfo object for each, then store them in the list
            sequences_info = list()
            for input_line in input_list:
                if input_line is not '':
                    sequences_info.append(SequenceInfo(input_line))

            # Ensure the SEQ-IDs is validated for all entries
            sequences_info = get_validated_seqids(sequences_info)

            # Update the issue to In Progress and give the author an update on progress
            issue.redmine_msg = "The text file has been parsed and the SEQ-IDs have been validated. Beginning to move" \
                                "%d pairs of fastqs and the sample sheet to the drive.." % len(sequences_info)
            self.access_redmine.update_status_inprogress(issue, self.botmsg)

            # Create the path for the files to be moved to on the drive
            output_folder = os.path.join(self.drive_mnt, str(issue.id))

            # Process the inputs from Redmine and move the corresponding files to the mounted drive
            missing_files = MassExtractor(nas_mnt=self.nas_mnt).move_files(sequences_info, output_folder)

            # Set the issue back to the author and give a final response
            self.completed_response(issue, missing_files)

        except ValueError as e:
            import traceback
            self.timelog.time_print("[Warning] The automation process had a problem, continuing redmine api anyways.")
            self.timelog.time_print("[Automation Error Dump]\n" + traceback.format_exc())
            # Send response
            issue.redmine_msg = "There was a problem with your request. Please create a new issue on" \
                                " Redmine to re-run it.\n%s" % traceback.format_exc()
            # Set it to feedback and assign it back to the author
            self.access_redmine.update_issue_to_author(issue, self.botmsg)

    def completed_response(self, issue, missing):
        """
            Update the issue back to the author once the process has finished
            :param issue: Specified Redmine issue the process has been completed on
            :param missing: List of missing files that could not be found on the nas ???????????????????????????????
        """
        notes = "Completed extracting files to the drive, it is available to pickup for this support request. \n" \
                "Results stored at ~/My Passport/%d" % issue.id
        missing_files = ""

        if len(missing) > 0:
            notes += '\nSome files are missing:\n'
            for file in missing:
                missing_files += file + '\n'

        # Assign the request back to the author
        self.access_redmine.update_issue_to_author(issue, notes + missing_files + self.botmsg)

        self.timelog.time_print("The request has been completed. " + missing_files +
                                "The next request will be processed once available.")

    def parse_redmine_attached_file(self, issue):
        """
        Read the text file that was submitted on Redmine, then split the text file into a list of separate lines. 
        * Ensure to strip any extra characters off of the lines
        :param issue: Specified Redmine issue of which the attached file must be processed
        :return: A list of lines from the attached file, return None if the text file is empty or an error occurs
        """
        try:
            # Get the attached text file from Redmine
            txt_file = self.access_redmine.get_attached_text_file(issue, 0)

            if txt_file is not None:
                # Split the text file, and strip off any extra characters
                txt_lines = txt_file.split('\n')
                txt_lines = [x.strip() for x in txt_lines]
                return txt_lines
            else:
                issue.redmine_msg = "No file with the proper format was uploaded to the request. Please attach " \
                                    "another file to try again."
                self.timelog.time_print(issue.redmine_msg)
                self.access_redmine.update_issue_to_author(issue, self.botmsg)
                return None

        except KeyError:
            issue.redmine_msg = "The file uploaded had invalid properties. Please upload a new request with another " \
                       "file to try again."
            self.timelog.time_print(issue.redmine_msg)
            self.access_redmine.update_issue_to_author(issue, self.botmsg)
            return None