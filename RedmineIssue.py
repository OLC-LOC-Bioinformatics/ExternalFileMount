class Issue:
    def __init__(self, issue):
        self.subject = issue['subject']
        self.id = issue['id']

        self.author = issue['author']
        self.author_id = self.author['id']
        self.author_name = self.author['name']
