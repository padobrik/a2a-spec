"""Exit codes shared by every handshake command.

When a run has both kinds of problems, EXIT_INPUT wins: the run was not
complete, so its passes cannot be trusted.
"""

EXIT_OK = 0
EXIT_FAILED = 1  # the check found problems
EXIT_INPUT = 2  # configuration or input error: the command could not run as asked
