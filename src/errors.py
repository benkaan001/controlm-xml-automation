class ControlMXmlError(Exception):
    """Custom exception for Control-M XML modification errors."""
    def __init__(self, message, step=None):
        super().__init__(message)
        self.step = step
