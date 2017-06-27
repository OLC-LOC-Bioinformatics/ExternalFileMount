import os

class ListType:
    fastq = 'fastqs'
    fasta = 'fastas'


class Mode:
    fasta = 'fasta'
    fastq = 'fastq'


def get_input(nas_mnt, drive_mnt, sequences_list, redmine_id):
    regex = r'^(2\d{3}-\w{2,10}-\d{3,4})$'
    inputs = {
        ListType.fastq: list(),
        'outputfolder': os.path.join(drive_mnt, str(redmine_id))
    }

    import re
    for sequence in sequences_list:
        if re.match(regex, sequence.seq_id):
            inputs[ListType.fastq].append(sequence)
        else:
            raise ValueError("Invalid seq-id \"%s\"" % sequence.seq_id)

    if len(inputs[ListType.fastq]) < 1:
        raise ValueError("Invalid format for redmine request. Couldn't find any fastas or fastqs to extract")

    return inputs
