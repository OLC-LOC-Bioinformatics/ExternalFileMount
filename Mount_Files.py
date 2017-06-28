import os
from pyaccessories.SaveLoad import SaveLoad
from Utilities import DefaultValues, JsonKeys, FileExtension, UtilityMethods
from RedmineAPI.RedmineAPI import RedmineInterface
from Encryption import Encryption
from Extract_Files import MassExtractor
from Sequence_File import SequenceInfo


class MountFiles(object):

    def __init__(self, force):

        import sys
        script_dir = sys.path[0]  # copy current path
        self.config_json = os.path.join(script_dir, FileExtension.config_json)  # get the the json config file dir

        UtilityMethods.create_dir(script_dir, FileExtension.runner_log)
        self.timelog = UtilityMethods.create_timerlog(script_dir, FileExtension.runner_log)
        self.timelog.set_colour(30)

        # Load issues that the bot has already responded to
        self.issue_loader = SaveLoad(os.path.join(script_dir, FileExtension.issues_json),
                                     create=True)  # creates a save load object
        self.responded_issues = set(self.issue_loader.get(DefaultValues.responded_issues, default=[], ask=False))

        # Load information from the config if possible
        # Otherwise they are entered by the user (with the keyboard or hitting enter for default)
        self.loader = SaveLoad(self.config_json, create=True)
        self.redmine_api_key = self.loader.get(JsonKeys.redmine_api_key_encrypted, default='none',
                                               ask=False)  # gives default as none, so must be entered

        self.first_run = self.loader.get(JsonKeys.first_run, default=DefaultValues.first_run, ask=False)
        self.nas_mnt = os.path.normpath(self.loader.get(JsonKeys.nas_mount, default=DefaultValues.nas_mount_path,
                                                        get_type=str))
        self.drive_mnt = os.path.normpath(self.loader.get(JsonKeys.drive_mount, default=DefaultValues.drive_mount_path,
                                                          get_type=str))
        self.seconds_between_redmine_checks = self.loader.get(JsonKeys.secs_between_redmine_checks,
                                                              default=DefaultValues.check_time, get_type=int)

        self.key = DefaultValues.encryption_key  # a string to decript and encrypt the json files
        self.redmine = None
        self.botmsg = '\n\n_I am a bot. This action was performed automatically._'  # sets bot message

        try:
            self.set_api_key(force)
            self.timed_retrieve()

        except Exception as e:
            import traceback
            self.timelog.time_print("[Error] Dumping...\n%s" % traceback.format_exc())
            raise

    def set_api_key(self, force):
        if self.first_run == 'yes':
            choice = 'y'
            if force:
                raise ValueError('Need redmine API key!')
        else:
            if force:
                choice = 'n'
            else:
                self.timelog.time_print("Would you like to set the redmine api key? (y/n)")
                choice = input()
        if choice == 'y':
            self.timelog.time_print("Enter your redmine api key (will be encrypted to file)")
            self.redmine_api_key = input()
            # Encode and send to json file
            self.loader.redmine_api_key_encrypted = Encryption.encode(self.key, self.redmine_api_key).decode('utf-8')
            self.loader.first_run = 'no'
            self.loader.dump(self.config_json)
        else:
            # Import and decode from file
            self.redmine_api_key = Encryption.decode(self.key, self.redmine_api_key)

        import re
        if not re.match(r'^[a-z0-9]{40}$', self.redmine_api_key):
            self.timelog.time_print("Invalid Redmine API key!")
            exit(1)

        self.redmine = RedmineInterface('http://redmine.biodiversity.agr.gc.ca/', self.redmine_api_key)

    def timed_retrieve(self):
        import time
        while True:
            self.run_retrieve()
            self.timelog.time_print("Waiting for the next check.")
            time.sleep(self.seconds_between_redmine_checks)

    def run_retrieve(self):
        self.timelog.time_print("Checking for extraction requests...")

        data = self.redmine.get_new_issues('cfia')
        found = []

        # find all 'issues' on redmine, add them to data
        # Sort through all the issues with status -> 'New' and added them to found
        for issue in data['issues']:
            if issue['id'] not in self.responded_issues and issue['status']['name'] == 'New':
                if issue['subject'].lower().rstrip() == 'irida retrieve':
                    found.append(issue)

        self.timelog.time_print("Found %d new issue(s)..." % len(found))  # returns number of issues

        while len(found) > 0:  # While there are still issues to respond to
            self.respond_to_issue(found.pop(len(found)-1))

    def respond_to_issue(self, issue):

        self.timelog.time_print("Found a request to run. Subject: %s. ID: %s" % (issue['subject'], issue['id']))
        self.timelog.time_print("Adding to the list of responded to requests.")

        # add files to the responded log so the action will not be performed again
        self.responded_issues.add(issue['id'])
        self.issue_loader.responded_issues = list(self.responded_issues)
        self.issue_loader.dump()

        sequences_info = list()
        input_list = self.parse_redmine_attached_file(issue)
        output_folder = os.path.join(self.drive_mnt, str(issue['id']))

        for input_line in input_list:
            if input_line is not '':
                sequences_info.append(SequenceInfo(input_line))

        try:
            sequences_info = self.add_validated_seqids(sequences_info)
            response = "Moving %d pairs of fastqs and the sample sheet to the drive..." % len(sequences_info)

            # Set the issue to in progress since the Extraction is running
            self.redmine.update_issue(issue['id'], notes=response + self.botmsg, status_change=2)
            self.timelog.time_print('\n' + response)
            self.run_request(issue, sequences_info, output_folder)

        except ValueError as e:
            response = "Sorry, there was a problem with your request:\n%s\n" \
                       "Please submit a new request and close this one." % e.args[0]

            # If something went wrong set the status to feedback and assign the author the issue
            get = self.redmine.get_issue_data(issue['id'])
            self.redmine.update_issue(issue['id'], notes=response + self.botmsg, status_change=4,
                                      assign_to_id=get['issue']['author']['id'])

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
            msg = traceback.format_exc()

            # Set it to feedback and assign it back to the author
            get = self.redmine.get_issue_data(os.path.split(output_folder)[-1])
            self.redmine.update_issue(issue['id'],
                                      notes="There was a problem with your request. Please create a new issue on"
                                            " Redmine to re-run it.\n%s" % msg + self.botmsg,
                                      status_change=4,
                                      assign_to_id=get['issue']['author']['id'])

    def completed_response(self, issue, missing):
        notes = "Completed extracting files to the drive, it is available to pickup for this support request. \n" \
                "Results stored at %d" % issue['id']
        missing_files = ""

        if len(missing) > 0:
            notes += '\nSome files are missing:\n'
            for file in missing:
                missing_files += file + '\n'

        # Assign the request back to the author
        get = self.redmine.get_issue_data(issue['id'])
        self.redmine.update_issue(issue['id'], notes + missing_files + self.botmsg, status_change=4,
                                  assign_to_id=get['issue']['author']['id'])

        self.timelog.time_print("The request has been completed. " + missing_files +
                                "The next request will be processed once available/")

    def parse_redmine_attached_file(self, issue):
        # Turn the description from the Redmine Request into a list of lines
        redmine_data = self.redmine.get_issue_data(issue['id'])
        try:
            attachment = redmine_data['issue']['attachments']

            if len(attachment) > 0:
                file_name = attachment[0]['filename']
                self.timelog.time_print("Found the attachment to the Redmine Request: %s" % file_name)
                self.timelog.time_print("Downloading file.....")

                txt_file = self.redmine.download_file(attachment[0]['content_url'])

                txt_lines = txt_file.split('\n')
                txt_lines = [x.strip() for x in txt_lines]
                return txt_lines

        except KeyError:
            response = "The file uploaded had invalid properites. Please upload a new request with another " \
                       "file to try again."
            self.timelog.time_print(response)
            get = self.redmine.get_issue_data(issue['id'])
            # self.redmine.update_issue(issue['id'], notes=response + self.botmsg, status_change=4,
            #                           assign_to_id=get['issue']['author']['id'])

    def add_validated_seqids(self, sequences_list):

        validated_sequence_list = list()
        regex = r'^(2\d{3}-\w{2,10}-\d{3,4})$'
        import re
        for sequence in sequences_list:
            if re.match(regex, sequence.seq_id):
                validated_sequence_list.append(sequence)
            else:
                raise ValueError("Invalid seq-id \"%s\"" % sequence.seq_id)

        if len(validated_sequence_list) < 1:
            raise ValueError("Invalid format for redmine request. Couldn't find any fastas or fastqs to extract")

        return validated_sequence_list
