import os


class CustomDefaultValues:
    """
    Default values specific to the automation task
    """
    drive_mount_path = "/media/bownessn/My Passport/"


class CustomJsonKeys:
    """
    Json keys to be found in the config file specific to the automation task
    """
    drive_mount = 'drive_mnt'


class UtilityMethods:
    @staticmethod
    def create_dir(basepath, path_ext=""):
        """ Creates the the output directory if it doesn't exist """
        if not os.path.exists(os.path.join(basepath, path_ext)):
            os.makedirs(os.path.join(basepath, path_ext))
