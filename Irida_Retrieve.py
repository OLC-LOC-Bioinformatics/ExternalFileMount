from Mount_Files import MountFiles

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--force", action="store_true",
                        help="Don't ask to update redmine api key")

    args = parser.parse_args()
    mount_files = MountFiles()

    # try to run the program, if an error occurs print it
    try:
        mount_files.set_api_key(args.force)
        mount_files.timed_retrieve()
    except Exception as e:
        import traceback

        mount_files.timelog.time_print("[Error] Dumping...\n%s" % traceback.format_exc())
        raise
