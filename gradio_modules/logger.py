import os


class Logger:
    def __init__(self, filepath):
        self.filename = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    def write(self, message):
        with open(self.filename, "a") as f:
            f.write(message + "\n")

    def isatty(self):
        return False

    def reset_logs(self):
        with open(self.filename, "w") as file:
            file.truncate(0)

    def read_logs(self):
        if os.path.exists(self.filename):
            # Read the entire content of the log file
            with open(self.filename, "r") as f:
                log_content = f.readlines()

            recent_lines = log_content[-30:]
            return "".join(recent_lines)
        else:
            return "로그 생성 대기중..."
