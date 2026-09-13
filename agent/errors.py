class AgentContractError(Exception):
    """Internal marker for sanitized contract failures."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message