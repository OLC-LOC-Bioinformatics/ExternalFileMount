import os
import datetime
from pyaccessories.TimeLog import Timer

class DefaultValues:

    # default values
    nas_mount_path = "/mnt/nas/"
    drive_mount_path = "/media/bownessn/My Passport/"
    check_time = 600
    first_run = 'yes'

    # Normal Keys
    responded_issues = 'responded_issues'
    encryption_key = 'Sixteen byte key'

class JsonKeys:

    # Config Json Keys
    redmine_api_key_encrypted = 'redmine_api_key_encrypted'
    first_run = 'first_run'
    secs_between_redmine_checks = 'secs_between_redmine_checks'
    nas_mount = 'nasmnt'
    drive_mount = 'drive_mnt'


class FileExtension:

    # Path or extensions (extn)
    config_json = 'config.json'
    runner_log = 'runner_logs'
    issues_json = 'responded_issues.json'


class UtilityMethods:
    @staticmethod
    def create_dir(basepath, path_ext=""):
        """ Creates the the output directory if it doesn't exist """
        if not os.path.exists(os.path.join(basepath, path_ext)):
            os.makedirs(os.path.join(basepath, path_ext))

    @staticmethod
    def create_timerlog(basepath, path_ext):
        return Timer(log_file=os.path.join(basepath, path_ext,
                                           datetime.datetime.now().strftime("%d-%m-%Y_%H:%M:%S")))