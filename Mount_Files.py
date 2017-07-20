import os

from RedmineAPI.Utilities import FileExtension, create_time_log, get_validated_seqids
from RedmineAPI.Access import RedmineAccess
from RedmineAPI.Configuration import Setup

from Utilities import CustomValues, CustomKeys
from Extract_Files import MassExtractor
from Sequence_File import SequenceInfo


class MountFiles(object):

    def __init__(self, force):

        self.timelog = create_time_log(FileExtension.runner_log)

        # dictionary : with 3 value Tuple to store the custom term arguments to be stored in the config file
        custom_terms = {CustomKeys.drive_mount: (CustomValues.drive_mount_path, True, str)}
        setup = Setup(time_log=self.timelog, custom_terms=custom_terms)
        setup.set_api_key(force)
        # return a dictionary with the value inputted by the user or loaded from the config file
        self.custom_values = setup.get_custom_term_values()

        self.drive_mnt = self.custom_values[CustomKeys.drive_mount]
        self.seconds_between_checks = setup.seconds_between_check
        self.nas_mnt = setup.nas_mnt
        self.redmine_api_key = setup.api_key

        self.redmine_access = RedmineAccess(self.timelog, self.redmine_api_key)

        self.botmsg = '\n\n_I am a bot. This action was performed automatically._'  # sets bot message
        self.issue_title = 'irida retrieve'
        self.issue_status = 'Feedback'

    def timed_retrieve(self):
        import time
        while True:
            if os.path.exists(self.drive_mnt):  # if the drive exists continue, otherwise wait

                # Get issues matching the issue status and title
                found_issues = self.redmine_access.retrieve_issues(self.issue_status, self.issue_title)
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
            sequences_info = get_validated_seqids(sequences_info)
            response = "Moving %d pairs of fastqs and the sample sheet to the drive..." % len(sequences_info)

            # Set the issue to in progress since the Extraction is running
            self.redmine_access.update_status_inprogress(issue, response + self.botmsg)
            self.run_request(issue, sequences_info, output_folder)

        except ValueError as e:
            response = "Sorry, there was a problem with your request:\n%s\n" \
                       "Please submit a new request and close this one." % e.args[0]

            # If something went wrong set the status to feedback and assign the author the issue
            self.redmine_access.update_issue_to_author(issue, response + self.botmsg)

    def parse_redmine_attached_file(self, issue):
        # Turn the description from the Redmine Request into a list of lines
        try:
            txt_file = self.redmine_access.get_attached_text_file(issue, 0)

            if txt_file is not None:
                txt_lines = txt_file.split('\n')
                txt_lines = [x.strip() for x in txt_lines]
                return txt_lines
            else:
                response = "No file with the proper format was uploaded to the request. Please attach another " \
                           "file to try again."
                self.timelog.time_print(response)
                self.redmine_access.update_issue_to_author(issue, response + self.botmsg)

        except KeyError:
            response = "The file uploaded had invalid properites. Please upload a new request with another " \
                       "file to try again."
            self.timelog.time_print(response)
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
