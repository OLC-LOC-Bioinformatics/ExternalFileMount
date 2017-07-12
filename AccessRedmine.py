from pyaccessories.SaveLoad import SaveLoad
from RedmineAPI.RedmineAPI import RedmineInterface
from Utilities import DefaultValues, FileExtension
from RedmineIssue import Issue
import os

class Redmine:

    def __init__(self, api_key):
        self.api_key = api_key
        self.redmine_api = RedmineInterface('http://redmine.biodiversity.agr.gc.ca/', self.api_key)

        import sys
        script_dir = sys.path[0]  # copy current path
        self.issue_loader = SaveLoad(os.path.join(script_dir, FileExtension.issues_json),
                                     create=True)
        self.rm_responded_issues = set(self.issue_loader.get(DefaultValues.responded_issues, default=[], ask=False))

    def retrieve_issues(self, issue_status, issue_title):

        data = self.redmine_api.get_new_issues('cfia')
        found_issues = []

        # find all 'issues' on redmine, add them to data
        # Sort through all the issues with status -> 'New' and added them to found
        for issue in data['issues']:
            if issue['id'] not in self.rm_responded_issues and issue['status']['name'] == issue_status:
                if issue['subject'].lower().rstrip() == issue_title:
                    found_issues.append(Issue(issue))

        return found_issues

    def get_attached_files(self, issue):
        redmine_data = self.redmine_api.get_issue_data(issue.id)
        return redmine_data['issue']['attachments']

    def log_new_issue(self, issue):
        # add files to the responded log so the action will not be performed again
        self.rm_responded_issues.add(issue.id)
        self.issue_loader.responded_issues = list(self.rm_responded_issues)
        self.issue_loader.dump()

    def update_status_inprogress(self, issue, message):
        self.redmine_api.update_issue(issue.id, notes=message, status_change=2)

    def update_issue_to_author(self, issue, message):
        self.redmine_api.update_issue(issue.id, notes=message, status_change=4, assign_to_id=issue.author_id)
