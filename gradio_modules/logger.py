import os

import aiofiles


class Logger:
    def __init__(self, filepath):
        self.filename = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    def write(self, message):
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    async def awrite(self, message):
        async with aiofiles.open(self.filename, mode="a", encoding="utf-8") as f:
            await f.write(message + "\n")

    def isatty(self):
        return False

    def reset_logs(self):
        with open(self.filename, "w", encoding="utf-8") as file:
            file.truncate(0)

    def read_logs(self):
        if os.path.exists(self.filename):
            # Read the entire content of the log file
            with open(self.filename, "r", encoding="utf-8") as f:
                log_content = f.readlines()

            recent_lines = log_content[-30:]
            return "".join(recent_lines)
        else:
            return "로그 생성 대기중..."
